"""Minimal secret scan for this repository (no external scanner is installed).
Run from the repository root: python backend/scripts/secret_scan.py

Checks every tracked file and every commit's diff in git history for common credential patterns,
plus the *values* currently set in backend/.env (JWT_SECRET, SEED_USER_PASSWORD, ANTHROPIC_API_KEY),
without printing them. Exit code 1 if anything is found. A clean result is not proof of absence."""

from __future__ import annotations

import re
import subprocess  # noqa: S404 - fixed git commands
import sys
from pathlib import Path

PATTERNS = {
    "anthropic_key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private_key": re.compile(r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    # NAME=value in config-like text; value must look like a credential (not code such as `').Split(`).
    "assigned_secret": re.compile(
        r"(?i)\b(JWT_SECRET|ANTHROPIC_API_KEY|SEED_USER_PASSWORD)\s*=\s*['\"]?([A-Za-z0-9][A-Za-z0-9_\-+/=.]{7,})"
    ),
}
ALLOWED_ASSIGNMENTS = {"replace-with-a-long-random-string-of-at-least-32-chars"}
# Test fixtures use deliberate, test-only values (e.g. tests/conftest.py TEST_JWT_SECRET); the key-format
# patterns still apply to them.
TEST_ONLY = ("backend/tests/",)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8",  # noqa: S603, S607
                          errors="replace", check=True).stdout


def env_values(root: Path) -> dict[str, str]:
    env = root / "backend" / ".env"
    out = {}
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(JWT_SECRET|SEED_USER_PASSWORD|ANTHROPIC_API_KEY)=(.+)$", line.strip())
            if m and len(m.group(2)) >= 8:
                out[m.group(1)] = m.group(2)
    return out


def scan(text: str, where: str, secrets: dict[str, str]) -> list[str]:
    hits = []
    for name, rx in PATTERNS.items():
        if name == "assigned_secret" and where.startswith(TEST_ONLY):
            continue
        for m in rx.finditer(text):
            if name == "assigned_secret" and (m.group(2) in ALLOWED_ASSIGNMENTS or "test" in m.group(2).lower()):
                continue
            hits.append(f"{where}: pattern {name}")
    hits += [f"{where}: value of {name} from backend/.env" for name, value in secrets.items() if value in text]
    return hits


def main() -> int:
    root = Path(git("rev-parse", "--show-toplevel").strip())
    secrets = env_values(root)
    findings: list[str] = []
    files = [f for f in git("ls-files").splitlines() if f]
    for f in files:
        path = root / f
        if path.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".ico"} or not path.is_file():
            continue
        findings += scan(path.read_text(encoding="utf-8", errors="replace"), f, secrets)
    history = git("log", "--all", "-p", "--no-color", "--", ".", ":(exclude)*.pdf", ":(exclude)*.png")
    per_file: dict[str, list[str]] = {}
    current = "(unknown)"
    for line in history.splitlines():  # split the history by file so path rules apply to it as well
        if line.startswith("+++ b/"):
            current = line[6:]
        per_file.setdefault(current, []).append(line)
    for path, lines in per_file.items():
        findings += [f"git history: {h}" for h in scan("\n".join(lines), path, secrets)]
    print(f"scanned {len(files)} tracked files and {git('rev-list', '--all', '--count').strip()} commits; "
          f"checked {len(secrets)} local secret value(s) from backend/.env")
    for line in sorted(set(findings)):
        print("FOUND", line)
    print("result:", "FINDINGS" if findings else "no secrets found")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
