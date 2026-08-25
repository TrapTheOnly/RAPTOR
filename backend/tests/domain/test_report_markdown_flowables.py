import re

from app.integrations.reporting.report_pdf_layout import markdown_to_flowables


class _Style:
    def __init__(self, name):
        self.name = name


def _paragraph(text, style, **kwargs):
    return {
        "type": "paragraph",
        "text": text,
        "style": style.name,
        "bullet": kwargs.get("bulletText"),
    }


def _spacer(_w, h):
    return {"type": "spacer", "height": h}


def _preformatted(text, style):
    return {
        "type": "preformatted",
        "text": text,
        "style": style.name,
    }


def test_markdown_heading_levels_map_to_compact_report_styles():
    styles = {
        "ReportSectionTitle": _Style("ReportSectionTitle"),
        "ReportMarkdownH1": _Style("ReportMarkdownH1"),
        "ReportMarkdownH2": _Style("ReportMarkdownH2"),
        "ReportMarkdownH3": _Style("ReportMarkdownH3"),
        "ReportMarkdownH4": _Style("ReportMarkdownH4"),
        "ReportCodeLanguage": _Style("ReportCodeLanguage"),
        "ReportCodeBlock": _Style("ReportCodeBlock"),
        "ReportBody": _Style("ReportBody"),
        "ReportMuted": _Style("ReportMuted"),
        "ReportBullet": _Style("ReportBullet"),
    }
    raw_markdown = "\n".join(
        [
            "# Remediation",
            "## Exploitability",
            "### Validation Steps",
            "#### Analyst Notes",
            "##### Deep Detail",
            "Normal paragraph content",
            "- bullet point",
        ]
    )

    flowables = markdown_to_flowables(
        raw_markdown,
        styles,
        lambda value: value,
        re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
        lambda *_args, **_kwargs: None,
        _paragraph,
        _spacer,
    )

    paragraph_styles = [item["style"] for item in flowables if item.get("type") == "paragraph"]
    assert paragraph_styles == [
        "ReportMarkdownH1",
        "ReportMarkdownH2",
        "ReportMarkdownH3",
        "ReportMarkdownH4",
        "ReportMarkdownH4",
        "ReportBody",
        "ReportBullet",
    ]


def test_markdown_code_fence_renders_code_block_and_language_label():
    styles = {
        "ReportSectionTitle": _Style("ReportSectionTitle"),
        "ReportMarkdownH1": _Style("ReportMarkdownH1"),
        "ReportMarkdownH2": _Style("ReportMarkdownH2"),
        "ReportMarkdownH3": _Style("ReportMarkdownH3"),
        "ReportMarkdownH4": _Style("ReportMarkdownH4"),
        "ReportCodeLanguage": _Style("ReportCodeLanguage"),
        "ReportCodeBlock": _Style("ReportCodeBlock"),
        "ReportBody": _Style("ReportBody"),
        "ReportMuted": _Style("ReportMuted"),
        "ReportBullet": _Style("ReportBullet"),
    }
    raw_markdown = "```php\n<?php echo 'ok';\n```\n"

    flowables = markdown_to_flowables(
        raw_markdown,
        styles,
        lambda value: value,
        re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
        lambda *_args, **_kwargs: None,
        _paragraph,
        _spacer,
        preformatted=_preformatted,
    )

    paragraph_items = [item for item in flowables if item.get("type") == "paragraph"]
    preformatted_items = [item for item in flowables if item.get("type") == "preformatted"]
    assert paragraph_items[0]["style"] == "ReportCodeLanguage"
    assert "Code (php)" in paragraph_items[0]["text"]
    assert len(preformatted_items) == 1
    assert preformatted_items[0]["style"] == "ReportCodeBlock"
    assert "<?php echo 'ok';" in preformatted_items[0]["text"]


def test_markdown_image_requests_full_text_width_scaling():
    styles = {
        "ReportSectionTitle": _Style("ReportSectionTitle"),
        "ReportMarkdownH1": _Style("ReportMarkdownH1"),
        "ReportMarkdownH2": _Style("ReportMarkdownH2"),
        "ReportMarkdownH3": _Style("ReportMarkdownH3"),
        "ReportMarkdownH4": _Style("ReportMarkdownH4"),
        "ReportCodeLanguage": _Style("ReportCodeLanguage"),
        "ReportCodeBlock": _Style("ReportCodeBlock"),
        "ReportBody": _Style("ReportBody"),
        "ReportMuted": _Style("ReportMuted"),
        "ReportBullet": _Style("ReportBullet"),
    }
    calls = []

    def _image_fn(_url, **kwargs):
        calls.append(kwargs)
        return {"type": "image"}

    markdown_to_flowables(
        "![evidence](/pentest/images/abcdef1234567890abcdef1234567890.png)",
        styles,
        lambda value: value,
        re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
        _image_fn,
        _paragraph,
        _spacer,
        markdown_image_target_width_mm=178,
        markdown_image_max_height_mm=250,
    )

    assert len(calls) == 1
    assert calls[0]["centered"] is True
    assert calls[0]["target_width_mm"] == 178
    assert calls[0]["max_width_mm"] == 178
    assert calls[0]["max_height_mm"] == 250


def _base_styles():
    return {
        "ReportSectionTitle": _Style("ReportSectionTitle"),
        "ReportMarkdownH1": _Style("ReportMarkdownH1"),
        "ReportMarkdownH2": _Style("ReportMarkdownH2"),
        "ReportMarkdownH3": _Style("ReportMarkdownH3"),
        "ReportMarkdownH4": _Style("ReportMarkdownH4"),
        "ReportCodeLanguage": _Style("ReportCodeLanguage"),
        "ReportCodeBlock": _Style("ReportCodeBlock"),
        "ReportBody": _Style("ReportBody"),
        "ReportMuted": _Style("ReportMuted"),
        "ReportBullet": _Style("ReportBullet"),
        "ReportQuote": _Style("ReportQuote"),
    }


def test_markdown_lists_quotes_tables_rules_and_tasks():
    captured = {}

    def table_fn(rows):
        captured["table"] = rows
        return {"type": "table", "rows": rows}

    def quote_fn(body):
        captured["quote"] = body
        return {"type": "quote", "text": body}

    def rule_fn():
        captured["rule"] = True
        return {"type": "rule"}

    raw_markdown = "\n".join(
        [
            "1. First step",
            "2. Second step",
            "+ extra bullet",
            "- [x] done task",
            "- [ ] open task",
            "> quoted proof",
            "> continues here",
            "",
            "| Host | Status |",
            "| --- | --- |",
            "| api.example | Open |",
            "",
            "---",
        ]
    )
    flowables = markdown_to_flowables(
        raw_markdown,
        _base_styles(),
        lambda value: value,
        re.compile(r"!\[([^\]]*)\]\(([^)]+)\)"),
        lambda *_args, **_kwargs: None,
        _paragraph,
        _spacer,
        table_fn=table_fn,
        quote_fn=quote_fn,
        rule_fn=rule_fn,
    )
    bullets = [item for item in flowables if item.get("type") == "paragraph" and item.get("style") == "ReportBullet"]
    assert [item["bullet"] for item in bullets] == ["1.", "2.", "•", "☑", "☐"]
    assert captured["quote"] == "quoted proof\ncontinues here"
    assert captured["table"][0] == ["Host", "Status"]
    assert captured["table"][1] == ["api.example", "Open"]
    assert captured["rule"] is True
    assert any(item.get("type") == "rule" for item in flowables)
