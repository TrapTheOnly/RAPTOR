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


def markdown_to_flowables(
    raw_text,
    styles,
    replace_inline_markdown,
    markdown_image_pattern,
    get_embedded_image_fn,
    paragraph,
    spacer,
    empty_message="No content provided.",
):
    text = str(raw_text or "")
    if not text.strip():
        return [paragraph(empty_message, styles["ReportMuted"])]

    flowables = []
    for line in text.splitlines():
        current = line.rstrip()
        if not current.strip():
            flowables.append(spacer(1, 4))
            continue

        image_matches = list(markdown_image_pattern.finditer(current))
        text_without_images = markdown_image_pattern.sub("", current).strip()

        if text_without_images:
            if text_without_images.startswith("### "):
                flowables.append(paragraph(replace_inline_markdown(text_without_images[4:]), styles["ReportSectionTitle"]))
            elif text_without_images.startswith("## "):
                flowables.append(paragraph(replace_inline_markdown(text_without_images[3:]), styles["ReportSectionTitle"]))
            elif text_without_images.startswith("# "):
                flowables.append(paragraph(replace_inline_markdown(text_without_images[2:]), styles["ReportSectionTitle"]))
            elif text_without_images.startswith("- ") or text_without_images.startswith("* "):
                flowables.append(
                    paragraph(replace_inline_markdown(text_without_images[2:]), styles["ReportBullet"], bulletText="•")
                )
            else:
                flowables.append(paragraph(replace_inline_markdown(text_without_images), styles["ReportBody"]))

        for match in image_matches:
            image_url = match.group(2)
            image = get_embedded_image_fn(image_url, centered=True)
            if image:
                flowables.append(spacer(1, 6))
                flowables.append(image)
                flowables.append(spacer(1, 6))
            else:
                alt_text = match.group(1) or "image"
                flowables.append(
                    paragraph(f"[Image omitted: {replace_inline_markdown(alt_text)}]", styles["ReportMuted"])
                )

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


def build_bar_chart(data_map, to_int, primary, colors, drawing_class, vertical_bar_chart_class):
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


def table_with_style(rows, col_widths, table_class, table_style_class, accent, border_color, surface_light, colors):
    table = table_class(rows, colWidths=col_widths, hAlign="LEFT")
    table.setStyle(
        table_style_class(
            [
                ("BACKGROUND", (0, 0), (-1, 0), accent),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("GRID", (0, 0), (-1, -1), 0.55, border_color),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, surface_light]),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
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


def make_draw_cover_page(a4, mm, primary, accent, company_name, colors):
    def draw_cover_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = a4
        canvas.setFillColor(primary)
        canvas.rect(0, page_height - (24 * mm), page_width, 24 * mm, fill=1, stroke=0)
        canvas.setFillColor(accent)
        canvas.rect(0, 0, page_width, 7 * mm, fill=1, stroke=0)
        canvas.restoreState()

    return draw_cover_page


def make_draw_body_page(a4, mm, surface_light, border_color, muted, resolve, context, company_name):
    def draw_body_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = a4
        canvas.setFillColor(surface_light)
        canvas.rect(0, page_height - (15 * mm), page_width, 15 * mm, fill=1, stroke=0)
        canvas.setStrokeColor(border_color)
        canvas.setLineWidth(0.5)
        canvas.line(12 * mm, page_height - (15 * mm), page_width - (12 * mm), page_height - (15 * mm))
        canvas.setFont("Helvetica", 8.4)
        canvas.setFillColor(muted)
        canvas.drawString(14 * mm, page_height - (10 * mm), company_name)
        canvas.drawRightString(page_width - (14 * mm), page_height - (10 * mm), resolve("{{record.name}}") or "Pentest")
        canvas.drawString(14 * mm, 10 * mm, f"Generated {context['generated_date']}")
        canvas.drawRightString(page_width - (14 * mm), 10 * mm, f"Page {doc.page}")
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
    "safe_color",
    "section_title",
    "table_with_style",
]
