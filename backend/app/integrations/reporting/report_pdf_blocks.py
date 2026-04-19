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
        story.append(Spacer(1, 22 * mm))

        if raw_block.get("show_logo") and logo_url:
            logo_image = get_embedded_image_fn(
                resolve(logo_url),
                target_width_mm=35.6,
                max_width_mm=35.6,
                max_height_mm=30,
                centered=True,
            )
            if logo_image:
                story.append(logo_image)
                story.append(Spacer(1, 5 * mm))

        story.append(
            Paragraph(
                f"<b>{replace_inline_markdown(company_name or 'Security Operations')}</b>",
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

        prepared_for = resolve(context.get("placeholders", {}).get("prepared_for", "{{record.name}}"))
        prepared_by = resolve(context.get("placeholders", {}).get("prepared_by", "{{pentest.tested_by}}"))

        generated_by = context.get("generated_by", "")
        assignee = context.get("pentest", {}).get("tested_by", "")
        collaborator_usernames = model.get("collaborator_usernames", [])

        if generated_by and generated_by != assignee:
            display_prepared_by = generated_by
        else:
            display_prepared_by = prepared_by or "N/A"

        meta_rows = [
            [
                Paragraph("Prepared For", styles["ReportCoverMetaLabel"]),
                Paragraph(replace_inline_markdown(prepared_for or "N/A"), styles["ReportCoverMetaValue"]),
            ],
            [
                Paragraph("Prepared By", styles["ReportCoverMetaLabel"]),
                Paragraph(replace_inline_markdown(display_prepared_by or "N/A"), styles["ReportCoverMetaValue"]),
            ],
        ]

        if generated_by and generated_by != assignee:
            meta_rows.append(
                [
                    Paragraph("Assignee", styles["ReportCoverMetaLabel"]),
                    Paragraph(replace_inline_markdown(assignee or "Unassigned"), styles["ReportCoverMetaValue"]),
                ]
            )

        if collaborator_usernames:
            display_collaborators = generated_by if (generated_by and generated_by != assignee) else None
            collab_names = list(collaborator_usernames)
            if display_collaborators and display_collaborators not in collab_names:
                collab_names.append(display_collaborators)
            meta_rows.append(
                [
                    Paragraph("Collaborators", styles["ReportCoverMetaLabel"]),
                    Paragraph(replace_inline_markdown(", ".join(collab_names)), styles["ReportCoverMetaValue"]),
                ]
            )

        meta_rows.extend(
            [
                [
                    Paragraph("Application", styles["ReportCoverMetaLabel"]),
                    Paragraph(
                        replace_inline_markdown(resolve("{{record.application_name}}") or "N/A"),
                        styles["ReportCoverMetaValue"],
                    ),
                ],
                [
                    Paragraph("Generated", styles["ReportCoverMetaLabel"]),
                    Paragraph(replace_inline_markdown(context["generated_at"]), styles["ReportCoverMetaValue"]),
                ],
            ]
        )
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
                styles["ReportMutedCenter"],
            )
        )
        story.append(PageBreak())
        return

    if title:
        story.append(section_title_fn(title))
        story.append(Spacer(1, 4))

    if block_type == "engagement_overview":
        collaborator_list = resolve("{{pentest.collaborators}}")
        rows = [
            ["Field", "Value"],
            ["Target", resolve("{{record.name}}") or "N/A"],
            ["IP Address", resolve("{{record.ip_address}}") or "N/A"],
            ["Source", resolve("{{record.source}}") or "N/A"],
            ["Application", resolve("{{record.application_name}}") or "N/A"],
            ["Assigned Tester", resolve("{{pentest.tested_by}}") or "Unassigned"],
        ]
        if collaborator_list:
            rows.append(["Collaborators", collaborator_list])
        rows.extend(
            [
                ["Status", resolve("{{pentest.status}}") or "Not Started"],
                ["Start Date", resolve("{{pentest.test_start_date}}") or "N/A"],
                ["End Date", resolve("{{pentest.test_end_date}}") or "N/A"],
                ["Service Desk Link", resolve("{{pentest.service_desk_link}}") or "N/A"],
            ]
        )
        story.append(table_with_style_fn(rows, [55 * mm, 123 * mm]))
        story.append(Spacer(1, 8))
        return

    if block_type == "key_metrics":
        metrics = [
            ("Total Findings", resolve("{{metrics.vulnerability_count}}")),
            ("Critical Findings", resolve("{{metrics.critical_count}}")),
            ("High Findings", resolve("{{metrics.high_count}}")),
            ("Open Findings", resolve("{{metrics.open_findings}}")),
            ("Fixed Findings", resolve("{{metrics.fixed_findings}}")),
            ("Open Ports", resolve("{{metrics.open_ports_count}}")),
            ("Checklist Completed", resolve("{{metrics.checklist_completed}}")),
            ("Checklist Coverage", f"{resolve('{{metrics.checklist_percentage}}')}%"),
        ]
        story.append(metric_tiles_fn(metrics, columns=4))
        story.append(Spacer(1, 8))
        return

    if block_type == "chart":
        chart_type = str(raw_block.get("chart", "")).strip().lower()
        if chart_type == "vulnerability_severity":
            chart = build_bar_chart_fn(model["severity_counts"])
            chart_caption = "Distribution of findings by severity."
        elif chart_type == "checklist_completion":
            chart = build_pie_chart_fn(
                {
                    "Completed": context["metrics"]["checklist_completed"],
                    "Irrelevant": context["metrics"]["checklist_irrelevant"],
                    "Unstarted": context["metrics"]["checklist_unstarted"],
                }
            )
            chart_caption = "Checklist completion breakdown."
        elif chart_type == "vulnerability_fix_status":
            chart = build_pie_chart_fn(
                {
                    "Open": context["metrics"]["open_findings"],
                    "Fixed": context["metrics"]["fixed_findings"],
                }
            )
            chart_caption = "Open versus remediated findings."
        else:
            chart = build_pie_chart_fn({"Unsupported": 1})
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
        return

    if block_type == "open_ports":
        if model["open_ports"]:
            rows = [["Port", "Likely Service"]]
            for port in model["open_ports"]:
                rows.append([str(port), build_service_name(port)])
            story.append(table_with_style_fn(rows, [36 * mm, 142 * mm]))
        else:
            story.append(Paragraph("No open ports recorded.", styles["ReportMuted"]))
        story.append(Spacer(1, 8))
        return

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
        story.extend(markdown_to_flowables_fn(resolve(field_value)))
        story.append(Spacer(1, 8))
        return

    if block_type == "checklists":
        rows = [["Checklist", "Service", "Completed", "Irrelevant", "Unstarted", "Total", "Completion %"]]
        for item in model["checklist_progress_rows"]:
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
            story.append(Paragraph("No checklist coverage recorded.", styles["ReportMuted"]))
        else:
            story.append(table_with_style_fn(rows, [56 * mm, 19 * mm, 18 * mm, 20 * mm, 20 * mm, 14 * mm, 31 * mm]))
        story.append(Spacer(1, 8))
        return

    if block_type == "vulnerabilities":
        include_descriptions = bool(raw_block.get("include_descriptions", True))
        if not model["vulnerabilities"]:
            story.append(Paragraph("No vulnerabilities recorded.", styles["ReportMuted"]))
            story.append(Spacer(1, 8))
            return

        for index, vuln in enumerate(model["vulnerabilities"], start=1):
            category_name = str(vuln.get("categoryName", "")).strip() or f"Finding {index}"
            base_score = to_float(vuln.get("baseScore"), 0.0)
            severity = severity_from_score(base_score)
            severity_color = severity_colors.get(severity, styles["ReportMuted"].textColor)

            finding_header = Paragraph(
                f"<b>{index}. {replace_inline_markdown(category_name)}</b>",
                styles["ReportFindingTitle"],
            )
            severity_label = Paragraph(
                f"<b><font color='{severity_color_hex.get(severity, '#475569')}'>"
                f"{severity} | CVSS {base_score:.1f}</font></b>",
                styles["ReportMutedCenter"],
            )

            # Keep header in a compact card, but render long body content outside the table
            # so reportlab can paginate naturally for large findings and images.
            finding_header_table = Table(
                [[finding_header, severity_label]],
                colWidths=[130 * mm, 48 * mm],
                hAlign="LEFT",
            )
            finding_header_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                        ("BOX", (0, 0), (-1, -1), 0.7, border_color),
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

            metrics = vuln.get("metrics")
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

            if include_descriptions:
                description = vuln.get("description", "")
                story.append(Spacer(1, 4))
                story.extend(markdown_to_flowables_fn(description))
            story.append(Spacer(1, 7))
        return

    if block_type == "text":
        body = resolve(raw_block.get("content", ""))
        story.extend(markdown_to_flowables_fn(body))
        story.append(Spacer(1, 8))
        return

    story.append(
        Paragraph(
            f"Unsupported block type: {replace_inline_markdown(block_type)}",
            styles["ReportMuted"],
        )
    )
    story.append(Spacer(1, 8))


__all__ = ["append_story_block"]
