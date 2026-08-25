import re
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^```([a-zA-Z0-9_+-]*)\s*$")
_UL_RE = re.compile(r"^(\s*)([-*+])\s+(?:\[([ xX])\]\s+)?(.*)$")
_OL_RE = re.compile(r"^(\s*)(\d+)[.)]\s+(?:\[([ xX])\]\s+)?(.*)$")
_BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")

RAPTOR_LOCKUP_HEIGHT_MM = 15
RAPTOR_LOCKUP_LEFT_MM = 12
RAPTOR_LOCKUP_BOTTOM_MM = 7


def raptor_lockup_path():
    return Path(__file__).resolve().parents[2] / "assets" / "brand" / "raptor-lockup-print.png"


def draw_raptor_footer_lockup(canvas, mm):
    """Stamp the RAPTOR icon+wordmark lockup at the bottom-left of a page."""
    path = raptor_lockup_path()
    if not path.is_file():
        return RAPTOR_LOCKUP_LEFT_MM * mm
    from reportlab.lib.utils import ImageReader

    image = ImageReader(str(path))
    intrinsic_width, intrinsic_height = image.getSize()
    height = RAPTOR_LOCKUP_HEIGHT_MM * mm
    width = height * (float(intrinsic_width) / max(float(intrinsic_height), 1.0))
    left = RAPTOR_LOCKUP_LEFT_MM * mm
    bottom = RAPTOR_LOCKUP_BOTTOM_MM * mm
    canvas.drawImage(
        image,
        left,
        bottom,
        width=width,
        height=height,
        mask="auto",
        preserveAspectRatio=True,
        anchor="sw",
    )
    return left + width + (3.5 * mm)


def safe_color(value, fallback, colors):
    try:
        return colors.HexColor(value)
    except Exception:
        return colors.HexColor(fallback)


def get_embedded_image(
    url,
    image_fetcher,
    rl_image_class,
    mm,
    image_reference_pattern,
    max_width_mm=170,
    max_height_mm=90,
    target_width_mm=None,
    centered=False,
):
    if not url or not image_fetcher:
        return None
    match = image_reference_pattern.fullmatch(str(url).strip())
    if not match:
        return None
    filename = match.group(1).lower()
    try:
        file_obj = image_fetcher(filename)
        image = rl_image_class(file_obj)
        if target_width_mm is not None:
            target_width = max(float(target_width_mm), 1.0) * mm
            if image.drawWidth > 0:
                ratio = target_width / float(image.drawWidth)
                image.drawWidth = target_width
                image.drawHeight *= ratio
        max_width = max_width_mm * mm
        max_height = max_height_mm * mm
        if image.drawWidth > max_width:
            ratio = max_width / float(image.drawWidth)
            image.drawWidth *= ratio
            image.drawHeight *= ratio
        if image.drawHeight > max_height:
            ratio = max_height / float(image.drawHeight)
            image.drawWidth *= ratio
            image.drawHeight *= ratio
        if centered:
            image.hAlign = "CENTER"
        return image
    except Exception:
        return None


def _is_horizontal_rule(line):
    compact = re.sub(r"\s+", "", str(line or "").strip())
    return bool(compact) and len(compact) >= 3 and compact == compact[0] * len(compact) and compact[0] in "-*_"


def _split_table_row(line):
    value = str(line or "").strip()
    if value.startswith("|"):
        value = value[1:]
    if value.endswith("|"):
        value = value[:-1]
    return [part.strip() for part in value.split("|")]


def _list_indent_level(spaces):
    expanded = str(spaces or "").replace("\t", "    ")
    return max(0, len(expanded) // 2)


def markdown_to_flowables(
    raw_text,
    styles,
    replace_inline_markdown,
    markdown_image_pattern,
    get_embedded_image_fn,
    paragraph,
    spacer,
    empty_message="No content provided.",
    preformatted=None,
    markdown_image_target_width_mm=None,
    markdown_image_max_height_mm=250,
    table_fn=None,
    quote_fn=None,
    rule_fn=None,
):
    text = str(raw_text or "")
    if not text.strip():
        return [paragraph(empty_message, styles["ReportMuted"])]

    heading_style_map = {
        1: "ReportMarkdownH1",
        2: "ReportMarkdownH2",
        3: "ReportMarkdownH3",
        4: "ReportMarkdownH4",
    }

    def append_code_block(flowables_list, code_lines, code_language):
        if not code_lines:
            return
        code_text = "\n".join(code_lines).rstrip("\n")
        if not code_text.strip():
            return

        if code_language:
            language_style = styles["ReportCodeLanguage"] if "ReportCodeLanguage" in styles else styles["ReportMuted"]
            flowables_list.append(
                paragraph(
                    f"Code ({replace_inline_markdown(code_language.lower())})",
                    language_style,
                )
            )
            flowables_list.append(spacer(1, 2))

        if preformatted and "ReportCodeBlock" in styles:
            flowables_list.append(preformatted(code_text, styles["ReportCodeBlock"]))
        else:
            fallback_text = code_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            flowables_list.append(paragraph(f"<font name='Courier'>{fallback_text}</font>", styles["ReportBody"]))
        flowables_list.append(spacer(1, 5))

    def emit_images(flowables_list, raw_line):
        for match in markdown_image_pattern.finditer(raw_line):
            image_url = match.group(2)
            image_width_target = markdown_image_target_width_mm if markdown_image_target_width_mm else 170
            image = get_embedded_image_fn(
                image_url,
                max_width_mm=image_width_target,
                max_height_mm=markdown_image_max_height_mm,
                target_width_mm=markdown_image_target_width_mm,
                centered=True,
            )
            if image:
                flowables_list.append(spacer(1, 6))
                flowables_list.append(image)
                flowables_list.append(spacer(1, 6))
            else:
                alt_text = match.group(1) or "image"
                flowables_list.append(
                    paragraph(f"[Image omitted: {replace_inline_markdown(alt_text)}]", styles["ReportMuted"])
                )

    def emit_text(flowables_list, raw_line, style_name, bullet=None, prefix=""):
        text_without_images = markdown_image_pattern.sub("", raw_line).strip()
        if prefix or text_without_images:
            kwargs = {"bulletText": bullet} if bullet else {}
            style = styles[style_name] if style_name in styles else styles["ReportBody"]
            body = prefix + (replace_inline_markdown(text_without_images) if text_without_images else "")
            flowables_list.append(paragraph(body, style, **kwargs))
        emit_images(flowables_list, raw_line)

    def is_list_line(raw_line):
        if _is_horizontal_rule(raw_line):
            return False
        return bool(_UL_RE.match(raw_line) or _OL_RE.match(raw_line))

    def is_table_start(source, index):
        current = source[index]
        if "|" not in current:
            return False
        if index + 1 >= len(source):
            return False
        return bool(_TABLE_SEP_RE.match(source[index + 1].strip()))

    def starts_block(raw_line, source=None, index=None):
        stripped = raw_line.strip()
        if not stripped:
            return True
        if _FENCE_RE.match(stripped):
            return True
        if _is_horizontal_rule(raw_line):
            return True
        if _HEADING_RE.match(stripped):
            return True
        if _BLOCKQUOTE_RE.match(raw_line):
            return True
        if is_list_line(raw_line):
            return True
        if source is not None and index is not None and is_table_start(source, index):
            return True
        return False

    lines = [line.rstrip() for line in text.splitlines()]
    flowables = []
    index = 0
    while index < len(lines):
        current = lines[index]
        fence_match = _FENCE_RE.match(current.strip())
        if fence_match:
            language = (fence_match.group(1) or "").strip()
            code_lines = []
            index += 1
            while index < len(lines) and not _FENCE_RE.match(lines[index].strip()):
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            append_code_block(flowables, code_lines, language)
            continue

        if not current.strip():
            flowables.append(spacer(1, 4))
            index += 1
            continue

        if _is_horizontal_rule(current):
            if rule_fn:
                flowables.append(rule_fn())
            else:
                flowables.append(spacer(1, 8))
            index += 1
            continue

        heading_match = _HEADING_RE.match(markdown_image_pattern.sub("", current).strip())
        if heading_match:
            heading_level = len(heading_match.group(1))
            style_name = heading_style_map.get(heading_level, "ReportMarkdownH4")
            emit_text(flowables, heading_match.group(2).strip(), style_name)
            emit_images(flowables, current)
            index += 1
            continue

        if is_table_start(lines, index):
            rows = [_split_table_row(current)]
            index += 2
            while index < len(lines) and "|" in lines[index] and lines[index].strip() and not _is_horizontal_rule(lines[index]):
                rows.append(_split_table_row(lines[index]))
                index += 1
            if table_fn:
                flowables.append(table_fn(rows))
                flowables.append(spacer(1, 6))
            else:
                for row in rows:
                    flowables.append(paragraph(replace_inline_markdown(" | ".join(row)), styles["ReportBody"]))
            continue

        quote_match = _BLOCKQUOTE_RE.match(current)
        if quote_match:
            quoted = [quote_match.group(1)]
            index += 1
            while index < len(lines):
                nxt = _BLOCKQUOTE_RE.match(lines[index])
                if not nxt:
                    break
                quoted.append(nxt.group(1))
                index += 1
            body = "\n".join(quoted).strip()
            if quote_fn:
                flowables.append(quote_fn(body))
            else:
                quote_style = styles["ReportQuote"] if "ReportQuote" in styles else styles["ReportBody"]
                flowables.append(paragraph(replace_inline_markdown(body), quote_style))
            flowables.append(spacer(1, 4))
            continue

        if is_list_line(current):
            while index < len(lines) and is_list_line(lines[index]):
                item = lines[index]
                ul_match = _UL_RE.match(item)
                ol_match = None if ul_match else _OL_RE.match(item)
                match = ul_match or ol_match
                level = _list_indent_level(match.group(1))
                checked = match.group(3)
                item_text = match.group(4) if ul_match else match.group(4)
                if checked is not None:
                    marker = "☑" if checked.lower() == "x" else "☐"
                    prefix = ("&nbsp;" * (4 * level))
                    emit_text(flowables, item_text, "ReportBullet", bullet=marker, prefix=prefix)
                elif ul_match:
                    prefix = "&nbsp;" * (4 * level)
                    emit_text(flowables, item_text, "ReportBullet", bullet="•", prefix=prefix)
                else:
                    prefix = "&nbsp;" * (4 * level)
                    emit_text(flowables, item_text, "ReportBullet", bullet=f"{match.group(2)}.", prefix=prefix)
                index += 1
            continue

        paragraph_lines = [current]
        index += 1
        while index < len(lines) and not starts_block(lines[index], lines, index):
            paragraph_lines.append(lines[index])
            index += 1
        joined = " ".join(part.strip() for part in paragraph_lines if part.strip())
        emit_text(flowables, joined, "ReportBody")

    return flowables


def build_pie_chart(data_map, to_int, primary, colors, drawing_class, pie_class):
    labels = [key for key, value in data_map.items() if to_int(value, 0) > 0]
    values = [to_int(data_map[label], 0) for label in labels]
    if not labels:
        labels = ["No Data"]
        values = [1]

    drawing = drawing_class(420, 220)
    pie = pie_class()
    pie.x = 112
    pie.y = 24
    pie.width = 170
    pie.height = 170
    pie.data = values
    pie.labels = [f"{labels[idx]} ({values[idx]})" for idx in range(len(labels))]
    pie.slices.strokeWidth = 0.6
    pie.slices.strokeColor = colors.white
    palette = [
        primary,
        colors.HexColor("#DC2626"),
        colors.HexColor("#F59E0B"),
        colors.HexColor("#10B981"),
        colors.HexColor("#7C3AED"),
        colors.HexColor("#94A3B8"),
    ]
    for index in range(len(values)):
        pie.slices[index].fillColor = palette[index % len(palette)]
    drawing.add(pie)
    return drawing


def build_bar_chart(data_map, to_int, primary, colors, drawing_class, vertical_bar_chart_class, bar_colors=None):
    keys = list(data_map.keys()) or ["No Data"]
    values = [to_int(data_map.get(key, 0), 0) for key in keys] or [0]

    drawing = drawing_class(450, 220)
    chart = vertical_bar_chart_class()
    chart.x = 38
    chart.y = 46
    chart.height = 140
    chart.width = 342
    chart.data = [values]
    chart.barWidth = 20
    chart.groupSpacing = 14
    chart.barSpacing = 4
    chart.bars[0].fillColor = primary
    chart.bars[0].strokeColor = primary
    if bar_colors:
        for index, fill in enumerate(bar_colors):
            try:
                chart.bars[(0, index)].fillColor = fill
                chart.bars[(0, index)].strokeColor = fill
            except Exception:
                pass
    chart.categoryAxis.categoryNames = keys
    chart.categoryAxis.labels.angle = 18
    chart.categoryAxis.labels.dy = -12
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.strokeColor = colors.HexColor("#94A3B8")
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values + [1]) + 1
    chart.valueAxis.valueStep = max(1, int(chart.valueAxis.valueMax / 5))
    chart.valueAxis.strokeColor = colors.HexColor("#94A3B8")
    chart.valueAxis.gridStrokeColor = colors.HexColor("#E2E8F0")
    chart.valueAxis.gridStrokeWidth = 0.4
    drawing.add(chart)
    return drawing


def section_title(
    text,
    resolve,
    replace_inline_markdown,
    paragraph,
    styles,
    table_class,
    table_style_class,
    mm,
    surface_light,
    border_color,
    primary,
):
    heading = paragraph(replace_inline_markdown(resolve(text or "")), styles["ReportSectionTitle"])
    title_table = table_class([[heading]], colWidths=[178 * mm], hAlign="LEFT")
    title_table.setStyle(
        table_style_class(
            [
                ("BACKGROUND", (0, 0), (-1, -1), surface_light),
                ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                ("LINEBEFORE", (0, 0), (0, 0), 4, primary),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return title_table


def _xml_escape(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _is_plain_table_cell(cell):
    return cell is None or isinstance(cell, (str, int, float))


def _wrap_table_rows(rows, paragraph_class, header_style, body_style):
    wrapped = []
    for row_index, row in enumerate(rows or []):
        style = header_style if row_index == 0 else body_style
        wrapped_row = []
        for cell in row:
            if _is_plain_table_cell(cell):
                text = "" if cell is None else _xml_escape(cell)
                wrapped_row.append(paragraph_class(text or " ", style))
            else:
                wrapped_row.append(cell)
        wrapped.append(wrapped_row)
    return wrapped


def table_with_style(
    rows,
    col_widths,
    table_class,
    table_style_class,
    accent,
    border_color,
    surface_light,
    colors,
    paragraph_class=None,
    header_style=None,
    body_style=None,
    extra_commands=None,
):
    payload = rows
    if paragraph_class and header_style and body_style:
        payload = _wrap_table_rows(rows, paragraph_class, header_style, body_style)
    table = table_class(payload, colWidths=col_widths, hAlign="LEFT")
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("GRID", (0, 0), (-1, -1), 0.55, border_color),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, surface_light]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if extra_commands:
        commands.extend(extra_commands)
    table.setStyle(table_style_class(commands))
    return table


def metric_tiles(
    items,
    columns,
    table_class,
    table_style_class,
    paragraph,
    spacer,
    styles,
    mm,
    border_color,
    colors,
    replace_inline_markdown,
):
    if not items:
        return paragraph("No metrics available.", styles["ReportMuted"])
    col_width = (178 * mm) / max(columns, 1)
    rows = []
    row = []
    for label, value in items:
        content = [
            paragraph(replace_inline_markdown(str(label)), styles["ReportMetricLabel"]),
            spacer(1, 3),
            paragraph(f"<b>{replace_inline_markdown(str(value))}</b>", styles["ReportMetricValue"]),
        ]
        row.append(content)
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        while len(row) < columns:
            row.append("")
        rows.append(row)

    table = table_class(rows, colWidths=[col_width] * columns, hAlign="LEFT")
    table.setStyle(
        table_style_class(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def _chrome_header_footer(branding, company_name, resolve, context):
    branding = branding if isinstance(branding, dict) else {}
    header_left = str(branding.get("header_text") or "").strip() or company_name
    header_right = resolve("{{application.name}}") or resolve("{{record.name}}") or "Report"
    footer_parts = []
    footer_text = str(branding.get("footer_text") or "").strip()
    if footer_text:
        footer_parts.append(footer_text)
    elif company_name:
        footer_parts.append(company_name)
    generated = str((context or {}).get("generated_date") or "").strip()
    if generated:
        footer_parts.append(generated)
    footer = " · ".join(footer_parts)
    return header_left, header_right, footer


def make_draw_cover_page(a4, mm, primary, accent, company_name, colors, context=None, branding=None):
    def draw_cover_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = a4
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(1.2)
        canvas.line(0, page_height - (8 * mm), page_width, page_height - (8 * mm))
        canvas.setStrokeColor(accent)
        canvas.setLineWidth(0.6)
        rule_y = (RAPTOR_LOCKUP_BOTTOM_MM + RAPTOR_LOCKUP_HEIGHT_MM + 3) * mm
        canvas.line(0, rule_y, page_width, rule_y)
        text_x = draw_raptor_footer_lockup(canvas, mm)
        _, _, footer = _chrome_header_footer(branding, company_name, lambda _token: "", context)
        if footer:
            canvas.setFont("Helvetica", 7.5)
            canvas.setFillColor(colors.HexColor("#64748B"))
            canvas.drawString(text_x, (RAPTOR_LOCKUP_BOTTOM_MM + 5) * mm, footer)
        canvas.restoreState()

    return draw_cover_page


def make_draw_body_page(a4, mm, surface_light, border_color, muted, resolve, context, company_name, branding=None):
    def draw_body_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = a4
        canvas.setStrokeColor(border_color)
        canvas.setLineWidth(0.5)
        canvas.line(12 * mm, page_height - (12 * mm), page_width - (12 * mm), page_height - (12 * mm))
        canvas.setFont("Helvetica", 8.4)
        canvas.setFillColor(muted)
        header_left, header_right, footer = _chrome_header_footer(branding, company_name, resolve, context)
        canvas.drawString(14 * mm, page_height - (9 * mm), header_left)
        canvas.drawRightString(page_width - (14 * mm), page_height - (9 * mm), header_right)
        text_x = draw_raptor_footer_lockup(canvas, mm)
        footer_y = (RAPTOR_LOCKUP_BOTTOM_MM + 5) * mm
        canvas.drawString(text_x, footer_y, footer)
        canvas.drawRightString(page_width - (14 * mm), footer_y, f"Page {doc.page}")
        canvas.restoreState()

    return draw_body_page


__all__ = [
    "build_bar_chart",
    "build_pie_chart",
    "get_embedded_image",
    "make_draw_body_page",
    "make_draw_cover_page",
    "markdown_to_flowables",
    "metric_tiles",
    "draw_raptor_footer_lockup",
    "raptor_lockup_path",
    "safe_color",
    "section_title",
    "table_with_style",
]
