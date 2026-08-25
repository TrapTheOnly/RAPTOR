from io import BytesIO

from app.integrations.reporting.report_pdf_layout import raptor_lockup_path
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf


def test_raptor_lockup_asset_ships_with_the_backend():
    path = raptor_lockup_path()
    assert path.is_file()
    assert path.stat().st_size > 1000


def test_every_report_page_embeds_the_raptor_lockup():
    template_definition = {
        "version": 1,
        "branding": {
            "company_name": "Acme Security",
            "primary_color": "#0B5CAD",
            "accent_color": "#1E293B",
            "logo_url": "",
        },
        "placeholders": {"report_title": "Penetration Testing Report"},
        "blocks": [
            {"type": "cover", "title": "{{placeholders.report_title}}", "subtitle": "", "show_logo": False},
            {"type": "page_break"},
            {"type": "text", "title": "Scope", "content": "Short body so the report has a second page."},
        ],
    }
    record_data = {
        "name": "api.example.com",
        "ip_address": "192.168.0.2",
        "source": "Internal",
        "application_name": "RAPTOR",
        "status": "In Progress",
        "tested_by": "tester1",
        "open_ports": "443",
        "vulnerabilities": "[]",
        "checklist_states": "{}",
        "description": "",
        "notes": "",
        "vulnerability_fixed": 0,
    }

    pdf_bytes = render_pentest_report_pdf(
        record_data,
        template_definition,
        checklist_templates=[],
        image_fetcher=lambda _filename: BytesIO(),
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.count(b"/Subtype /Image") >= 1
    assert pdf_bytes.count(b"/XObject") >= 2
    assert b"/Width 1254" in pdf_bytes
    assert b"/Height 1254" in pdf_bytes
    assert raptor_lockup_path().read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
