"""FQDN normalization for ingest. Absolute names keep their labels."""


def normalize_fqdn(name: str, origin: str = "") -> str:
    """Return a lowercase FQDN without a trailing dot.

    Absolute names (trailing dot) are not concatenated with ``origin``.
    ``@`` and empty owner names resolve to ``origin``.
    """
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
