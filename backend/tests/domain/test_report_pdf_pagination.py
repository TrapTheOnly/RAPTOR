import json
from io import BytesIO

from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf


def _image_fetcher(_filename):
    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (4, 4), (220, 38, 38)).save(buffer, format="PNG")
    buffer.seek(0)
    return buffer


def test_render_report_with_long_vulnerability_markdown_images_does_not_crash():
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
            {"type": "vulnerabilities", "title": "Findings", "include_descriptions": True},
        ],
    }

    image_ref = "/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png"
    repeated_lines = []
    for i in range(220):
        repeated_lines.append(f"Evidence line {i + 1}: observation details")
        if i % 12 == 0:
            repeated_lines.append(f"![evidence]({image_ref})")

    vulnerabilities = [
        {
            "categoryName": "Blind SQL Injection",
            "baseScore": 9.1,
            "description": "\n".join(repeated_lines),
        }
    ]
    record_data = {
        "name": "api.example.com",
        "ip_address": "192.168.0.2",
        "source": "Internal",
        "application_name": "RAPTOR",
        "status": "In Progress",
        "tested_by": "tester1",
        "open_ports": "443,8443",
        "vulnerabilities": json.dumps(vulnerabilities),
        "checklist_states": json.dumps({}),
        "description": "",
        "notes": "",
        "vulnerability_fixed": 0,
    }

    pdf_bytes = render_pentest_report_pdf(
        record_data,
        template_definition,
        checklist_templates=[],
        image_fetcher=_image_fetcher,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
