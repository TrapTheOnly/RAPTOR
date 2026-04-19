import os
from typing import Any, Iterable, Optional

try:  # psycopg v3
    import psycopg  # type: ignore[import-not-found]
    from psycopg.rows import dict_row  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    psycopg = None
    dict_row = None

try:  # psycopg2 fallback
    import psycopg2  # type: ignore[import-not-found]
    from psycopg2.extras import RealDictCursor  # type: ignore[import-not-found]
except Exception:  # pragma: no cover
    psycopg2 = None
    RealDictCursor = None

ROW_AS_DICT = object()

if psycopg is not None:
    IntegrityError = psycopg.IntegrityError
elif psycopg2 is not None:
    IntegrityError = psycopg2.IntegrityError
else:  # pragma: no cover
    class IntegrityError(Exception):
        pass


def _resolve_database_url(database_url: Optional[str]) -> str:
    direct_url = str(database_url or "").strip()
    if direct_url.startswith(("postgres://", "postgresql://")):
        return direct_url

    env_url = str(os.getenv("DATABASE_URL") or "").strip()
    if env_url:
        return env_url
    raise RuntimeError("DATABASE_URL is required. SQLite runtime mode is not supported.")


def _normalize_params(params: Any) -> Any:
    if params is None:
        return ()
    if isinstance(params, list):
        return tuple(params)
    return params


def _convert_qmark_placeholders(query: str) -> str:
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


class DatabaseCursor:
    def __init__(self, cursor):
        self._cursor = cursor

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def execute(self, query: str, params: Any = None):
        self._cursor.execute(_convert_qmark_placeholders(query), _normalize_params(params))
        return self

    def executemany(self, query: str, seq_of_params: Iterable[Any]):
        params = [_normalize_params(item) for item in seq_of_params]
        self._cursor.executemany(_convert_qmark_placeholders(query), params)
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def close(self):
        return self._cursor.close()

    def __iter__(self):
        return iter(self._cursor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


class DatabaseConnection:
    def __init__(self, connection):
        self._connection = connection
        self.row_factory = None

    def cursor(self):
        if psycopg is not None and self.row_factory is ROW_AS_DICT:
            return DatabaseCursor(self._connection.cursor(row_factory=dict_row))
        if psycopg2 is not None and self.row_factory is ROW_AS_DICT:
            return DatabaseCursor(self._connection.cursor(cursor_factory=RealDictCursor))
        return DatabaseCursor(self._connection.cursor())

    def commit(self):
        return self._connection.commit()

    def rollback(self):
        return self._connection.rollback()

    def close(self):
        return self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False


def get_db_connection(database_url: Optional[str] = None) -> DatabaseConnection:
    resolved_url = _resolve_database_url(database_url)
    if psycopg is not None:
        return DatabaseConnection(psycopg.connect(resolved_url))
    if psycopg2 is not None:
        return DatabaseConnection(psycopg2.connect(resolved_url))
    raise RuntimeError(
        "PostgreSQL backend requires a PostgreSQL driver "
        "(psycopg[binary] or psycopg2-binary). Install requirements and retry."
    )


def get_table_columns(cursor: DatabaseCursor, table_name: str) -> set[str]:
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = ?
        """,
        (str(table_name).strip().lower(),),
    )
    rows = cursor.fetchall()
    columns = set()
    for row in rows:
        if isinstance(row, dict):
            columns.add(str(row.get("column_name") or "").strip().lower())
        elif row:
            columns.add(str(row[0] or "").strip().lower())
    return columns


__all__ = [
    "DatabaseConnection",
    "DatabaseCursor",
    "IntegrityError",
    "ROW_AS_DICT",
    "get_db_connection",
    "get_table_columns",
]
