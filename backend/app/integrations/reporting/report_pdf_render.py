from app.integrations.reporting.report_pdf_blocks import (
    CHART_PAGE_IDS,
    append_story_block,
    ensure_report_blocks,
)


def _chart_id(block):
    if not isinstance(block, dict):
        return ""
    if str(block.get("type") or "").strip().lower() != "chart":
        return ""
    return str(block.get("chart") or "").strip().lower()
from app.integrations.reporting.report_pdf_layout import (
    build_bar_chart,
    build_pie_chart,
    get_embedded_image,
    make_draw_body_page,
    make_draw_cover_page,
    markdown_to_flowables,
    metric_tiles,
    safe_color,
    section_title,
    table_with_style,
)
from app.integrations.reporting.report_context import (
    SEVERITY_PRINT_HEX,
    UnknownTokenError,
    lint_template_tokens,
    resolve_placeholders_strict,
    token_flat_context,
)
from app.integrations.reporting.report_pdf_model import (
    IMAGE_REFERENCE_PATTERN,
    MARKDOWN_IMAGE_PATTERN,
    build_report_model,
    build_service_name,
    replace_inline_markdown,
    severity_from_score,
    to_float,
    to_int,
)
from app.repositories.users_repository import get_display_names


def render_pentest_report_pdf(
    context,
    template_definition,
    checklist_templates=None,
    image_fetcher=None,
    generated_by=None,
):
    """Build a PDF report from ReportContext (or a legacy host payload) and a template."""
    try:
        from io import BytesIO

        from reportlab.graphics.charts.barcharts import VerticalBarChart
        from reportlab.graphics.charts.piecharts import Pie
        from reportlab.graphics.shapes import Drawing
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            Image as RLImage,
            KeepTogether,
            PageBreak,
            Paragraph,
            Preformatted,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception as e:
        raise RuntimeError(f"Report generation dependency missing: {e}") from e

    if not isinstance(template_definition, dict):
        raise ValueError("Template definition must be a JSON object.")

    blocks = template_definition.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Template must include a non-empty 'blocks' array.")

    token_error = lint_template_tokens(template_definition)
    if token_error:
        raise UnknownTokenError(token_error)

    model = build_report_model(context or {}, checklist_templates or [], generated_by=generated_by)

    usernames_to_resolve = set()
    model_generated_by = model["context"].get("generated_by", "")
    model_tested_by = model["context"].get("pentest", {}).get("tested_by", "")
    if model_generated_by and model_generated_by != "Unassigned":
        usernames_to_resolve.add(model_generated_by)
    if model_tested_by and model_tested_by != "Unassigned":
        usernames_to_resolve.add(model_tested_by)
    for collab in model.get("collaborator_usernames", []):
        if collab:
            usernames_to_resolve.add(collab)

    display_names = {}
    if usernames_to_resolve:
        try:
            display_names = get_display_names(list(usernames_to_resolve)) or {}
        except Exception:
            display_names = {}

    if model_generated_by in display_names:
        model["context"]["generated_by"] = display_names[model_generated_by]
    if model_tested_by in display_names:
        model["context"]["pentest"]["tested_by"] = display_names[model_tested_by]
    if model.get("collaborator_usernames"):
        model["collaborator_usernames"] = [display_names.get(u, u) for u in model["collaborator_usernames"]]
        model["context"]["pentest"]["collaborators"] = ", ".join(model["collaborator_usernames"])

    rebuilt_flat = token_flat_context(model["context"])
    model["flat_context"] = rebuilt_flat

    context = model["context"]
    flat_context = dict(model["flat_context"])

    placeholders = template_definition.get("placeholders")
    if isinstance(placeholders, dict):
        resolved = {}
        for key, value in placeholders.items():
            resolved[key] = (
                resolve_placeholders_strict(value, flat_context) if isinstance(value, str) else value
            )
            flat_context[str(key)] = "" if resolved[key] is None else str(resolved[key])
            flat_context[f"placeholders.{key}"] = flat_context[str(key)]
        context["placeholders"] = resolved

    branding = template_definition.get("branding") if isinstance(template_definition.get("branding"), dict) else {}
    primary_color = branding.get("primary_color", "#067A8A")
    accent_color = branding.get("accent_color", "#1E293B")
    logo_url = str(branding.get("logo_url", "") or "").strip()
    company_name = str(branding.get("company_name", "Security Operations") or "Security Operations")

    primary = safe_color(primary_color, "#067A8A", colors)
    accent = safe_color(accent_color, "#1E293B", colors)
    muted = colors.HexColor("#64748B")
    text_primary = colors.HexColor("#111827")
    border_color = colors.HexColor("#CBD5E1")
    surface_light = colors.HexColor("#F8FAFC")
    severity_color_hex = dict(SEVERITY_PRINT_HEX)
    severity_colors = {key: colors.HexColor(value) for key, value in severity_color_hex.items()}
    content_width_mm = 178

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportSectionTitle",
            parent=styles["Heading2"],
            fontSize=14.5,
            leading=18,
            textColor=primary,
            spaceBefore=0,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontSize=10.2,
            leading=14.3,
            textColor=text_primary,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMarkdownH1",
            parent=styles["ReportBody"],
            fontName="Helvetica-Bold",
            fontSize=12.4,
            leading=16,
            textColor=primary,
            spaceBefore=2,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMarkdownH2",
            parent=styles["ReportBody"],
            fontName="Helvetica-Bold",
            fontSize=11.6,
            leading=14.8,
            textColor=primary,
            spaceBefore=1,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMarkdownH3",
            parent=styles["ReportBody"],
            fontName="Helvetica-Bold",
            fontSize=10.9,
            leading=13.8,
            textColor=text_primary,
            spaceBefore=1,
            spaceAfter=0.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMarkdownH4",
            parent=styles["ReportBody"],
            fontName="Helvetica-Bold",
            fontSize=10.4,
            leading=13.2,
            textColor=text_primary,
            spaceBefore=0.5,
            spaceAfter=0.5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMuted",
            parent=styles["BodyText"],
            fontSize=9.1,
            leading=12.4,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCodeLanguage",
            parent=styles["ReportMuted"],
            fontSize=8.2,
            leading=10,
            textColor=muted,
            spaceBefore=1,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCodeBlock",
            parent=styles["ReportBody"],
            fontName="Courier",
            fontSize=8.8,
            leading=11.4,
            textColor=text_primary,
            backColor=colors.HexColor("#F1F5F9"),
            borderColor=border_color,
            borderWidth=0.5,
            borderPadding=6,
            leftIndent=2,
            rightIndent=2,
            spaceBefore=0,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMutedCenter",
            parent=styles["ReportMuted"],
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverTitle",
            parent=styles["Heading1"],
            fontSize=32,
            leading=36,
            alignment=TA_CENTER,
            textColor=primary,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverCompany",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=primary,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverSub",
            parent=styles["BodyText"],
            fontSize=12.8,
            leading=18,
            alignment=TA_CENTER,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverMetaLabel",
            parent=styles["BodyText"],
            fontSize=9.2,
            leading=12,
            textColor=muted,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverMetaValue",
            parent=styles["BodyText"],
            fontSize=10.3,
            leading=13.5,
            textColor=text_primary,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMetricLabel",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11.3,
            textColor=muted,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMetricValue",
            parent=styles["BodyText"],
            fontSize=16,
            leading=18,
            textColor=primary,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBullet",
            parent=styles["BodyText"],
            fontSize=10,
            leading=13.5,
            textColor=text_primary,
            leftIndent=12,
            bulletIndent=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportFindingTitle",
            parent=styles["BodyText"],
            fontSize=11.2,
            leading=14.5,
            textColor=primary,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportQuote",
            parent=styles["ReportBody"],
            fontName="Helvetica-Oblique",
            textColor=muted,
            leftIndent=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTableHeader",
            parent=styles["ReportBody"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.white,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTableCell",
            parent=styles["ReportBody"],
            fontSize=9,
            leading=12,
            textColor=text_primary,
            wordWrap="CJK",
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportTableCellCenter",
            parent=styles["ReportTableCell"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        )
    )

    def resolve(value):
        return resolve_placeholders_strict(value, flat_context)

    def get_embedded_image_fn(
        url,
        max_width_mm=170,
        max_height_mm=90,
        target_width_mm=None,
        centered=False,
    ):
        return get_embedded_image(
            url,
            image_fetcher,
            RLImage,
            mm,
            IMAGE_REFERENCE_PATTERN,
            max_width_mm=max_width_mm,
            max_height_mm=max_height_mm,
            target_width_mm=target_width_mm,
            centered=centered,
        )

    def markdown_to_flowables_fn(raw_text, empty_message="No content provided."):
        return markdown_to_flowables(
            raw_text,
            styles,
            replace_inline_markdown,
            MARKDOWN_IMAGE_PATTERN,
            get_embedded_image_fn,
            Paragraph,
            Spacer,
            empty_message=empty_message,
            preformatted=Preformatted,
            markdown_image_target_width_mm=content_width_mm,
            markdown_image_max_height_mm=250,
            table_fn=markdown_table_fn,
            quote_fn=markdown_quote_fn,
            rule_fn=markdown_rule_fn,
        )

    def section_title_fn(text):
        return section_title(
            text,
            resolve,
            replace_inline_markdown,
            Paragraph,
            styles,
            Table,
            TableStyle,
            mm,
            surface_light,
            border_color,
            primary,
        )

    def table_with_style_fn(rows, col_widths, extra_commands=None):
        return table_with_style(
            rows,
            col_widths,
            Table,
            TableStyle,
            primary,
            border_color,
            surface_light,
            colors,
            paragraph_class=Paragraph,
            header_style=styles["ReportTableHeader"],
            body_style=styles["ReportTableCell"],
            extra_commands=extra_commands,
        )

    def markdown_table_fn(rows):
        if not rows:
            return Spacer(1, 1)
        cols = max((len(row) for row in rows), default=1) or 1
        normalized = [list(row) + [""] * (cols - len(row)) for row in rows]
        col_widths = [(content_width_mm / cols) * mm] * cols
        header_style = styles["ReportTableHeader"]
        para_rows = []
        for row_index, row in enumerate(normalized):
            cell_style = header_style if row_index == 0 else styles["ReportBody"]
            para_rows.append([Paragraph(replace_inline_markdown(cell), cell_style) for cell in row])
        return table_with_style_fn(para_rows, col_widths)

    def markdown_quote_fn(body):
        inner = Paragraph(replace_inline_markdown(body), styles["ReportQuote"])
        card = Table([[inner]], colWidths=[content_width_mm * mm], hAlign="LEFT")
        card.setStyle(
            TableStyle(
                [
                    ("LINEBEFORE", (0, 0), (0, 0), 3, primary),
                    ("BACKGROUND", (0, 0), (-1, -1), surface_light),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        return card

    def markdown_rule_fn():
        rule = Table([[""]], colWidths=[content_width_mm * mm], hAlign="LEFT")
        rule.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 0.7, border_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return rule

    def metric_tiles_fn(items, columns=3):
        return metric_tiles(
            items,
            columns,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
            styles,
            mm,
            border_color,
            colors,
            replace_inline_markdown,
        )

    def build_bar_chart_fn(data, bar_colors=None):
        return build_bar_chart(
            data,
            to_int,
            primary,
            colors,
            Drawing,
            VerticalBarChart,
            bar_colors=bar_colors,
        )

    def build_pie_chart_fn(data):
        return build_pie_chart(data, to_int, primary, colors, Drawing, Pie)

    draw_cover_page = make_draw_cover_page(
        A4, mm, primary, accent, company_name, colors, context=context, branding=branding
    )
    draw_body_page = make_draw_body_page(
        A4, mm, surface_light, border_color, muted, resolve, context, company_name, branding=branding
    )

    story = []
    flow_blocks = ensure_report_blocks(blocks)

    def append_one(target, raw_block):
        append_story_block(
            target,
            raw_block,
            resolve=resolve,
            context=context,
            model=model,
            styles=styles,
            mm=mm,
            PageBreak=PageBreak,
            Spacer=Spacer,
            Paragraph=Paragraph,
            Table=Table,
            TableStyle=TableStyle,
            colors=colors,
            border_color=border_color,
            severity_color_hex=severity_color_hex,
            severity_colors=severity_colors,
            company_name=company_name,
            logo_url=logo_url,
            get_embedded_image_fn=get_embedded_image_fn,
            section_title_fn=section_title_fn,
            table_with_style_fn=table_with_style_fn,
            metric_tiles_fn=metric_tiles_fn,
            markdown_to_flowables_fn=markdown_to_flowables_fn,
            build_bar_chart_fn=build_bar_chart_fn,
            build_pie_chart_fn=build_pie_chart_fn,
            build_service_name=build_service_name,
            replace_inline_markdown=replace_inline_markdown,
            to_float=to_float,
            severity_from_score=severity_from_score,
        )

    index = 0
    while index < len(flow_blocks):
        raw_block = flow_blocks[index]
        nxt = flow_blocks[index + 1] if index + 1 < len(flow_blocks) else None
        chart = _chart_id(raw_block)
        next_chart = _chart_id(nxt)
        if chart in CHART_PAGE_IDS and next_chart in CHART_PAGE_IDS:
            inner = []
            append_one(inner, raw_block)
            append_one(inner, nxt)
            story.append(PageBreak())
            story.append(KeepTogether(inner))
            index += 2
            continue
        block_type = str((raw_block or {}).get("type") or "").strip().lower()
        if chart in CHART_PAGE_IDS or block_type == "vulnerabilities":
            story.append(PageBreak())
        append_one(story, raw_block)
        index += 1

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=str(resolve("{{placeholders.report_title}}") or "Pentest Report"),
        author=company_name,
    )
    doc.build(story, onFirstPage=draw_cover_page, onLaterPages=draw_body_page)
    pdf_buffer.seek(0)
    return pdf_buffer.read()


__all__ = ["render_pentest_report_pdf"]
