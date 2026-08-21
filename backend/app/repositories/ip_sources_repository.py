from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.config import DB_PATH
from app.integrations.db.connection import ROW_AS_DICT, get_db_connection

PROVIDER_IP_SOURCE_NAMES = {
    "cloudflare": "Cloudflare",
    "route53": "AWS",
    "azure": "Azure",
    "gcp": "Google Cloud",
    "alidns": "Alibaba Cloud",
}


def fetch_ip_sources(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    conn = get_db_connection(db_path)
    conn.row_factory = ROW_AS_DICT
    c = conn.cursor()
    c.execute("SELECT id, source_name, ip_address FROM ip_sources")
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def add_ip_source(source_name: str, ip_address: str, db_path: str = DB_PATH) -> int:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO ip_sources (source_name, ip_address)
        VALUES (?, ?)
        """,
        (source_name, ip_address),
    )
    conn.commit()

    c.execute(
        """
        UPDATE records
        SET source = ?,
            status = 'updated',
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE ip_address = ?
        """,
        (source_name, ip_address),
    )
    updated_count = c.rowcount

    conn.commit()
    conn.close()
    return updated_count


def ip_source_name_for_dns_type(source_type: Optional[str]) -> Optional[str]:
    kind = str(source_type or "").strip().lower()
    return PROVIDER_IP_SOURCE_NAMES.get(kind)


def ensure_ip_sources(
    source_name: str,
    ip_addresses: Iterable[str],
    db_path: str = DB_PATH,
) -> int:
    """Create or move IP mappings into ``source_name``. Does not rewrite ``records``."""
    label = str(source_name or "").strip()
    ips = sorted({str(ip or "").strip() for ip in ip_addresses if str(ip or "").strip()})
    if not label or not ips:
        return 0

    conn = get_db_connection(db_path)
    c = conn.cursor()
    written = 0
    for ip_address in ips:
        c.execute(
            """
            INSERT INTO ip_sources (source_name, ip_address)
            VALUES (?, ?)
            ON CONFLICT (ip_address) DO UPDATE SET source_name = EXCLUDED.source_name
            """,
            (label, ip_address),
        )
        written += 1
    conn.commit()
    conn.close()
    return written


def delete_ip_source(ip_address: str, db_path: str = DB_PATH) -> Optional[Tuple[str, int]]:
    conn = get_db_connection(db_path)
    c = conn.cursor()

    c.execute("SELECT source_name FROM ip_sources WHERE ip_address = ?", (ip_address,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None

    source_name = row[0]
    c.execute("DELETE FROM ip_sources WHERE ip_address = ?", (ip_address,))
    conn.commit()

    c.execute(
        """
        UPDATE records
        SET source = 'Other',
            status = 'updated',
            last_modification_date = (NOW() + INTERVAL '4 hours')
        WHERE ip_address = ?
        """,
        (ip_address,),
    )
    updated_count = c.rowcount
    conn.commit()
    conn.close()

    return source_name, updated_count
