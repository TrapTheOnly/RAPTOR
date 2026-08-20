from app.integrations.reporting.report_context import (
    SEVERITY_CELL_HEX,
    SEVERITY_PRINT_HEX,
    STATUS_GLYPHS,
    STATUS_LABELS,
    UnknownBlockError,
    UnknownChartError,
    collect_involved_people,
    severity_by_env_counts,
    split_finding_narrative,
)

COVER_LOGO_WIDTH_MM = 105
COVER_LOGO_MAX_HEIGHT_MM = 48
CHART_PAGE_IDS = {"vulnerability_severity", "occurrence_status", "vulnerability_fix_status"}


def _scope(model):
    payload = model.get("report_context") or {}
    return str(payload.get("scope") or model.get("context", {}).get("scope") or "")


def _is_host_scope(model):
    return _scope(model) == "host"


def _wants_field(block, key):
    raw = block.get("fields") if isinstance(block, dict) else None
    if not isinstance(raw, list) or not raw:
        return True
    wanted = {str(item).strip() for item in raw if str(item).strip()}
    return key in wanted


def _block_type(block):
    if not isinstance(block, dict):
        return ""
    return str(block.get("type") or "").strip().lower()


def ensure_report_blocks(blocks):
    flow = [item for item in (blocks or []) if isinstance(item, dict)]
    types = [_block_type(item) for item in flow]
    if "table_of_contents" not in types:
        insert_at = None
        for index, block_type in enumerate(types):
            if block_type == "key_metrics":
                insert_at = index + 1
            elif block_type == "engagement_overview" and insert_at is None:
                insert_at = index + 1
        if insert_at is None:
            insert_at = 1 if types[:1] == ["cover"] else 0
        flow.insert(insert_at, {"type": "table_of_contents", "title": "Table of Contents"})
    return flow


def _prepared_by_label(context, model):
    findings = (model or {}).get("findings") or (context or {}).get("findings") or []
    return collect_involved_people(context, findings) or "N/A"


def append_story_block(
    story,
    raw_block,
    *,
    resolve,
    context,
    model,
    styles,
    mm,
    PageBreak,
    Spacer,
    Paragraph,
    Table,
    TableStyle,
    colors,
    border_color,
    severity_color_hex,
    severity_colors,
    company_name,
    logo_url,
    get_embedded_image_fn,
    section_title_fn,
    table_with_style_fn,
    metric_tiles_fn,
    markdown_to_flowables_fn,
    build_bar_chart_fn,
    build_pie_chart_fn,
    build_service_name,
    replace_inline_markdown,
    to_float,
    severity_from_score,
):
    if not isinstance(raw_block, dict):
        return

    block_type = str(raw_block.get("type", "")).strip().lower()
    title = resolve(raw_block.get("title", ""))

    if block_type == "page_break":
        story.append(PageBreak())
        return

    if block_type == "cover":
        story.append(Spacer(1, 10 * mm))

        if raw_block.get("show_logo") and logo_url:
            logo_image = get_embedded_image_fn(
                resolve(logo_url),
                target_width_mm=COVER_LOGO_WIDTH_MM,
                max_width_mm=COVER_LOGO_WIDTH_MM,
                max_height_mm=COVER_LOGO_MAX_HEIGHT_MM,
                centered=True,
            )
            if logo_image:
                story.append(logo_image)
                story.append(Spacer(1, 5 * mm))

        story.append(
            Paragraph(
                replace_inline_markdown(company_name or "Security Operations"),
                styles["ReportCoverCompany"],
            )
        )
        story.append(Spacer(1, 5 * mm))

        story.append(
            Paragraph(
                replace_inline_markdown(title or "Penetration Test Report"),
                styles["ReportCoverTitle"],
            )
        )
        subtitle = resolve(raw_block.get("subtitle", ""))
        if subtitle:
            story.append(Paragraph(replace_inline_markdown(subtitle), styles["ReportCoverSub"]))
            story.append(Spacer(1, 8 * mm))

        prepared_for_default = (
            "{{record.name}}" if _is_host_scope(model) else "{{application.name}}"
        )
        prepared_for = resolve(context.get("placeholders", {}).get("prepared_for", prepared_for_default))
        display_prepared_by = _prepared_by_label(context, model)
        watermark = str((context.get("export") or {}).get("watermark") or "")
        generated_label = context.get("generated_date") or context.get("generated_at") or ""

        meta_rows = [
            [
                Paragraph("Prepared For", styles["ReportCoverMetaLabel"]),
                Paragraph(replace_inline_markdown(prepared_for or "N/A"), styles["ReportCoverMetaValue"]),
            ],
            [
                Paragraph("Prepared By", styles["ReportCoverMetaLabel"]),
                Paragraph(replace_inline_markdown(display_prepared_by), styles["ReportCoverMetaValue"]),
            ],
        ]
        if watermark:
            meta_rows.append(
                [
                    Paragraph("Classification", styles["ReportCoverMetaLabel"]),
                    Paragraph(replace_inline_markdown(watermark), styles["ReportCoverMetaValue"]),
                ]
            )
        meta_rows.append(
            [
                Paragraph("Generated", styles["ReportCoverMetaLabel"]),
                Paragraph(replace_inline_markdown(generated_label), styles["ReportCoverMetaValue"]),
            ]
        )
        meta_table = Table(meta_rows, colWidths=[42 * mm, 92 * mm], hAlign="CENTER")
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.4, border_color),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, border_color),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(Spacer(1, 9 * mm))
        story.append(meta_table)
        story.append(PageBreak())
        return

    if title:
        story.append(section_title_fn(title))
        story.append(Spacer(1, 4))

    if block_type == "engagement_overview":
        if _is_host_scope(model):
            collaborator_list = resolve("{{pentest.collaborators}}")
            rows = [["Field", "Value"]]
            if _wants_field(raw_block, "target"):
                rows.append(["Target", resolve("{{record.name}}") or "N/A"])
            if _wants_field(raw_block, "ip"):
                rows.append(["IP Address", resolve("{{record.ip_address}}") or "N/A"])
            if _wants_field(raw_block, "source"):
                rows.append(["Source", resolve("{{record.source}}") or "N/A"])
            if _wants_field(raw_block, "application"):
                rows.append(["Application", resolve("{{record.application_name}}") or "N/A"])
            if _wants_field(raw_block, "tester"):
                rows.append(["Assigned Tester", _prepared_by_label(context, model)])
            if _wants_field(raw_block, "collaborators") and collaborator_list:
                rows.append(["Collaborators", collaborator_list])
            if _wants_field(raw_block, "status"):
                rows.append(["Status", resolve("{{pentest.status}}") or "Not Started"])
            if _wants_field(raw_block, "dates"):
                rows.append(["Start Date", resolve("{{pentest.test_start_date}}") or "N/A"])
                rows.append(["End Date", resolve("{{pentest.test_end_date}}") or "N/A"])
            if _wants_field(raw_block, "service_desk"):
                rows.append(["Service Desk Link", resolve("{{pentest.service_desk_link}}") or "N/A"])
        else:
            env_names = ", ".join(
                str(env.get("slug") or "")
                for env in (model.get("report_context") or {}).get("environments") or []
                if env.get("slug")
            )
            host_count = resolve("{{metrics.host_count}}") or "0"
            rows = [["Field", "Value"]]
            if _wants_field(raw_block, "application"):
                rows.append(["Application", resolve("{{application.name}}") or "N/A"])
            if _wants_field(raw_block, "environments"):
                rows.append(["Environments", env_names or "N/A"])
            if _wants_field(raw_block, "hosts"):
                rows.append(["Hosts in scope", str(host_count)])
            if _wants_field(raw_block, "tester"):
                rows.append(["Prepared By", _prepared_by_label(context, model)])
            wave_name = resolve("{{wave.name}}")
            if _wants_field(raw_block, "wave") and wave_name:
                rows.append(["Wave", wave_name])
            watermark = str((context.get("export") or {}).get("watermark") or "")
            if _wants_field(raw_block, "classification") and watermark:
                rows.append(["Classification", watermark])
        if len(rows) > 1:
            story.append(table_with_style_fn(rows, [55 * mm, 123 * mm]))
            story.append(Spacer(1, 8))
        return

    if block_type == "key_metrics":
        metrics = []
        if _wants_field(raw_block, "findings"):
            metrics.append(("Total Findings", resolve("{{metrics.vulnerability_count}}")))
        if _wants_field(raw_block, "critical"):
            metrics.append(("Critical Findings", resolve("{{metrics.critical_count}}")))
        if _wants_field(raw_block, "high"):
            metrics.append(("High Findings", resolve("{{metrics.high_count}}")))
        if _wants_field(raw_block, "open_like"):
            metrics.append(("Open-like", resolve("{{metrics.open_like_count}}") or resolve("{{metrics.open_findings}}")))
        if _wants_field(raw_block, "fixed"):
            metrics.append(("Fixed", resolve("{{metrics.occurrence_fixed}}") or resolve("{{metrics.fixed_findings}}")))
        if _wants_field(raw_block, "hosts"):
            metrics.append(("Hosts", resolve("{{metrics.host_count}}")))
        if _wants_field(raw_block, "ports") and _is_host_scope(model) and to_float(resolve("{{metrics.open_ports_count}}") or 0, 0) > 0:
            metrics.append(("Open Ports", resolve("{{metrics.open_ports_count}}")))
        if _wants_field(raw_block, "checklist") and to_float(resolve("{{metrics.checklist_total}}") or 0, 0) > 0:
            metrics.append(("Checklist Coverage", f"{resolve('{{metrics.checklist_percentage}}')}%"))
        if not metrics:
            return
        story.append(metric_tiles_fn(metrics, columns=min(4, len(metrics))))
        story.append(Spacer(1, 8))
        return

    if block_type == "table_of_contents":
        findings = model.get("findings") or []
        rows = [["#", "Finding", "Severity"]]
        extra_commands = [("ALIGN", (0, 0), (0, -1), "CENTER"), ("ALIGN", (2, 0), (2, -1), "CENTER")]
        if not findings:
            rows.append(["—", "No findings in this scope.", "—"])
        else:
            for index, finding in enumerate(findings, start=1):
                finding_title = str(finding.get("title") or finding.get("category") or f"Finding {index}").strip()
                severity = severity_from_score(to_float(finding.get("baseScore"), 0.0))
                fill_hex, ink_hex = SEVERITY_CELL_HEX.get(severity, ("#E2E8F0", "#111827"))
                rows.append(
                    [
                        str(index),
                        finding_title,
                        Paragraph(
                            f"<font color='{ink_hex}'><b>{severity}</b></font>",
                            styles["ReportTableCellCenter"],
                        ),
                    ]
                )
                extra_commands.extend(
                    [
                        ("BACKGROUND", (2, index), (2, index), colors.HexColor(fill_hex)),
                        ("VALIGN", (2, index), (2, index), "MIDDLE"),
                    ]
                )
        story.append(table_with_style_fn(rows, [14 * mm, 124 * mm, 40 * mm], extra_commands=extra_commands))
        story.append(Spacer(1, 8))
        return

    if block_type == "chart":
        chart_type = str(raw_block.get("chart", "")).strip().lower()
        report_context = model.get("report_context") or {}
        if chart_type == "vulnerability_severity":
            ordered = ["Critical", "High", "Medium", "Low", "Informational"]
            data = {key: model["severity_counts"].get(key, 0) for key in ordered}
            bar_colors = [colors.HexColor(SEVERITY_PRINT_HEX[key]) for key in ordered]
            chart = build_bar_chart_fn(data, bar_colors=bar_colors)
            chart_caption = "Distribution of findings by severity."
        elif chart_type in {"occurrence_status", "vulnerability_fix_status"}:
            counts = model.get("occurrence_counts") or {}
            data = {STATUS_LABELS[key]: counts.get(key, 0) for key in STATUS_LABELS}
            chart = build_bar_chart_fn(data)
            chart_caption = "Occurrence status across in-scope hosts."
        elif chart_type == "checklist_completion":
            completed = context["metrics"].get("checklist_completed") or 0
            irrelevant = context["metrics"].get("checklist_irrelevant") or 0
            unstarted = context["metrics"].get("checklist_unstarted") or 0
            if not (completed or irrelevant or unstarted):
                return
            chart = build_bar_chart_fn(
                {"Completed": completed, "Unstarted": unstarted, "Irrelevant": irrelevant}
            )
            chart_caption = "Checklist completion breakdown."
        elif chart_type == "severity_by_env":
            by_env = severity_by_env_counts(model.get("findings") or [])
            if not by_env:
                return
            data = {
                env: sum(counts.values())
                for env, counts in sorted(by_env.items(), key=lambda item: item[0])
            }
            chart = build_bar_chart_fn(data)
            chart_caption = "Findings by environment."
        elif chart_type == "wave_coverage":
            wave = (report_context.get("wave") or {})
            if not wave.get("id") and not wave.get("name"):
                return
            data = {
                "Hosts": context["metrics"].get("host_count") or 0,
                "Findings": context["metrics"].get("vulnerability_count") or 0,
            }
            chart = build_bar_chart_fn(data)
            chart_caption = "Wave coverage: hosts in snapshot versus findings."
        else:
            raise UnknownChartError(f"Unknown chart: {chart_type or '(empty)'}")

        chart_card = Table([[chart]], colWidths=[178 * mm], hAlign="LEFT")
        chart_card.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.4, border_color),
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
        return

    if block_type == "open_ports":
        if not model.get("open_ports"):
            return
        rows = [["Port", "Likely Service"]]
        for port in model["open_ports"]:
            rows.append([str(port), build_service_name(port)])
        story.append(table_with_style_fn(rows, [36 * mm, 142 * mm]))
        story.append(Spacer(1, 8))
        return

    if block_type == "markdown":
        field = str(raw_block.get("field", "")).strip().lower()
        field_value = ""
        if field in {"description", "record_description"}:
            field_value = context.get("record", {}).get("description") or ""
        elif field in {"notes", "security_details"}:
            field_value = context.get("pentest", {}).get("notes") or ""
        elif field in {"service_desk_link"}:
            field_value = context.get("pentest", {}).get("service_desk_link") or ""
        elif field in {"open_ports"}:
            field_value = context.get("pentest", {}).get("open_ports") or ""
        if not str(field_value or "").strip():
            return
        story.extend(markdown_to_flowables_fn(resolve(field_value)))
        story.append(Spacer(1, 8))
        return

    if block_type == "checklists":
        rows = [["Checklist", "Service", "Completed", "Irrelevant", "Unstarted", "Total", "Completion %"]]
        for item in model.get("checklist_progress_rows") or []:
            rows.append(
                [
                    item["name"],
                    str(item["service"]).upper() if item["service"] else "N/A",
                    str(item["completed"]),
                    str(item["irrelevant"]),
                    str(item["unstarted"]),
                    str(item["total"]),
                    f"{item['percentage']}%",
                ]
            )
        if len(rows) == 1:
            return
        story.append(table_with_style_fn(rows, [56 * mm, 19 * mm, 18 * mm, 20 * mm, 20 * mm, 14 * mm, 31 * mm]))
        story.append(Spacer(1, 8))
        return

    if block_type == "vulnerabilities":
        include_descriptions = bool(raw_block.get("include_descriptions", True))
        findings = model.get("findings") or model.get("vulnerabilities") or []
        if not findings:
            story.append(Paragraph("No findings in this scope.", styles["ReportMuted"]))
            story.append(Spacer(1, 8))
            return

        for index, finding in enumerate(findings, start=1):
            if index > 1:
                story.append(PageBreak())
            title_text = str(finding.get("title") or finding.get("categoryName") or f"Finding {index}").strip()
            base_score = to_float(finding.get("baseScore"), 0.0)
            severity = severity_from_score(base_score)
            severity_color = severity_colors.get(severity, styles["ReportMuted"].textColor)

            finding_header = Paragraph(
                f"<b>{index}. {replace_inline_markdown(title_text)}</b>",
                styles["ReportFindingTitle"],
            )
            severity_label = Paragraph(
                f"<b><font color='{severity_color_hex.get(severity, '#5A6472')}'>"
                f"{severity} | CVSS {base_score:.1f}</font></b>",
                styles["ReportMutedCenter"],
            )

            finding_header_table = Table(
                [[finding_header, severity_label]],
                colWidths=[130 * mm, 48 * mm],
                hAlign="LEFT",
            )
            finding_header_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.4, border_color),
                        ("LINEBEFORE", (0, 0), (0, 0), 3, severity_color),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(finding_header_table)

            metrics = finding.get("metrics")
            if isinstance(metrics, dict) and metrics:
                ordered = ["AV", "AC", "PR", "UI", "S", "C", "I", "A"]
                metric_parts = [
                    f"{metric}:{metrics.get(metric, '')}"
                    for metric in ordered
                    if metrics.get(metric) is not None and metrics.get(metric) != ""
                ]
                if metric_parts:
                    story.append(Spacer(1, 2))
                    story.append(
                        Paragraph(
                            f"CVSS Vector: {replace_inline_markdown('/'.join(metric_parts))}",
                            styles["ReportMuted"],
                        )
                    )

            occurrences = finding.get("occurrences") or []
            if occurrences:
                occ_rows = [["", "Host", "Environment", "Status"]]
                for occ in occurrences:
                    status = str(occ.get("status") or "open")
                    glyph = STATUS_GLYPHS.get(status, STATUS_GLYPHS["open"])
                    occ_rows.append(
                        [
                            glyph,
                            occ.get("dns") or str(occ.get("record_id") or ""),
                            occ.get("env") or occ.get("env_name") or "",
                            STATUS_LABELS.get(status, status),
                        ]
                    )
                story.append(Spacer(1, 4))
                story.append(table_with_style_fn(occ_rows, [10 * mm, 78 * mm, 45 * mm, 45 * mm]))
            also = finding.get("also_observed") or []
            if also:
                names = ", ".join(str(item.get("dns") or item.get("record_id") or "") for item in also)
                story.append(Spacer(1, 2))
                story.append(Paragraph(f"Also observed: {replace_inline_markdown(names)}", styles["ReportMuted"]))

            if include_descriptions:
                description, impact, evidence, remediation = split_finding_narrative(finding)
                sections = (
                    ("Description", description),
                    ("Impact", impact),
                    ("Evidence", evidence),
                    ("Remediation", remediation),
                )
                for heading, body in sections:
                    if not str(body or "").strip():
                        continue
                    story.append(Spacer(1, 4))
                    story.append(Paragraph(heading, styles["ReportMarkdownH2"]))
                    story.extend(markdown_to_flowables_fn(body))
            story.append(Spacer(1, 7))
        return

    if block_type == "text":
        body = resolve(raw_block.get("content", ""))
        story.extend(markdown_to_flowables_fn(body))
        story.append(Spacer(1, 8))
        return

    raise UnknownBlockError(f"Unknown block type: {block_type or '(empty)'}")


__all__ = ["append_story_block", "ensure_report_blocks", "CHART_PAGE_IDS"]
