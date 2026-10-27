"""Bounded local load test (NFR-005/006). Run against a LOCAL API only:
python -m scripts.perf_smoke [--base http://127.0.0.1:8000/api/v1] [--users 10] [--requests 200]

Structured lookups: `--requests` requests per endpoint, `--users` concurrent workers (NFR-005 target:
p95 ≤ 500 ms at 10 concurrent users, provisional). Chat (RAG, local embeddings, extractive answers, no
external LLM): a small fixed sample spread across accounts to stay under the 20/min/user chat limit.
Writes data/evaluation/results/perf_smoke.json. Only synthetic demo accounts are used."""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import httpx
from dotenv import dotenv_values

ACCOUNTS = {
    "member": "priya.member@example.test",
    "member2": "lee.member@example.test",
    "provider": "jordan.provider@example.test",
    "agent": "sam.agent@example.test",
    "admin": "alex.admin@example.test",
}
CHAT_USERS = ["priya.member@example.test", "lee.member@example.test", "robin.member@example.test",
              "jordan.provider@example.test", "casey.provider@example.test"]
QUESTIONS = ["How many outpatient physical therapy visits are covered per plan year?",
             "How long do I have to file an appeal for a denied claim?",
             "What does the claim status pending information mean?",
             "What is the emergency room copay?"]


def pct(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    k = (len(ordered) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo), 1)


def login(client: httpx.Client, email: str, password: str) -> str:
    r = client.post("/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def bench(client: httpx.Client, name: str, method: str, path: str, token: str | None, n: int, users: int,
          body_fn=None, ok=(200,)) -> dict:
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    def one(_):
        started = time.perf_counter()
        r = client.request(method, path, headers=headers, json=body_fn() if body_fn else None)
        return (time.perf_counter() - started) * 1000, r.status_code in ok

    client.request(method, path, headers=headers, json=body_fn() if body_fn else None)  # warm-up (not counted)
    wall = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(one, range(n)))
    wall = time.perf_counter() - wall
    times = [t for t, _ in results]
    errors = sum(1 for _, good in results if not good)
    return {"name": name, "requests": n, "concurrency": users, "p50_ms": pct(times, 0.5), "p95_ms": pct(times, 0.95),
            "max_ms": round(max(times), 1), "error_rate": round(errors / n, 4), "throughput_rps": round(n / wall, 1)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    parser.add_argument("--users", type=int, default=10)
    parser.add_argument("--requests", type=int, default=200)
    # Admin metrics run ~20 aggregate queries each; a realistic admin load is a few concurrent users.
    parser.add_argument("--metrics-users", type=int, default=10)
    args = parser.parse_args()
    if not args.base.startswith(("http://127.0.0.1", "http://localhost")):
        raise SystemExit("perf_smoke only targets a local API")
    password = os.environ.get("SEED_USER_PASSWORD") or dotenv_values(".env").get("SEED_USER_PASSWORD")
    limits = httpx.Limits(max_connections=args.users + 2, max_keepalive_connections=args.users + 2)
    out = {"environment": {"cpu_count": os.cpu_count(), "users": args.users, "requests_per_endpoint": args.requests,
                           "metrics_users": min(args.users, args.metrics_users)},
           "structured": [], "chat": None}
    with httpx.Client(base_url=args.base, timeout=30, limits=limits) as client:
        tok = {k: login(client, v, password) for k, v in ACCOUNTS.items()}
        n, u = args.requests, args.users
        out["structured"] = [
            bench(client, "GET /health", "GET", "/health", None, n, u),
            bench(client, "GET /claims (member)", "GET", "/claims", tok["member"], n, u),
            bench(client, "GET /claims/{number}", "GET", "/claims/SYN-CLM-2026-000101", tok["member"], n, u),
            bench(client, "GET /benefits/{plan}", "GET", "/benefits/SYN-PLAN-GOLD-01", tok["member"], n, u),
            bench(client, "GET /support-cases?scope=queue", "GET", "/support-cases?scope=queue", tok["agent"], n, u),
            bench(client, "GET /admin/metrics (30 days)", "GET", "/admin/metrics", tok["admin"], n,
                  min(u, args.metrics_users)),
            bench(client, "GET /documents (provider)", "GET", "/documents", tok["provider"], n, u),
        ]
        chat_tokens = [login(client, e, password) for e in CHAT_USERS]
        times, failures = [], 0

        def ask(i):
            started = time.perf_counter()
            r = client.post("/chat", headers={"Authorization": f"Bearer {chat_tokens[i % len(chat_tokens)]}"},
                            json={"message": QUESTIONS[i % len(QUESTIONS)], "client_message_id": str(uuid4())})
            return (time.perf_counter() - started) * 1000, r.status_code == 200

        with ThreadPoolExecutor(max_workers=3) as pool:
            for t, good in pool.map(ask, range(30)):
                times.append(t)
                failures += 0 if good else 1
        out["chat"] = {"name": "POST /chat (RAG, extractive, local embeddings)", "requests": 30, "concurrency": 3,
                       "p50_ms": pct(times, 0.5), "p95_ms": pct(times, 0.95), "max_ms": round(max(times), 1),
                       "error_rate": round(failures / 30, 4)}
    Path("data/evaluation/results").mkdir(parents=True, exist_ok=True)
    Path("data/evaluation/results/perf_smoke.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for row in out["structured"] + [out["chat"]]:
        print(f"{row['name']:<48} n={row['requests']:<4} c={row['concurrency']:<3} p50={row['p50_ms']:>7} ms  "
              f"p95={row['p95_ms']:>7} ms  max={row['max_ms']:>7} ms  errors={row['error_rate']:.2%}")


if __name__ == "__main__":
    main()
