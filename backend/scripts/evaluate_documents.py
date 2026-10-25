"""Evaluates document extraction and readiness rules on the synthetic sample corpus.
Run: python -m scripts.build_sample_documents && python -m scripts.evaluate_documents

Uses the real pipeline code (text extraction, the configured OCR engine, classification, field
extraction/validation) and the real rule engine with the seeded requirement sets. No database.
Extraction and checklist correctness are scored separately. Documents that need OCR are scored
only when an OCR engine is available; otherwise their observed behavior is reported as-is."""

from __future__ import annotations

import json
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import get_settings
from app.documents import fields as field_rules
from app.documents import readiness_rules as rules
from app.documents.extraction import extract_pages
from app.documents.ocr import build_ocr
from app.documents.validation import validate_upload
from scripts.seed_data import PA_REQUIREMENT_SETS

SAMPLES = Path("data/samples/documents")
RESULTS = Path("data/evaluation/results")
MIME = {".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg"}


def pct(n: int, d: int) -> str:
    return f"{100 * n / d:.1f}% ({n}/{d})" if d else "n/a"


def run() -> int:
    settings = get_settings()
    ocr = build_ocr(settings)
    ocr_ok = ocr.available()
    manifest = json.loads((SAMPLES / "expected.json").read_text(encoding="utf-8"))
    active = {s["procedure_code"] for s in PA_REQUIREMENT_SETS}
    extracted: dict[str, tuple[str, list]] = {}
    rows, timings = [], []

    for name, exp in manifest["documents"].items():
        data = (SAMPLES / name).read_bytes()
        started = time.perf_counter()
        checked = validate_upload(name, MIME[Path(name).suffix], data, settings)
        pages = extract_pages(data, checked.mime_type, settings, ocr, time.monotonic() + settings.job_timeout_seconds)
        doc_type = field_rules.classify(pages)
        results = field_rules.extract_fields(doc_type, pages, active, settings.extraction_low_confidence)
        timings.append({"document": name, "bytes": len(data), "pages": len(pages),
                        "ms": round((time.perf_counter() - started) * 1000, 1)})
        extracted[name] = (doc_type, results)
        scored = ocr_ok or not exp["needs_ocr"]
        by_name = {r.field_name: r for r in results}
        for field_name, want in exp["fields"].items():
            got = by_name.get(field_name)
            rows.append({
                "document": name, "field": field_name, "scored": scored, "expected_status": want["status"],
                "actual_status": got.validation_status if got else "NOT_EXTRACTED",
                "expected_value": want.get("normalized"), "actual_value": got.normalized_value if got else None,
                "status_ok": bool(got and got.validation_status == want["status"]),
                "exact_ok": bool(got and got.validation_status == want["status"]
                                 and (want["status"] != "VALID" or got.normalized_value == want.get("normalized"))),
            })
        rows.append({"document": name, "field": "(document type)", "scored": scored,
                     "expected_status": exp["detected_document_type"], "actual_status": doc_type,
                     "expected_value": None, "actual_value": None,
                     "status_ok": doc_type == exp["detected_document_type"],
                     "exact_ok": doc_type == exp["detected_document_type"]})

    scored_rows = [r for r in rows if r["scored"] and r["field"] != "(document type)"]
    type_rows = [r for r in rows if r["scored"] and r["field"] == "(document type)"]
    # Missing-field detection: positive class = expected ABSENT.
    tp = sum(r["expected_status"] == "ABSENT" and r["actual_status"] == "ABSENT" for r in scored_rows)
    fp = sum(r["expected_status"] != "ABSENT" and r["actual_status"] == "ABSENT" for r in scored_rows)
    fn = sum(r["expected_status"] == "ABSENT" and r["actual_status"] != "ABSENT" for r in scored_rows)
    # Field extraction precision/recall over values expected VALID.
    valid_exp = [r for r in scored_rows if r["expected_status"] == "VALID"]
    valid_got = [r for r in scored_rows if r["actual_status"] == "VALID"]
    correct_valid = sum(r["exact_ok"] for r in valid_exp)

    sets = {s["procedure_code"]: s for s in PA_REQUIREMENT_SETS}
    scenario_rows = []
    for sc in manifest["scenarios"]:
        docs = []
        for name in sc["documents"]:
            doc_type, results = extracted[name]
            doc_id = uuid.uuid4()
            docs.append(rules.DocumentEvidence(doc_id, name, doc_type, {
                r.field_name: rules.FieldEvidence(uuid.uuid4(), doc_id, name, r.field_name, r.validation_status,
                                                  r.normalized_value, r.raw_value, r.source_page) for r in results}))
        expected = dict(sc["expected"])
        scored = ocr_ok or not sc.get("needs_ocr")
        if not ocr_ok and sc.get("expected_without_ocr"):
            expected.update(sc["expected_without_ocr"])  # documented expected degradation without OCR
            scored = True
        statuses = []
        for req in sets[sc["procedure_code"]]["requirements"]:
            got = rules.evaluate(rules.Requirement(req["requirement_code"], req["rule_type"], req["rule_params"]), docs)
            statuses.append(got.item_status)
            scenario_rows.append({"scenario": sc["name"], "requirement": req["requirement_code"], "scored": scored,
                                  "expected": expected[req["requirement_code"]], "actual": got.item_status,
                                  "ok": got.item_status == expected[req["requirement_code"]],
                                  "explanation": got.explanation})
        scenario_rows.append({"scenario": sc["name"], "requirement": "(overall)", "scored": scored,
                              "expected": sc["readiness_status"] if (ocr_ok or not sc.get("expected_without_ocr"))
                              else rules.overall(list(expected.values())),
                              "actual": rules.overall(statuses), "ok": None, "explanation": ""})
        scenario_rows[-1]["ok"] = scenario_rows[-1]["expected"] == scenario_rows[-1]["actual"]

    items = [r for r in scenario_rows if r["scored"] and r["requirement"] != "(overall)"]
    overall_rows = [r for r in scenario_rows if r["scored"] and r["requirement"] == "(overall)"]
    per_status = {}
    for status in (rules.SATISFIED, rules.MISSING, rules.UNREADABLE, rules.MANUAL):
        exp = [r for r in items if r["expected"] == status]
        per_status[status] = (sum(r["ok"] for r in exp), len(exp))

    summary = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "ocr_engine": ocr.name, "ocr_available": ocr_ok,
        "documents": len(manifest["documents"]), "scenarios": len(manifest["scenarios"]),
        "document_type_accuracy": [sum(r["exact_ok"] for r in type_rows), len(type_rows)],
        "field_status_accuracy": [sum(r["status_ok"] for r in scored_rows), len(scored_rows)],
        "field_exact_match": [sum(r["exact_ok"] for r in scored_rows), len(scored_rows)],
        "valid_field_precision": [sum(r["exact_ok"] for r in valid_got if r["expected_status"] == "VALID"),
                                  len(valid_got)],
        "valid_field_recall": [correct_valid, len(valid_exp)],
        "missing_detection_precision": [tp, tp + fp], "missing_detection_recall": [tp, tp + fn],
        "checklist_item_accuracy": [sum(r["ok"] for r in items), len(items)],
        "overall_status_accuracy": [sum(r["ok"] for r in overall_rows), len(overall_rows)],
        "per_status": per_status,
    }
    unscored = sorted({r["document"] for r in rows if not r["scored"]})
    md = [
        "# Document AI evaluation (synthetic corpus v1.0)", "",
        f"- Run: {summary['run_at']} · documents: {summary['documents']} · scenarios: {summary['scenarios']}",
        f"- OCR engine: `{ocr.name}` · available: **{ocr_ok}**", "",
        "## Extraction (documents scored: " + str(len(type_rows)) + ")", "", "| Metric | Result |", "|---|---|",
        f"| Document type accuracy | {pct(*summary['document_type_accuracy'])} |",
        f"| Field validation-status accuracy | {pct(*summary['field_status_accuracy'])} |",
        f"| Field exact match (status + normalized value) | {pct(*summary['field_exact_match'])} |",
        f"| VALID-field precision | {pct(*summary['valid_field_precision'])} |",
        f"| VALID-field recall | {pct(*summary['valid_field_recall'])} |",
        f"| Missing-field (ABSENT) detection precision | {pct(*summary['missing_detection_precision'])} |",
        f"| Missing-field (ABSENT) detection recall | {pct(*summary['missing_detection_recall'])} |", "",
        "## Readiness checklist", "", "| Metric | Result |", "|---|---|",
        f"| Checklist item status accuracy | {pct(*summary['checklist_item_accuracy'])} |",
        f"| Overall readiness status accuracy | {pct(*summary['overall_status_accuracy'])} |",
        *[f"| Expected {s} classified correctly | {pct(*v)} |" for s, v in per_status.items()], "",
        "## Not scored (need OCR, engine unavailable)" if unscored else "## All documents scored", "",
        *[f"- `{d}`: observed type {extracted[d][0]}, field statuses "
          f"{sorted({r.validation_status for r in extracted[d][1]}) or ['(none)']}" for d in unscored], "",
        "## Processing time (local CPU)", "", "| Document | Bytes | Pages | ms |", "|---|---|---|---|",
        *[f"| {t['document']} | {t['bytes']} | {t['pages']} | {t['ms']} |" for t in timings], "",
        "## Mismatches", "", "| Where | Expected | Actual |", "|---|---|---|",
        *[f"| {r['document']} · {r['field']} | {r['expected_status']} {r['expected_value'] or ''} | "
          f"{r['actual_status']} {r['actual_value'] or ''} |" for r in rows if r["scored"] and not r["exact_ok"]],
        *[f"| {r['scenario']} · {r['requirement']} | {r['expected']} | {r['actual']} |"
          for r in scenario_rows if r["scored"] and not r["ok"]],
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "document_eval_v1.json").write_text(json.dumps(
        {"summary": summary, "fields": rows, "checklist": scenario_rows, "timings": timings}, indent=2),
        encoding="utf-8")
    (RESULTS / "document_eval_v1.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(run())
