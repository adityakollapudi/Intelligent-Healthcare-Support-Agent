"""Retention cleanup job (NFR-021). Run: python -m scripts.cleanup_expired [--dry-run]
Schedule it daily (Windows Task Scheduler, cron, or a container job). See app/services/retention_service.py."""

import argparse
import json
from dataclasses import asdict

from app.db.session import get_session_factory
from app.documents.storage import get_storage
from app.services import retention_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete data whose retention period has passed.")
    parser.add_argument("--dry-run", action="store_true", help="report what would be deleted; change nothing")
    args = parser.parse_args()
    with get_session_factory()() as db:
        report = retention_service.run(db, get_storage(), dry_run=args.dry_run)
    print(json.dumps(asdict(report), indent=2))


if __name__ == "__main__":
    main()
