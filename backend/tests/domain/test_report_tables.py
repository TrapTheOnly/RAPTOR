from app.integrations.reporting.report_context import SEVERITY_CELL_HEX
from app.integrations.reporting.report_pdf_layout import table_with_style


class _Style:
    def __init__(self, name):
        self.name = name


class _Paragraph:
    def __init__(self, text, style):
        self.text = text
        self.style = style


class _Table:
    def __init__(self, rows, colWidths=None, hAlign=None):
        self.rows = rows
        self.col_widths = colWidths
        self.commands = []

    def setStyle(self, style):
        self.commands = list(style.commands)


class _TableStyle:
    def __init__(self, commands):
        self.commands = commands


class _Colors:
    white = "white"

    @staticmethod
    def HexColor(value):
        return value


HEADER = _Style("header")
BODY = _Style("body")


def test_table_with_style_wraps_plain_cells_so_values_can_break():
    table = table_with_style(
        [
            ["Field", "Value"],
            ["Prepared By", "samir.okonkwo, jordan.cho, lena.brooks, awadmin, marco.stein"],
        ],
        [55, 123],
        _Table,
        _TableStyle,
        "navy",
        "gray",
        "ice",
        _Colors,
        paragraph_class=_Paragraph,
        header_style=HEADER,
        body_style=BODY,
    )

    assert all(isinstance(cell, _Paragraph) for row in table.rows for cell in row)
    assert table.rows[1][1].text.startswith("samir.okonkwo")
    assert ("VALIGN", (0, 0), (-1, -1), "TOP") in table.commands


def test_table_with_style_keeps_existing_flowables_and_applies_severity_fills():
    severity = _Paragraph("<b>Critical</b>", BODY)
    table = table_with_style(
        [["#", "Finding", "Severity"], ["1", "SQLi", severity]],
        [14, 124, 40],
        _Table,
        _TableStyle,
        "navy",
        "gray",
        "ice",
        _Colors,
        paragraph_class=_Paragraph,
        header_style=HEADER,
        body_style=BODY,
        extra_commands=[("BACKGROUND", (2, 1), (2, 1), "#DC2626")],
    )

    assert table.rows[1][2] is severity
    assert isinstance(table.rows[1][1], _Paragraph)
    assert ("BACKGROUND", (2, 1), (2, 1), "#DC2626") in table.commands


def test_severity_cell_palette_is_red_orange_yellow_green_blue():
    assert SEVERITY_CELL_HEX["Critical"][0] == "#DC2626"
    assert SEVERITY_CELL_HEX["High"][0] == "#EA580C"
    assert SEVERITY_CELL_HEX["Medium"][0] == "#EAB308"
    assert SEVERITY_CELL_HEX["Low"][0] == "#16A34A"
    assert SEVERITY_CELL_HEX["Informational"][0] == "#2563EB"


def test_overview_and_toc_render_with_wrapping_tables():
    from app.integrations.reporting.report_context import sample_report_context
    from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf

    context = sample_report_context("owner_delivery")
    context["pentest"]["tested_by"] = (
        "samir.okonkwo, jordan.cho, lena.brooks, awadmin, marco.stein, "
        "Samir Okonkwo, Jordan Cho, Lena Brooks"
    )
    pdf_bytes = render_pentest_report_pdf(
        context,
        {
            "version": 1,
            "branding": {"company_name": "Acme", "primary_color": "#0B5CAD", "accent_color": "#1E293B"},
            "placeholders": {"report_title": "Report"},
            "blocks": [
                {"type": "engagement_overview", "title": "Overview"},
                {"type": "table_of_contents", "title": "Table of Contents"},
            ],
        },
        checklist_templates=[],
    )
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
