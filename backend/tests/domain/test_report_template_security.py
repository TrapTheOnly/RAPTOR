import json

from app.domain.offsec.shared import normalize_report_template_payload
from app.integrations.reporting.report_pdf_model import replace_inline_markdown
from app.services.offsec import offsec_templates


def _base_report_template_payload():
    return {
        "key": "template_security",
        "name": "Template Security",
        "description": "",
        "enabled": True,
        "template": {
            "version": 1,
            "branding": {
                "company_name": "Acme Security",
                "primary_color": "#0B5CAD",
                "accent_color": "#1E293B",
                "logo_url": "",
            },
            "placeholders": {
                "report_title": "Penetration Testing Report",
                "report_subtitle": "Comprehensive assessment",
            },
            "blocks": [
                {
                    "type": "cover",
                    "title": "{{report_title}}",
                    "subtitle": "{{report_subtitle}}",
                    "show_logo": True,
                }
            ],
        },
    }


def _png_bytes():
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
        + b"\x90wS\xde"
    )


class DummyUpload:
    def __init__(self, filename, payload):
        self.filename = filename
        self._payload = payload

    def read(self, *args, **kwargs):
        if args:
            max_len = int(args[0])
            return self._payload[:max_len]
        return self._payload


class DummyCursor:
    def __init__(self, row=None):
        self._row = row

    def execute(self, query, params=None):
        return self

    def fetchone(self):
        return self._row


def test_normalize_report_template_rejects_external_logo_url():
    payload = _base_report_template_payload()
    payload["template"]["branding"]["logo_url"] = "https://evil.example/logo.png"

    normalized, error = normalize_report_template_payload(payload)

    assert error is None
    parsed = json.loads(normalized["template_json"])
    assert parsed["branding"]["logo_url"] == ""


def test_normalize_report_template_accepts_internal_logo_url():
    payload = _base_report_template_payload()
    payload["template"]["branding"]["logo_url"] = (
        "https://portal.local/pentest/images/abcdef1234567890abcdef1234567890.png"
    )

    normalized, error = normalize_report_template_payload(payload)

    assert error is None
    parsed = json.loads(normalized["template_json"])
    assert parsed["branding"]["logo_url"] == "/pentest/images/abcdef1234567890abcdef1234567890.png"


def test_replace_inline_markdown_rejects_unsafe_link_schemes():
    rendered = replace_inline_markdown("[click](javascript:alert(1))")

    assert "<a href=" not in rendered
    assert "click" in rendered


def test_replace_inline_markdown_covers_italic_strike_and_code():
    rendered = replace_inline_markdown("Use *weak* and ~~old~~ plus `id` and __heavy__.")
    assert "<i>weak</i>" in rendered
    assert "<strike>old</strike>" in rendered
    assert "Courier" in rendered
    assert "<b>heavy</b>" in rendered
    assert replace_inline_markdown("host_name stays") == "host_name stays"


def test_validate_report_logo_file_allows_png():
    file_data, error = offsec_templates._validate_report_logo_file(DummyUpload("logo.png", _png_bytes()))

    assert error is None
    assert file_data.startswith(b"\x89PNG\r\n\x1a\n")


def test_validate_report_logo_file_rejects_non_png():
    file_data, error = offsec_templates._validate_report_logo_file(
        DummyUpload("logo.jpg", b"\xff\xd8\xff\xe0not-a-png")
    )

    assert file_data is None
    assert error == "Only PNG logo files are allowed."


def test_prepare_report_template_logo_for_create_rejects_logo_asset_id():
    template_definition = {
        "branding": {"logo_asset_id": 123, "logo_url": "/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"},
        "blocks": [{"type": "cover"}],
    }

    prepared, error = offsec_templates.prepare_report_template_logo_for_create(template_definition)

    assert prepared is None
    assert error == "Save template first, then upload/select a logo for it."


def test_bind_report_template_logo_for_template_rejects_foreign_asset():
    template_definition = {
        "branding": {"logo_asset_id": 77, "logo_url": ""},
        "blocks": [{"type": "cover"}],
    }
    cursor = DummyCursor(row=None)

    bound, error = offsec_templates.bind_report_template_logo_for_template(cursor, 10, template_definition)

    assert bound is None
    assert error == "Invalid logo asset for this report template."


def test_bind_report_template_logo_for_template_sets_internal_logo_url():
    template_definition = {
        "branding": {"logo_asset_id": 7, "logo_url": ""},
        "blocks": [{"type": "cover"}],
    }
    cursor = DummyCursor(row={"file_path": "abcdef1234567890abcdef1234567890.png"})

    bound, error = offsec_templates.bind_report_template_logo_for_template(cursor, 5, template_definition)

    assert error is None
    assert bound["branding"]["logo_asset_id"] == 7
    assert bound["branding"]["logo_url"] == "/pentest/images/abcdef1234567890abcdef1234567890.png"
