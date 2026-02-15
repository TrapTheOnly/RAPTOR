#!/usr/bin/env python3
"""
Verify PostgreSQL migration state for RAPTOR.

Checks:
1) Destination PostgreSQL is reachable.
2) Migration marker exists (optionally only when SQLite source exists).
3) Row-count checks between SQLite source and PostgreSQL destination.

The default count mode is "ge" (destination >= source), which is safe for
ongoing deployments after initial cutover.
"""

import argparse
import os
import sqlite3
import sys

try:
    import psycopg2
    from psycopg2 import sql
except Exception:
    print(
        "psycopg2 is required. Install backend requirements first "
        "(pip install -r backend/requirements.txt).",
        file=sys.stderr,
    )
    raise


def parse_args():
    parser = argparse.ArgumentParser(description="Verify SQLite->PostgreSQL migration state.")
    parser.add_argument(
        "--sqlite-path",
        default="backend/data/database.db",
        help="Path to source SQLite database file.",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("DATABASE_URL", ""),
        help="PostgreSQL DSN/URL. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--mark-key",
        default="sqlite_to_postgres_migrated_v1",
        help="Migration marker key in Postgres app_meta.",
    )
    parser.add_argument(
        "--count-mode",
        choices=["exact", "ge"],
        default="ge",
        help="Row-count check mode. 'exact' requires equality, 'ge' requires destination >= source.",
    )
    parser.add_argument(
        "--allow-missing-sqlite",
        action="store_true",
        help="Skip source row-count checks if SQLite file does not exist.",
    )
    parser.add_argument(
        "--require-marker",
        action="store_true",
        help="Always require migration marker key in destination app_meta.",
    )
    parser.add_argument(
        "--require-marker-if-sqlite",
        action="store_true",
        help="Require migration marker only when SQLite source file exists.",
    )
    return parser.parse_args()


def load_source_counts(sqlite_path):
    conn = sqlite3.connect(sqlite_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        )
        tables = [row[0] for row in cur.fetchall()]
        counts = {}
        for table in tables:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            counts[table] = int(cur.fetchone()[0])
        return counts
    finally:
        conn.close()


def pg_table_exists(pg_conn, table_name):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = current_schema()
                  AND table_name = %s
            )
            """,
            (table_name,),
        )
        return bool(cur.fetchone()[0])


def pg_table_count(pg_conn, table_name):
    with pg_conn.cursor() as cur:
        cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
        return int(cur.fetchone()[0])


def ensure_app_meta_table(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS app_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
    pg_conn.commit()


def marker_exists(pg_conn, mark_key):
    ensure_app_meta_table(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM app_meta WHERE key = %s", (mark_key,))
        return cur.fetchone() is not None


def main():
    args = parse_args()

    if not args.postgres_url:
        raise ValueError("PostgreSQL URL is required (--postgres-url or DATABASE_URL).")

    sqlite_exists = os.path.exists(args.sqlite_path)
    if not sqlite_exists and not args.allow_missing_sqlite:
        raise FileNotFoundError(f"SQLite file not found: {args.sqlite_path}")

    source_counts = {}
    if sqlite_exists:
        source_counts = load_source_counts(args.sqlite_path)
        print("Source table counts:")
        for table, count in source_counts.items():
            print(f"  - {table}: {count}")
    else:
        print(f"SQLite source not found at {args.sqlite_path}. Skipping source count checks.")

    failures = []

    with psycopg2.connect(args.postgres_url) as pg_conn:
        has_marker = marker_exists(pg_conn, args.mark_key)
        print(f"Migration marker '{args.mark_key}': {'present' if has_marker else 'missing'}")

        marker_required = args.require_marker or (args.require_marker_if_sqlite and sqlite_exists)
        if marker_required and not has_marker:
            failures.append(f"Missing required migration marker: {args.mark_key}")

        if sqlite_exists:
            print("Destination table counts:")
            for table, src_count in source_counts.items():
                if not pg_table_exists(pg_conn, table):
                    failures.append(f"Destination table missing: {table}")
                    print(f"  - {table}: destination=missing, source={src_count}")
                    continue
                dst_count = pg_table_count(pg_conn, table)
                print(f"  - {table}: destination={dst_count}, source={src_count}")

                if args.count_mode == "exact":
                    if dst_count != src_count:
                        failures.append(
                            f"Count mismatch for {table}: destination={dst_count}, source={src_count}"
                        )
                else:  # ge
                    if dst_count < src_count:
                        failures.append(
                            f"Count regression for {table}: destination={dst_count}, source={src_count}"
                        )

    if failures:
        print("\nVerification FAILED:")
        for item in failures:
            print(f"  - {item}")
        sys.exit(1)

    print("\nVerification PASSED.")


if __name__ == "__main__":
    main()

