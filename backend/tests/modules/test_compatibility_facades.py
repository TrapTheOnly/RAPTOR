from modules import offsec, report_pdf
from modules.offsec_generated_reports import generate_report
from modules.offsec_shared import normalize_ports
from modules.offsec_templates import get_report_templates
from modules.report_pdf_model import replace_inline_markdown, to_int
from modules.report_pdf_render import render_pentest_report_pdf


def test_offsec_facade_keeps_legacy_exports():
    assert callable(offsec.get_pentest_data)
    assert callable(offsec.create_or_update_pentest_data)
    assert offsec.generate_report is generate_report
    assert offsec.get_report_templates is get_report_templates
    assert offsec._normalize_ports is normalize_ports


def test_report_pdf_facade_keeps_legacy_exports():
    assert report_pdf.render_pentest_report_pdf is render_pentest_report_pdf
    assert report_pdf._to_int is to_int
    assert report_pdf._replace_inline_markdown is replace_inline_markdown
