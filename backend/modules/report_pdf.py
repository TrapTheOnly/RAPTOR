"""Compatibility facade for PDF reporting utilities."""

from app.integrations.reporting.report_pdf_model import (
    IMAGE_REFERENCE_PATTERN,
    MARKDOWN_IMAGE_PATTERN,
    build_report_model as _build_report_model,
    build_service_name as _build_service_name,
    flatten as _flatten,
    parse_open_ports as _parse_open_ports,
    replace_inline_markdown as _replace_inline_markdown,
    resolve_placeholders as _resolve_placeholders,
    safe_json_load as _safe_json_load,
    severity_from_score as _severity_from_score,
    to_float as _to_float,
    to_int as _to_int,
)
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf

__all__ = [
    "IMAGE_REFERENCE_PATTERN",
    "MARKDOWN_IMAGE_PATTERN",
    "_build_report_model",
    "_build_service_name",
    "_flatten",
    "_parse_open_ports",
    "_replace_inline_markdown",
    "_resolve_placeholders",
    "_safe_json_load",
    "_severity_from_score",
    "_to_float",
    "_to_int",
    "render_pentest_report_pdf",
]
