"""DNS ingest pipeline shared by collector agents and cloud DNS pulls."""

from app.services.ingest.fqdn import normalize_fqdn
from app.services.ingest.models import ResourceRecord, ZoneSnapshot

__all__ = [
    "ResourceRecord",
    "ZoneSnapshot",
    "apply_ingest_batch",
    "normalize_fqdn",
    "project_a_records",
]


def __getattr__(name):
    if name in ("apply_ingest_batch", "project_a_records"):
        from app.services.ingest.apply import apply_ingest_batch, project_a_records

        exports = {
            "apply_ingest_batch": apply_ingest_batch,
            "project_a_records": project_a_records,
        }
        return exports[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
