from app.integrations.reporting.report_pdf_blocks import append_story_block
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
from app.integrations.reporting.report_pdf_model import (
    IMAGE_REFERENCE_PATTERN,
    MARKDOWN_IMAGE_PATTERN,
    build_report_model,
    build_service_name,
    replace_inline_markdown,
    resolve_placeholders,
    severity_from_score,
    to_float,
    to_int,
)


def render_pentest_report_pdf(
    record_data,
    template_definition,
    checklist_templates=None,
    image_fetcher=None,
):
    """Build a polished PDF report from pentest data and template definition."""
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
            PageBreak,
            Paragraph,
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

    model = build_report_model(record_data or {}, checklist_templates or [])
    context = model["context"]
    flat_context = dict(model["flat_context"])

    placeholders = template_definition.get("placeholders")
    if isinstance(placeholders, dict):
        resolved = {}
        for key, value in placeholders.items():
            resolved[key] = resolve_placeholders(value, flat_context) if isinstance(value, str) else value
            flat_context[str(key)] = "" if resolved[key] is None else str(resolved[key])
            flat_context[f"placeholders.{key}"] = flat_context[str(key)]
        context["placeholders"] = resolved

    branding = template_definition.get("branding") if isinstance(template_definition.get("branding"), dict) else {}
    primary_color = branding.get("primary_color", "#0B5CAD")
    accent_color = branding.get("accent_color", "#1E293B")
    logo_url = str(branding.get("logo_url", "") or "").strip()
    company_name = str(branding.get("company_name", "Security Operations") or "Security Operations")

    primary = safe_color(primary_color, "#0B5CAD", colors)
    accent = safe_color(accent_color, "#1E293B", colors)
    muted = colors.HexColor("#64748B")
    text_primary = colors.HexColor("#111827")
    border_color = colors.HexColor("#CBD5E1")
    surface_light = colors.HexColor("#F8FAFC")
    severity_color_hex = {
        "Critical": "#991B1B",
        "High": "#B45309",
        "Medium": "#0E7490",
        "Low": "#166534",
        "Informational": "#475569",
    }
    severity_colors = {key: colors.HexColor(value) for key, value in severity_color_hex.items()}

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportSectionTitle",
            parent=styles["Heading2"],
            fontSize=14.5,
            leading=18,
            textColor=accent,
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
            name="ReportMuted",
            parent=styles["BodyText"],
            fontSize=9.1,
            leading=12.4,
            textColor=muted,
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
            textColor=accent,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverCompany",
            parent=styles["BodyText"],
            fontSize=14,
            leading=18,
            alignment=TA_CENTER,
            textColor=accent,
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
            textColor=accent,
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
            textColor=accent,
        )
    )

    def resolve(value):
        return resolve_placeholders(value, flat_context)

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

    def table_with_style_fn(rows, col_widths):
        return table_with_style(
            rows,
            col_widths,
            Table,
            TableStyle,
            accent,
            border_color,
            surface_light,
            colors,
        )

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

    def build_bar_chart_fn(data):
        return build_bar_chart(data, to_int, primary, colors, Drawing, VerticalBarChart)

    def build_pie_chart_fn(data):
        return build_pie_chart(data, to_int, primary, colors, Drawing, Pie)

    draw_cover_page = make_draw_cover_page(A4, mm, primary, accent, company_name, colors)
    draw_body_page = make_draw_body_page(A4, mm, surface_light, border_color, muted, resolve, context, company_name)

    story = []

    for raw_block in blocks:
        append_story_block(
            story,
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
