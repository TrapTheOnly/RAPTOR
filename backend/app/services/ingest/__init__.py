"""DNS ingest pipeline shared by bind_file sync and collector agents."""

from app.services.ingest.apply import apply_ingest_batch, project_a_records
from app.services.ingest.fqdn import normalize_fqdn
from app.services.ingest.models import ResourceRecord, ZoneSnapshot

__all__ = [
    "ResourceRecord",
    "ZoneSnapshot",
    "apply_ingest_batch",
    "normalize_fqdn",
    "project_a_records",
]
