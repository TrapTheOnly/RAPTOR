import re
import sqlite3

try:
    import psycopg2
except Exception:  # pragma: no cover - optional dependency for environments missing postgres libs
    psycopg2 = None


class SQLiteCompatRow(dict):
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class SQLiteCompatConnection:
    def __init__(self, database_url):
        self._conn = psycopg2.connect(database_url)
        self.row_factory = None
        self._column_cache = {}

    def cursor(self):
        return SQLiteCompatCursor(self, self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def execute(self, query, params=None):
        cur = self.cursor()
        return cur.execute(query, params)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        return False

    def table_has_column(self, table_name, column_name):
        key = table_name.lower()
        if key not in self._column_cache:
            with self._conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = current_schema()
                      AND table_name = %s
                    """,
                    (key,),
                )
                self._column_cache[key] = {row[0] for row in cur.fetchall()}
        return column_name.lower() in self._column_cache[key]


class SQLiteCompatCursor:
    def __init__(self, connection, cursor):
        self._connection = connection
        self._cursor = cursor
        self._fake_rows = None
        self._fake_index = 0
        self._fake_description = None
        self._lastrowid = None

    @property
    def description(self):
        if self._fake_rows is not None:
            return self._fake_description
        return self._cursor.description

    @property
    def rowcount(self):
        if self._fake_rows is not None:
            return len(self._fake_rows)
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._lastrowid

    def close(self):
        return self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def execute(self, query, params=None):
        self._reset_fake_result()
        self._lastrowid = None

        pragma_table_info = re.match(r"^\s*PRAGMA\s+table_info\(([^)]+)\)", query, re.IGNORECASE)
        if pragma_table_info:
            table = pragma_table_info.group(1).strip().strip("'\"`[]").lower()
            self._handle_pragma_table_info(table)
            return self

        transformed_query = _transform_sqlite_query(query)
        transformed_query = _convert_qmark_placeholders(transformed_query)
        transformed_params = _normalize_params(params)
        transformed_query, capture_lastrowid = _maybe_add_returning_id(
            transformed_query,
            self._connection,
        )

        try:
            self._cursor.execute(transformed_query, transformed_params)
        except Exception as exc:
            try:
                self._connection.rollback()
            except Exception:
                pass
            _raise_as_sqlite_error(exc)

        if capture_lastrowid:
            inserted = self._cursor.fetchone()
            if inserted:
                self._lastrowid = inserted[0]
        return self

    def executemany(self, query, seq_of_params):
        self._reset_fake_result()
        self._lastrowid = None

        transformed_query = _transform_sqlite_query(query)
        transformed_query = _convert_qmark_placeholders(transformed_query)
        params_list = [_normalize_params(p) for p in seq_of_params]

        try:
            self._cursor.executemany(transformed_query, params_list)
        except Exception as exc:
            try:
                self._connection.rollback()
            except Exception:
                pass
            _raise_as_sqlite_error(exc)
        return self

    def fetchone(self):
        if self._fake_rows is not None:
            if self._fake_index >= len(self._fake_rows):
                return None
            row = self._fake_rows[self._fake_index]
            self._fake_index += 1
            return self._convert_row(row, self._fake_description)

        row = self._cursor.fetchone()
        if row is None:
            return None
        return self._convert_row(row, self._cursor.description)

    def fetchall(self):
        if self._fake_rows is not None:
            rows = self._fake_rows[self._fake_index :]
            self._fake_index = len(self._fake_rows)
            return [self._convert_row(row, self._fake_description) for row in rows]

        rows = self._cursor.fetchall()
        return [self._convert_row(row, self._cursor.description) for row in rows]

    def __iter__(self):
        while True:
            row = self.fetchone()
            if row is None:
                break
            yield row

    def _convert_row(self, row, description):
        if self._connection.row_factory is sqlite3.Row and description:
            columns = [meta[0] for meta in description]
            return SQLiteCompatRow(columns, row)
        return row

    def _reset_fake_result(self):
        self._fake_rows = None
        self._fake_index = 0
        self._fake_description = None

    def _handle_pragma_table_info(self, table_name):
        with self._connection._conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.ordinal_position - 1 AS cid,
                    c.column_name,
                    c.data_type,
                    CASE WHEN c.is_nullable = 'NO' THEN 1 ELSE 0 END AS notnull,
                    c.column_default,
                    CASE WHEN pk.column_name IS NULL THEN 0 ELSE 1 END AS pk
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT kcu.table_schema, kcu.table_name, kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                     AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) pk
                  ON pk.table_schema = c.table_schema
                 AND pk.table_name = c.table_name
                 AND pk.column_name = c.column_name
                WHERE c.table_schema = current_schema()
                  AND c.table_name = %s
                ORDER BY c.ordinal_position
                """,
                (table_name,),
            )
            rows = cur.fetchall()

        self._fake_rows = rows
        self._fake_description = [
            ("cid", None, None, None, None, None, None),
            ("name", None, None, None, None, None, None),
            ("type", None, None, None, None, None, None),
            ("notnull", None, None, None, None, None, None),
            ("dflt_value", None, None, None, None, None, None),
            ("pk", None, None, None, None, None, None),
        ]


def normalize_params(params):
    if params is None:
        return ()
    if isinstance(params, list):
        return tuple(params)
    return params


def _normalize_params(params):
    return normalize_params(params)


def _raise_as_sqlite_error(exc):
    if psycopg2 is None:
        raise exc
    mapping = (
        (psycopg2.IntegrityError, sqlite3.IntegrityError),
        (psycopg2.OperationalError, sqlite3.OperationalError),
        (psycopg2.ProgrammingError, sqlite3.ProgrammingError),
        (psycopg2.DataError, sqlite3.DataError),
        (psycopg2.InterfaceError, sqlite3.InterfaceError),
        (psycopg2.DatabaseError, sqlite3.DatabaseError),
    )
    for source_exc, target_exc in mapping:
        if isinstance(exc, source_exc):
            raise target_exc(str(exc)) from exc
    raise exc


def _append_on_conflict_do_nothing(query):
    stripped = query.rstrip()
    has_semicolon = stripped.endswith(";")
    if has_semicolon:
        stripped = stripped[:-1].rstrip()
    stripped = f"{stripped} ON CONFLICT DO NOTHING"
    if has_semicolon:
        stripped += ";"
    return stripped


def _transform_sqlite_query(query):
    transformed = query

    transformed = re.sub(r"\bBLOB\b", "BYTEA", transformed, flags=re.IGNORECASE)

    transformed = re.sub(
        r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b",
        "SERIAL PRIMARY KEY",
        transformed,
        flags=re.IGNORECASE,
    )
    transformed = re.sub(r"\bAUTOINCREMENT\b", "", transformed, flags=re.IGNORECASE)
    transformed = re.sub(r"\bCOLLATE\s+NOCASE\b", "", transformed, flags=re.IGNORECASE)

    transformed = re.sub(
        r"datetime\(\s*'now'\s*,\s*'\+4 hours'\s*\)",
        "(NOW() + INTERVAL '4 hours')",
        transformed,
        flags=re.IGNORECASE,
    )
    transformed = re.sub(
        r"datetime\(\s*'now'\s*\)",
        "NOW()",
        transformed,
        flags=re.IGNORECASE,
    )

    transformed, count = re.subn(
        r"\bINSERT\s+OR\s+IGNORE\s+INTO\b",
        "INSERT INTO",
        transformed,
        flags=re.IGNORECASE,
    )
    if count > 0 and "ON CONFLICT" not in transformed.upper():
        transformed = _append_on_conflict_do_nothing(transformed)

    return transformed


def _convert_qmark_placeholders(query):
    output = []
    in_single = False
    in_double = False
    index = 0

    while index < len(query):
        char = query[index]

        if char == "'" and not in_double:
            if in_single and index + 1 < len(query) and query[index + 1] == "'":
                output.append("''")
                index += 2
                continue
            in_single = not in_single
            output.append(char)
            index += 1
            continue

        if char == '"' and not in_single:
            in_double = not in_double
            output.append(char)
            index += 1
            continue

        if char == "?" and not in_single and not in_double:
            output.append("%s")
        else:
            output.append(char)

        index += 1

    return "".join(output)


def _maybe_add_returning_id(query, connection):
    if not re.match(r"^\s*INSERT\s+INTO\s+", query, re.IGNORECASE):
        return query, False
    if re.search(r"\bRETURNING\b", query, re.IGNORECASE):
        return query, False

    table_match = re.match(
        r"^\s*INSERT\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)",
        query,
        re.IGNORECASE,
    )
    if not table_match:
        return query, False

    table_name = table_match.group(1).lower()
    if not connection.table_has_column(table_name, "id"):
        return query, False

    stripped = query.rstrip()
    has_semicolon = stripped.endswith(";")
    if has_semicolon:
        stripped = stripped[:-1].rstrip()
    stripped = f"{stripped} RETURNING id"
    if has_semicolon:
        stripped += ";"
    return stripped, True


__all__ = ["SQLiteCompatConnection", "SQLiteCompatCursor", "SQLiteCompatRow", "psycopg2"]
