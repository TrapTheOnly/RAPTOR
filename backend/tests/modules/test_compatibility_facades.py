import app.services.offsec as offsec
from app.domain.offsec.shared import normalize_ports
from app.integrations.reporting.report_pdf_model import replace_inline_markdown, to_int
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf
from app.services.offsec.offsec_generated_reports import generate_report
from app.services.offsec.offsec_templates import get_report_templates


def test_offsec_exports_are_wired():
    assert callable(offsec.get_pentest_data)
    assert callable(offsec.create_or_update_pentest_data)
    assert offsec.generate_report is generate_report
    assert offsec.get_report_templates is get_report_templates
    assert normalize_ports([80, "443", "bad", 443]) == [80, 443]


def test_report_pdf_exports_are_wired():
    assert callable(render_pentest_report_pdf)
    assert to_int("5") == 5
    assert replace_inline_markdown("**x**") == "<b>x</b>"
