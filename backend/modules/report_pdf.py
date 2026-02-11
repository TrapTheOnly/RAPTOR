import datetime
import html
import json
import re


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")
IMAGE_REFERENCE_PATTERN = re.compile(
    r"(?:https?://[^)\s]+)?/pentest/images/([a-f0-9]{32}\.(?:png|jpg|jpeg|gif|webp))",
    re.IGNORECASE
)
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _safe_json_load(raw_value, default):
    if raw_value is None:
        return default
    if isinstance(raw_value, (list, dict)):
        return raw_value
    if isinstance(raw_value, str) and raw_value.strip():
        try:
            return json.loads(raw_value)
        except Exception:
            return default
    return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_open_ports(raw_ports):
    if isinstance(raw_ports, list):
        values = raw_ports
    else:
        values = str(raw_ports or "").replace(";", ",").split(",")
    normalized = []
    for value in values:
        port = _to_int(str(value).strip(), default=None)
        if port is None:
            continue
        if 1 <= port <= 65535 and port not in normalized:
            normalized.append(port)
    return sorted(normalized)


def _severity_from_score(score):
    value = _to_float(score, 0.0)
    if value >= 9.0:
        return "Critical"
    if value >= 7.0:
        return "High"
    if value >= 4.0:
        return "Medium"
    if value > 0.0:
        return "Low"
    return "Informational"


def _flatten(prefix, value, target):
    if isinstance(value, dict):
        for key, inner in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            _flatten(path, inner, target)
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            path = f"{prefix}.{index}" if prefix else str(index)
            _flatten(path, inner, target)
    else:
        target[prefix] = "" if value is None else str(value)


def _resolve_placeholders(value, flat_context):
    if not isinstance(value, str):
        return value

    def repl(match):
        key = match.group(1).strip()
        return flat_context.get(key, "")

    return PLACEHOLDER_PATTERN.sub(repl, value)


def _replace_inline_markdown(text):
    safe_text = html.escape(str(text or ""))
    safe_text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe_text)
    safe_text = re.sub(r"`([^`]+)`", r"<font name='Courier'>\1</font>", safe_text)
    safe_text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<a href='\2'>\1</a>", safe_text)
    return safe_text


def _build_service_name(port):
    service_map = {
        21: "FTP",
        22: "SSH",
        23: "Telnet",
        25: "SMTP",
        53: "DNS",
        80: "HTTP",
        110: "POP3",
        123: "NTP",
        143: "IMAP",
        161: "SNMP",
        389: "LDAP",
        443: "HTTPS",
        445: "SMB",
        465: "SMTPS",
        587: "SMTP Submission",
        636: "LDAPS",
        1433: "MSSQL",
        1521: "Oracle",
        2049: "NFS",
        3306: "MySQL",
        3389: "RDP",
        5432: "PostgreSQL",
        6379: "Redis",
        8080: "HTTP Alternate",
        8443: "HTTPS Alternate"
    }
    return service_map.get(port, "Unknown")


def _build_report_model(record_data, checklist_templates):
    vulnerabilities = _safe_json_load(record_data.get("vulnerabilities"), [])
    if not isinstance(vulnerabilities, list):
        vulnerabilities = []
    vulnerabilities = [item for item in vulnerabilities if isinstance(item, dict)]

    open_ports = _parse_open_ports(record_data.get("open_ports"))
    checklist_states = _safe_json_load(record_data.get("checklist_states"), {})
    selected_checklists = checklist_states.get("selected", []) if isinstance(checklist_states, dict) else []
    if not isinstance(selected_checklists, list):
        selected_checklists = []
    checklist_statuses = checklist_states.get("statuses", {}) if isinstance(checklist_states, dict) else {}
    if not isinstance(checklist_statuses, dict):
        checklist_statuses = {}

    templates = []
    for template in checklist_templates or []:
        if not isinstance(template, dict):
            continue
        if template.get("enabled") is False:
            continue
        key = str(template.get("key", "")).strip()
        sections = template.get("sections")
        if not key or not isinstance(sections, list):
            continue
        templates.append(template)

    open_port_set = set(open_ports)
    enabled_template_keys = set([str(value).strip() for value in selected_checklists if str(value).strip()])
    for template in templates:
        for port in template.get("auto_ports", []):
            if _to_int(port, -1) in open_port_set:
                enabled_template_keys.add(template.get("key"))
                break

    checklist_progress_rows = []
    checklist_completed = 0
    checklist_irrelevant = 0
    checklist_unstarted = 0
    checklist_total = 0

    for template in templates:
        key = template.get("key")
        if key not in enabled_template_keys:
            continue
        item_ids = []
        for section in template.get("sections", []):
            for item in section.get("items", []):
                item_id = str(item.get("id", "")).strip()
                if item_id:
                    item_ids.append(item_id)
        if not item_ids:
            continue

        status_map = checklist_statuses.get(key, {})
        if not isinstance(status_map, dict):
            status_map = {}
        completed = 0
        irrelevant = 0
        for item_id in item_ids:
            status = str(status_map.get(item_id, "unstarted")).strip().lower()
            if status == "completed":
                completed += 1
            elif status == "irrelevant":
                irrelevant += 1

        total = len(item_ids)
        unstarted = max(total - completed - irrelevant, 0)
        checklist_progress_rows.append({
            "name": template.get("name", key),
            "service": template.get("service", ""),
            "completed": completed,
            "irrelevant": irrelevant,
            "unstarted": unstarted,
            "total": total,
            "percentage": round((completed / total) * 100, 1) if total else 0
        })

        checklist_total += total
        checklist_completed += completed
        checklist_irrelevant += irrelevant
        checklist_unstarted += unstarted

    severity_counts = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Informational": 0
    }
    for vuln in vulnerabilities:
        severity = _severity_from_score(vuln.get("baseScore"))
        severity_counts[severity] += 1

    vulnerability_count = len(vulnerabilities)
    vulnerability_fixed = _to_int(record_data.get("vulnerability_fixed"), 0) == 1
    fixed_findings = vulnerability_count if vulnerability_fixed else 0
    open_findings = max(vulnerability_count - fixed_findings, 0)

    generated_at = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    context = {
        "generated_at": generated_at,
        "generated_date": generated_at.split(" ")[0],
        "record": {
            "name": record_data.get("name", ""),
            "ip_address": record_data.get("ip_address", ""),
            "source": record_data.get("source", ""),
            "application_name": record_data.get("application_name", ""),
            "description": record_data.get("description", "")
        },
        "pentest": {
            "status": record_data.get("status", "Not Started"),
            "tested_by": (record_data.get("tested_by") or "Unassigned"),
            "test_start_date": record_data.get("test_start_date", ""),
            "test_end_date": record_data.get("test_end_date", ""),
            "service_desk_link": record_data.get("service_desk_link", ""),
            "notes": record_data.get("notes", ""),
            "open_ports": ", ".join([str(port) for port in open_ports]),
            "vulnerable": "Yes" if _to_int(record_data.get("vulnerable"), 0) == 1 else "No",
            "vulnerability_fixed": "Yes" if vulnerability_fixed else "No"
        },
        "metrics": {
            "vulnerability_count": vulnerability_count,
            "critical_count": severity_counts["Critical"],
            "high_count": severity_counts["High"],
            "medium_count": severity_counts["Medium"],
            "low_count": severity_counts["Low"],
            "informational_count": severity_counts["Informational"],
            "critical_high_count": severity_counts["Critical"] + severity_counts["High"],
            "open_findings": open_findings,
            "fixed_findings": fixed_findings,
            "open_ports_count": len(open_ports),
            "checklist_total": checklist_total,
            "checklist_completed": checklist_completed,
            "checklist_irrelevant": checklist_irrelevant,
            "checklist_unstarted": checklist_unstarted,
            "checklist_percentage": round((checklist_completed / checklist_total) * 100, 1)
            if checklist_total
            else 0
        }
    }

    flat_context = {}
    _flatten("", context, flat_context)

    return {
        "context": context,
        "flat_context": flat_context,
        "open_ports": open_ports,
        "vulnerabilities": vulnerabilities,
        "severity_counts": severity_counts,
        "checklist_progress_rows": checklist_progress_rows
    }


def render_pentest_report_pdf(
    record_data,
    template_definition,
    checklist_templates=None,
    image_fetcher=None
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
            TableStyle
        )
    except Exception as e:
        raise RuntimeError(f"Report generation dependency missing: {e}") from e

    if not isinstance(template_definition, dict):
        raise ValueError("Template definition must be a JSON object.")

    blocks = template_definition.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Template must include a non-empty 'blocks' array.")

    model = _build_report_model(record_data or {}, checklist_templates or [])
    context = model["context"]
    flat_context = dict(model["flat_context"])

    placeholders = template_definition.get("placeholders")
    if isinstance(placeholders, dict):
        resolved = {}
        for key, value in placeholders.items():
            resolved[key] = _resolve_placeholders(value, flat_context) if isinstance(value, str) else value
            flat_context[str(key)] = "" if resolved[key] is None else str(resolved[key])
            flat_context[f"placeholders.{key}"] = flat_context[str(key)]
        context["placeholders"] = resolved

    branding = template_definition.get("branding") if isinstance(template_definition.get("branding"), dict) else {}
    primary_color = branding.get("primary_color", "#0B5CAD")
    accent_color = branding.get("accent_color", "#1E293B")
    logo_url = str(branding.get("logo_url", "") or "").strip()
    company_name = str(branding.get("company_name", "Security Operations") or "Security Operations")

    def safe_color(value, fallback):
        try:
            return colors.HexColor(value)
        except Exception:
            return colors.HexColor(fallback)

    primary = safe_color(primary_color, "#0B5CAD")
    accent = safe_color(accent_color, "#1E293B")
    muted = colors.HexColor("#64748B")
    text_primary = colors.HexColor("#111827")
    border_color = colors.HexColor("#CBD5E1")
    surface_light = colors.HexColor("#F8FAFC")
    severity_color_hex = {
        "Critical": "#991B1B",
        "High": "#B45309",
        "Medium": "#0E7490",
        "Low": "#166534",
        "Informational": "#475569"
    }
    severity_colors = {
        key: colors.HexColor(value) for key, value in severity_color_hex.items()
    }

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportSectionTitle",
            parent=styles["Heading2"],
            fontSize=14.5,
            leading=18,
            textColor=accent,
            spaceBefore=0,
            spaceAfter=0
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportBody",
            parent=styles["BodyText"],
            fontSize=10.2,
            leading=14.3,
            textColor=text_primary
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMuted",
            parent=styles["BodyText"],
            fontSize=9.1,
            leading=12.4,
            textColor=muted
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMutedCenter",
            parent=styles["ReportMuted"],
            alignment=TA_CENTER
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
            spaceAfter=8
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverSub",
            parent=styles["BodyText"],
            fontSize=12.8,
            leading=18,
            alignment=TA_CENTER,
            textColor=muted
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverMetaLabel",
            parent=styles["BodyText"],
            fontSize=9.2,
            leading=12,
            textColor=muted
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportCoverMetaValue",
            parent=styles["BodyText"],
            fontSize=10.3,
            leading=13.5,
            textColor=text_primary
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMetricLabel",
            parent=styles["BodyText"],
            fontSize=8.5,
            leading=11.3,
            textColor=muted,
            alignment=TA_CENTER
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportMetricValue",
            parent=styles["BodyText"],
            fontSize=16,
            leading=18,
            textColor=accent,
            alignment=TA_CENTER
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
            bulletIndent=0
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportFindingTitle",
            parent=styles["BodyText"],
            fontSize=11.2,
            leading=14.5,
            textColor=accent
        )
    )

    def resolve(value):
        return _resolve_placeholders(value, flat_context)

    def get_embedded_image(url, max_width_mm=170, max_height_mm=90, centered=False):
        if not url or not image_fetcher:
            return None
        match = IMAGE_REFERENCE_PATTERN.search(str(url))
        if not match:
            return None
        filename = match.group(1).lower()
        try:
            file_obj = image_fetcher(filename)
            image = RLImage(file_obj)
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

    def markdown_to_flowables(raw_text, empty_message="No content provided."):
        text = str(raw_text or "")
        if not text.strip():
            return [Paragraph(empty_message, styles["ReportMuted"])]

        flowables = []
        for line in text.splitlines():
            current = line.rstrip()
            if not current.strip():
                flowables.append(Spacer(1, 4))
                continue

            image_matches = list(MARKDOWN_IMAGE_PATTERN.finditer(current))
            text_without_images = MARKDOWN_IMAGE_PATTERN.sub("", current).strip()

            if text_without_images:
                if text_without_images.startswith("### "):
                    flowables.append(
                        Paragraph(_replace_inline_markdown(text_without_images[4:]), styles["ReportSectionTitle"])
                    )
                elif text_without_images.startswith("## "):
                    flowables.append(
                        Paragraph(_replace_inline_markdown(text_without_images[3:]), styles["ReportSectionTitle"])
                    )
                elif text_without_images.startswith("# "):
                    flowables.append(
                        Paragraph(_replace_inline_markdown(text_without_images[2:]), styles["ReportSectionTitle"])
                    )
                elif text_without_images.startswith("- ") or text_without_images.startswith("* "):
                    flowables.append(
                        Paragraph(
                            _replace_inline_markdown(text_without_images[2:]),
                            styles["ReportBullet"],
                            bulletText="•"
                        )
                    )
                else:
                    flowables.append(
                        Paragraph(_replace_inline_markdown(text_without_images), styles["ReportBody"])
                    )

            for match in image_matches:
                image_url = match.group(2)
                image = get_embedded_image(image_url, centered=True)
                if image:
                    flowables.append(Spacer(1, 6))
                    flowables.append(image)
                    flowables.append(Spacer(1, 6))
                else:
                    alt_text = match.group(1) or "image"
                    flowables.append(
                        Paragraph(
                            f"[Image omitted: {_replace_inline_markdown(alt_text)}]",
                            styles["ReportMuted"]
                        )
                    )

        return flowables

    def build_pie_chart(data_map):
        labels = [key for key, value in data_map.items() if _to_int(value, 0) > 0]
        values = [_to_int(data_map[label], 0) for label in labels]
        if not labels:
            labels = ["No Data"]
            values = [1]

        drawing = Drawing(420, 220)
        pie = Pie()
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
            colors.HexColor("#94A3B8")
        ]
        for index in range(len(values)):
            pie.slices[index].fillColor = palette[index % len(palette)]
        drawing.add(pie)
        return drawing

    def build_bar_chart(data_map):
        keys = list(data_map.keys()) or ["No Data"]
        values = [_to_int(data_map.get(key, 0), 0) for key in keys] or [0]

        drawing = Drawing(450, 220)
        chart = VerticalBarChart()
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

    def section_title(text):
        heading = Paragraph(_replace_inline_markdown(resolve(text or "")), styles["ReportSectionTitle"])
        title_table = Table([[heading]], colWidths=[178 * mm], hAlign="LEFT")
        title_table.setStyle(
            TableStyle(
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

    def table_with_style(rows, col_widths):
        table = Table(rows, colWidths=col_widths, hAlign="LEFT")
        table.setStyle(
            TableStyle(
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

    def metric_tiles(items, columns=3):
        if not items:
            return Paragraph("No metrics available.", styles["ReportMuted"])
        col_width = (178 * mm) / max(columns, 1)
        rows = []
        row = []
        for label, value in items:
            content = [
                Paragraph(_replace_inline_markdown(str(label)), styles["ReportMetricLabel"]),
                Spacer(1, 3),
                Paragraph(f"<b>{_replace_inline_markdown(str(value))}</b>", styles["ReportMetricValue"])
            ]
            row.append(content)
            if len(row) == columns:
                rows.append(row)
                row = []
        if row:
            while len(row) < columns:
                row.append("")
            rows.append(row)

        table = Table(rows, colWidths=[col_width] * columns, hAlign="LEFT")
        table.setStyle(
            TableStyle(
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

    def draw_cover_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = A4
        canvas.setFillColor(primary)
        canvas.rect(0, page_height - (24 * mm), page_width, 24 * mm, fill=1, stroke=0)
        canvas.setFillColor(accent)
        canvas.rect(0, 0, page_width, 7 * mm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(14 * mm, page_height - (14 * mm), company_name)
        canvas.restoreState()

    def draw_body_page(canvas, doc):
        canvas.saveState()
        page_width, page_height = A4
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

    story = []

    for raw_block in blocks:
        if not isinstance(raw_block, dict):
            continue

        block_type = str(raw_block.get("type", "")).strip().lower()
        title = resolve(raw_block.get("title", ""))

        if block_type == "page_break":
            story.append(PageBreak())
            continue

        if block_type == "cover":
            story.append(Spacer(1, 44 * mm))

            if raw_block.get("show_logo") and logo_url:
                logo_image = get_embedded_image(resolve(logo_url), max_width_mm=52, max_height_mm=52, centered=True)
                if logo_image:
                    story.append(logo_image)
                    story.append(Spacer(1, 12 * mm))

            story.append(
                Paragraph(
                    _replace_inline_markdown(title or "Penetration Test Report"),
                    styles["ReportCoverTitle"]
                )
            )
            subtitle = resolve(raw_block.get("subtitle", ""))
            if subtitle:
                story.append(Paragraph(_replace_inline_markdown(subtitle), styles["ReportCoverSub"]))
                story.append(Spacer(1, 8 * mm))

            prepared_for = resolve(context.get("placeholders", {}).get("prepared_for", "{{record.name}}"))
            prepared_by = resolve(context.get("placeholders", {}).get("prepared_by", "{{pentest.tested_by}}"))
            meta_rows = [
                [
                    Paragraph("Prepared For", styles["ReportCoverMetaLabel"]),
                    Paragraph(_replace_inline_markdown(prepared_for or "N/A"), styles["ReportCoverMetaValue"]),
                ],
                [
                    Paragraph("Prepared By", styles["ReportCoverMetaLabel"]),
                    Paragraph(_replace_inline_markdown(prepared_by or "N/A"), styles["ReportCoverMetaValue"]),
                ],
                [
                    Paragraph("Application", styles["ReportCoverMetaLabel"]),
                    Paragraph(_replace_inline_markdown(resolve("{{record.application_name}}") or "N/A"), styles["ReportCoverMetaValue"]),
                ],
                [
                    Paragraph("Generated", styles["ReportCoverMetaLabel"]),
                    Paragraph(_replace_inline_markdown(context["generated_at"]), styles["ReportCoverMetaValue"]),
                ],
            ]
            meta_table = Table(meta_rows, colWidths=[42 * mm, 92 * mm], hAlign="CENTER")
            meta_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                        ("INNERGRID", (0, 0), (-1, -1), 0.4, border_color),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ]
                )
            )
            story.append(Spacer(1, 9 * mm))
            story.append(meta_table)
            story.append(Spacer(1, 8 * mm))
            story.append(
                Paragraph(
                    "Confidential. Distribution limited to approved stakeholders.",
                    styles["ReportMutedCenter"]
                )
            )
            story.append(PageBreak())
            continue

        if title:
            story.append(section_title(title))
            story.append(Spacer(1, 4))

        if block_type == "engagement_overview":
            rows = [
                ["Field", "Value"],
                ["Target", resolve("{{record.name}}") or "N/A"],
                ["IP Address", resolve("{{record.ip_address}}") or "N/A"],
                ["Source", resolve("{{record.source}}") or "N/A"],
                ["Application", resolve("{{record.application_name}}") or "N/A"],
                ["Assigned Tester", resolve("{{pentest.tested_by}}") or "Unassigned"],
                ["Status", resolve("{{pentest.status}}") or "Not Started"],
                ["Start Date", resolve("{{pentest.test_start_date}}") or "N/A"],
                ["End Date", resolve("{{pentest.test_end_date}}") or "N/A"],
                ["Service Desk Link", resolve("{{pentest.service_desk_link}}") or "N/A"]
            ]
            story.append(table_with_style(rows, [55 * mm, 123 * mm]))
            story.append(Spacer(1, 8))
            continue

        if block_type == "key_metrics":
            metrics = [
                ("Total Findings", resolve("{{metrics.vulnerability_count}}")),
                ("Critical Findings", resolve("{{metrics.critical_count}}")),
                ("High Findings", resolve("{{metrics.high_count}}")),
                ("Open Findings", resolve("{{metrics.open_findings}}")),
                ("Fixed Findings", resolve("{{metrics.fixed_findings}}")),
                ("Open Ports", resolve("{{metrics.open_ports_count}}")),
                ("Checklist Completed", resolve("{{metrics.checklist_completed}}")),
                ("Checklist Coverage", f"{resolve('{{metrics.checklist_percentage}}')}%")
            ]
            story.append(metric_tiles(metrics, columns=4))
            story.append(Spacer(1, 8))
            continue

        if block_type == "chart":
            chart_type = str(raw_block.get("chart", "")).strip().lower()
            if chart_type == "vulnerability_severity":
                chart = build_bar_chart(model["severity_counts"])
                chart_caption = "Distribution of findings by severity."
            elif chart_type == "checklist_completion":
                chart = build_pie_chart(
                    {
                        "Completed": context["metrics"]["checklist_completed"],
                        "Irrelevant": context["metrics"]["checklist_irrelevant"],
                        "Unstarted": context["metrics"]["checklist_unstarted"]
                    }
                )
                chart_caption = "Checklist completion breakdown."
            elif chart_type == "vulnerability_fix_status":
                chart = build_pie_chart(
                    {
                        "Open": context["metrics"]["open_findings"],
                        "Fixed": context["metrics"]["fixed_findings"]
                    }
                )
                chart_caption = "Open versus remediated findings."
            else:
                chart = build_pie_chart({"Unsupported": 1})
                chart_caption = "Unsupported chart configuration."

            chart_card = Table([[chart]], colWidths=[178 * mm], hAlign="LEFT")
            chart_card.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                        ("LEFTPADDING", (0, 0), (-1, -1), 6),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(chart_card)
            story.append(Spacer(1, 3))
            story.append(Paragraph(chart_caption, styles["ReportMutedCenter"]))
            story.append(Spacer(1, 8))
            continue

        if block_type == "open_ports":
            if model["open_ports"]:
                rows = [["Port", "Likely Service"]]
                for port in model["open_ports"]:
                    rows.append([str(port), _build_service_name(port)])
                story.append(table_with_style(rows, [36 * mm, 142 * mm]))
            else:
                story.append(Paragraph("No open ports recorded.", styles["ReportMuted"]))
            story.append(Spacer(1, 8))
            continue

        if block_type == "markdown":
            field = str(raw_block.get("field", "")).strip().lower()
            field_value = ""
            if field in {"description", "record_description"}:
                field_value = context["record"]["description"]
            elif field in {"notes", "security_details"}:
                field_value = context["pentest"]["notes"]
            elif field in {"service_desk_link"}:
                field_value = context["pentest"]["service_desk_link"]
            elif field in {"open_ports"}:
                field_value = context["pentest"]["open_ports"]
            story.extend(markdown_to_flowables(resolve(field_value)))
            story.append(Spacer(1, 8))
            continue

        if block_type == "checklists":
            rows = [["Checklist", "Service", "Completed", "Irrelevant", "Unstarted", "Total", "Completion %"]]
            for item in model["checklist_progress_rows"]:
                rows.append([
                    item["name"],
                    str(item["service"]).upper() if item["service"] else "N/A",
                    str(item["completed"]),
                    str(item["irrelevant"]),
                    str(item["unstarted"]),
                    str(item["total"]),
                    f"{item['percentage']}%"
                ])

            if len(rows) == 1:
                story.append(Paragraph("No checklist coverage recorded.", styles["ReportMuted"]))
            else:
                story.append(
                    table_with_style(
                        rows,
                        [56 * mm, 19 * mm, 18 * mm, 20 * mm, 20 * mm, 14 * mm, 31 * mm]
                    )
                )
            story.append(Spacer(1, 8))
            continue

        if block_type == "vulnerabilities":
            include_descriptions = bool(raw_block.get("include_descriptions", True))
            if not model["vulnerabilities"]:
                story.append(Paragraph("No vulnerabilities recorded.", styles["ReportMuted"]))
                story.append(Spacer(1, 8))
                continue

            for index, vuln in enumerate(model["vulnerabilities"], start=1):
                category_name = str(vuln.get("categoryName", "")).strip() or f"Finding {index}"
                base_score = _to_float(vuln.get("baseScore"), 0.0)
                severity = _severity_from_score(base_score)
                severity_color = severity_colors.get(severity, muted)

                finding_header = Paragraph(
                    f"<b>{index}. {_replace_inline_markdown(category_name)}</b>",
                    styles["ReportFindingTitle"]
                )
                severity_label = Paragraph(
                    f"<b><font color='{severity_color_hex.get(severity, '#475569')}'>"
                    f"{severity} | CVSS {base_score:.1f}</font></b>",
                    styles["ReportMutedCenter"]
                )

                card_content = [finding_header, Spacer(1, 3), severity_label]
                metrics = vuln.get("metrics")
                if isinstance(metrics, dict) and metrics:
                    ordered = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
                    metric_parts = [
                        f"{metric}:{metrics.get(metric, '')}"
                        for metric in ordered
                        if metrics.get(metric) is not None and metrics.get(metric) != ""
                    ]
                    if metric_parts:
                        card_content.append(Spacer(1, 2))
                        card_content.append(
                            Paragraph(
                                f"CVSS Vector: {_replace_inline_markdown('/'.join(metric_parts))}",
                                styles["ReportMuted"]
                            )
                        )

                if include_descriptions:
                    description = vuln.get("description", "")
                    card_content.append(Spacer(1, 4))
                    card_content.extend(markdown_to_flowables(description))

                finding_table = Table([[card_content]], colWidths=[178 * mm], hAlign="LEFT")
                finding_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                            ("BOX", (0, 0), (-1, -1), 0.7, border_color),
                            ("LINEBEFORE", (0, 0), (0, 0), 3, severity_color),
                            ("LEFTPADDING", (0, 0), (-1, -1), 8),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                story.append(finding_table)
                story.append(Spacer(1, 7))
            continue

        if block_type == "text":
            body = resolve(raw_block.get("content", ""))
            story.extend(markdown_to_flowables(body))
            story.append(Spacer(1, 8))
            continue

        story.append(
            Paragraph(
                f"Unsupported block type: {_replace_inline_markdown(block_type)}",
                styles["ReportMuted"]
            )
        )
        story.append(Spacer(1, 8))

    pdf_buffer = BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=str(resolve("{{placeholders.report_title}}") or "Pentest Report"),
        author=company_name
    )
    doc.build(story, onFirstPage=draw_cover_page, onLaterPages=draw_body_page)
    pdf_buffer.seek(0)
    return pdf_buffer.read()
