#!/usr/bin/env python3
"""
Migrate RAPTOR data from SQLite to PostgreSQL.

Usage examples:
  python scripts/migrate_sqlite_to_postgres.py --sqlite-path backend/data/database.db --postgres-url "postgresql://raptor:raptor@localhost:5432/raptor" --truncate
  python scripts/migrate_sqlite_to_postgres.py --dry-run
"""

import argparse
import os
import re
import sqlite3
import sys
from collections import defaultdict

psycopg2 = None
execute_values = None
sql = None


def parse_args():
    parser = argparse.ArgumentParser(description="Migrate RAPTOR SQLite data into PostgreSQL.")
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
        "--truncate",
        action="store_true",
        help="Truncate destination tables before loading data.",
    )
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Create/ensure schema only. Do not copy table rows.",
    )
    parser.add_argument(
        "--data-only",
        action="store_true",
        help="Copy data only. Assume destination schema already exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions and exit.",
    )
    parser.add_argument(
        "--skip-if-marked",
        action="store_true",
        help="Skip migration when a marker key exists in destination app_meta.",
    )
    parser.add_argument(
        "--mark-key",
        default="sqlite_to_postgres_migrated_v1",
        help="Marker key in app_meta used to indicate migration already completed.",
    )
    parser.add_argument(
        "--allow-missing-sqlite",
        action="store_true",
        help="Exit successfully when source SQLite file does not exist.",
    )
    return parser.parse_args()


def ensure_inputs(args):
    if not os.path.exists(args.sqlite_path):
        if args.allow_missing_sqlite:
            return
        raise FileNotFoundError(f"SQLite file not found: {args.sqlite_path}")
    if not args.postgres_url and not args.dry_run:
        raise ValueError("PostgreSQL URL is required (--postgres-url or DATABASE_URL).")
    if args.schema_only and args.data_only:
        raise ValueError("Use either --schema-only or --data-only, not both.")


def ensure_postgres_libs():
    global psycopg2, execute_values, sql
    if psycopg2 is not None and execute_values is not None and sql is not None:
        return
    try:
        import psycopg2 as _psycopg2
        from psycopg2.extras import execute_values as _execute_values
        from psycopg2 import sql as _sql
    except Exception:
        print(
            "psycopg2 is required. Install backend requirements first "
            "(pip install -r backend/requirements.txt).",
            file=sys.stderr,
        )
        raise
    psycopg2 = _psycopg2
    execute_values = _execute_values
    sql = _sql


def load_sqlite_schema(sqlite_conn):
    cur = sqlite_conn.cursor()
    cur.execute(
        """
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    )
    tables = {}
    for name, create_sql in cur.fetchall():
        if not create_sql:
            continue
        tables[name] = create_sql
    return tables


def sqlite_row_count(sqlite_conn, table):
    cur = sqlite_conn.cursor()
    cur.execute(f'SELECT COUNT(*) FROM "{table}"')
    return int(cur.fetchone()[0])


def transform_create_table_sql(sql_text):
    result = sql_text.strip()

    # Keep explicit ids from SQLite and sync sequence afterwards.
    result = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "BIGINT PRIMARY KEY",
        result,
        flags=re.IGNORECASE,
    )
    result = re.sub(r"\bAUTOINCREMENT\b", "", result, flags=re.IGNORECASE)
    result = re.sub(r"\bBLOB\b", "BYTEA", result, flags=re.IGNORECASE)

    if re.match(r"^\s*CREATE\s+TABLE\s+", result, flags=re.IGNORECASE):
        result = re.sub(
            r"^\s*CREATE\s+TABLE\s+",
            "CREATE TABLE IF NOT EXISTS ",
            result,
            count=1,
            flags=re.IGNORECASE,
        )

    return result


def extract_dependencies(create_sql, known_tables):
    deps = set()
    for ref in re.findall(r"REFERENCES\s+([A-Za-z_][A-Za-z0-9_]*)", create_sql, flags=re.IGNORECASE):
        if ref in known_tables:
            deps.add(ref)
    return deps


def topo_sort_tables(table_sql_map):
    deps = {
        table: extract_dependencies(create_sql, set(table_sql_map.keys()))
        for table, create_sql in table_sql_map.items()
    }
    ready = sorted([t for t, d in deps.items() if not d])
    ordered = []

    while ready:
        table = ready.pop(0)
        ordered.append(table)
        for other in list(deps.keys()):
            if table in deps[other]:
                deps[other].remove(table)
                if not deps[other] and other not in ordered and other not in ready:
                    ready.append(other)
        ready.sort()

    remaining = [t for t in table_sql_map.keys() if t not in ordered]
    if remaining:
        # Fallback for unusual cycles: append in deterministic order.
        ordered.extend(sorted(remaining))
    return ordered


def table_exists(pg_conn, table_name):
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


def migration_marker_exists(pg_conn, mark_key):
    ensure_app_meta_table(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM app_meta WHERE key = %s", (mark_key,))
        return cur.fetchone() is not None


def set_migration_marker(pg_conn, mark_key):
    ensure_app_meta_table(pg_conn)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO app_meta (key, value)
            VALUES (%s, NOW()::text)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """,
            (mark_key,),
        )
    pg_conn.commit()


def get_column_types(pg_conn, table_name):
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
            ORDER BY ordinal_position
            """,
            (table_name,),
        )
        rows = cur.fetchall()
    return {name: (data_type, udt_name) for name, data_type, udt_name in rows}


def normalize_value_for_column(value, column_type):
    if value is None:
        return None
    if isinstance(value, bytes):
        _, udt_name = column_type
        if udt_name == "bytea":
            return value
        try:
            return value.decode("utf-8")
        except Exception:
            return value.decode("latin-1", errors="replace")
    return value


def create_schema(pg_conn, table_sql_map, ordered_tables):
    with pg_conn.cursor() as cur:
        for table in ordered_tables:
            statement = transform_create_table_sql(table_sql_map[table])
            cur.execute(statement)
    pg_conn.commit()


def truncate_tables(pg_conn, ordered_tables):
    with pg_conn.cursor() as cur:
        for table in reversed(ordered_tables):
            cur.execute(
                sql.SQL("TRUNCATE TABLE {} RESTART IDENTITY CASCADE").format(sql.Identifier(table))
            )
    pg_conn.commit()


def copy_table_data(sqlite_conn, pg_conn, table):
    sqlite_cur = sqlite_conn.cursor()
    sqlite_cur.execute(f'SELECT * FROM "{table}"')
    rows = sqlite_cur.fetchall()
    if not rows:
        return 0

    columns = [desc[0] for desc in sqlite_cur.description]
    column_types = get_column_types(pg_conn, table)

    normalized_rows = []
    for row in rows:
        normalized = []
        for idx, value in enumerate(row):
            column_name = columns[idx]
            normalized.append(
                normalize_value_for_column(value, column_types.get(column_name, ("text", "text")))
            )
        normalized_rows.append(tuple(normalized))

    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES %s").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns),
    )

    with pg_conn.cursor() as cur:
        execute_values(cur, insert_stmt, normalized_rows, page_size=1000)
    return len(normalized_rows)


def reset_id_sequences(pg_conn, ordered_tables):
    with pg_conn.cursor() as cur:
        for table in ordered_tables:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                      AND column_name = 'id'
                )
                """,
                (table,),
            )
            has_id = bool(cur.fetchone()[0])
            if not has_id:
                continue

            cur.execute(
                "SELECT pg_get_serial_sequence(%s, 'id')",
                (table,),
            )
            seq_name = cur.fetchone()[0]
            if not seq_name:
                continue

            cur.execute(sql.SQL("SELECT MAX(id) FROM {}").format(sql.Identifier(table)))
            max_id = cur.fetchone()[0]

            if max_id is None:
                cur.execute("SELECT setval(%s, 1, false)", (seq_name,))
            else:
                cur.execute("SELECT setval(%s, %s, true)", (seq_name, int(max_id)))

    pg_conn.commit()


def destination_table_counts(pg_conn, ordered_tables):
    counts = {}
    with pg_conn.cursor() as cur:
        for table in ordered_tables:
            if not table_exists(pg_conn, table):
                counts[table] = None
                continue
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table)))
            counts[table] = int(cur.fetchone()[0])
    return counts


def main():
    args = parse_args()
    ensure_inputs(args)
    if not os.path.exists(args.sqlite_path) and args.allow_missing_sqlite:
        print(f"SQLite source not found at {args.sqlite_path}. Nothing to migrate.")
        return

    sqlite_conn = sqlite3.connect(args.sqlite_path)
    try:
        table_sql_map = load_sqlite_schema(sqlite_conn)
        ordered_tables = topo_sort_tables(table_sql_map)
        source_counts = {table: sqlite_row_count(sqlite_conn, table) for table in ordered_tables}

        print("Source tables:")
        for table in ordered_tables:
            print(f"  - {table}: {source_counts[table]}")

        if args.dry_run:
            print("\nDry run only. No changes were made.")
            return

        ensure_postgres_libs()
        with psycopg2.connect(args.postgres_url) as pg_conn:
            if args.skip_if_marked and migration_marker_exists(pg_conn, args.mark_key):
                print(f"\nMarker '{args.mark_key}' exists. Skipping migration.")
                return

            if not args.data_only:
                print("\nCreating/ensuring schema...")
                create_schema(pg_conn, table_sql_map, ordered_tables)

            if args.truncate and not args.schema_only:
                print("Truncating destination tables...")
                truncate_tables(pg_conn, ordered_tables)

            copied = defaultdict(int)
            if not args.schema_only:
                print("Copying table rows...")
                for table in ordered_tables:
                    if not table_exists(pg_conn, table):
                        raise RuntimeError(
                            f"Destination table '{table}' does not exist. "
                            "Use without --data-only first."
                        )
                    copied[table] = copy_table_data(sqlite_conn, pg_conn, table)
                pg_conn.commit()
                reset_id_sequences(pg_conn, ordered_tables)

            dest_counts = destination_table_counts(pg_conn, ordered_tables)

            print("\nMigration summary:")
            for table in ordered_tables:
                src = source_counts[table]
                dst = dest_counts.get(table)
                copied_rows = copied.get(table, 0)
                print(f"  - {table}: source={src}, copied={copied_rows}, destination={dst}")

            if not args.schema_only:
                set_migration_marker(pg_conn, args.mark_key)
                print(f"\nSet migration marker: {args.mark_key}")

    finally:
        sqlite_conn.close()


if __name__ == "__main__":
    main()
