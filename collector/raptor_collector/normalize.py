"""FQDN helpers for collector-side zone normalization."""


def normalize_fqdn(name: str, origin: str = "") -> str:
    raw_name = str(name or "").strip()
    raw_origin = str(origin or "").strip().rstrip(".").lower()
    if not raw_name or raw_name in ("@", "."):
        return raw_origin

    is_absolute = raw_name.endswith(".")
    normalized = raw_name.rstrip(".").lower()
    if not normalized:
        return raw_origin
    if is_absolute or not raw_origin:
        return normalized
    if normalized == raw_origin or normalized.endswith("." + raw_origin):
        return normalized
    return f"{normalized}.{raw_origin}"
