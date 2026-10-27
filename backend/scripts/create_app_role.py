"""Creates (or updates) a least-privilege application role for a database (SEC-17): it can read and write
rows but cannot change the schema; migrations run with the owner/migrator role instead.

    python -m scripts.create_app_role --role ihsa_app --database ihsa_dev [--password ...]

Run with an administrative DATABASE_URL (e.g. the local development cluster). Idempotent."""

from __future__ import annotations

import argparse
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.config import get_settings

_IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", default="ihsa_app")
    parser.add_argument("--database", default=None, help="defaults to the database in DATABASE_URL")
    parser.add_argument("--password", default=None, help="optional; omit for local trust authentication")
    args = parser.parse_args()
    if not _IDENT.match(args.role):
        raise SystemExit("invalid role name")
    url = make_url(get_settings().sqlalchemy_url.render_as_string(hide_password=False))
    database = args.database or url.database
    if not _IDENT.match(database):
        raise SystemExit("invalid database name")
    engine = create_engine(url.set(database=database), isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        exists = conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": args.role})
        verb = "ALTER" if exists else "CREATE"
        conn.execute(text(f'{verb} ROLE "{args.role}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'))
        if args.password:
            conn.execute(text(f'ALTER ROLE "{args.role}" PASSWORD :p'), {"p": args.password})
        for stmt in (
            f'GRANT CONNECT ON DATABASE "{database}" TO "{args.role}"',
            f'GRANT USAGE ON SCHEMA public TO "{args.role}"',
            f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{args.role}"',
            f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "{args.role}"',
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES '
            f'TO "{args.role}"',
            f'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO "{args.role}"',
        ):
            conn.execute(text(stmt))
    print(f"role {args.role}: {verb.lower()}d with DML-only privileges on {database}")


if __name__ == "__main__":
    main()
