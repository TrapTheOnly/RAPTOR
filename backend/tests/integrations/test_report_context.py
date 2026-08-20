from app.integrations.reporting.report_context import (
    UnknownTokenError,
    compute_metrics,
    context_from_host_record,
    lint_template_tokens,
    normalize_finding,
    resolve_placeholders_strict,
    sample_report_context,
    token_flat_context,
)
from app.integrations.reporting.report_context_builder import build_sheet_context, export_cap_error
from app.integrations.reporting.report_pdf_render import render_pentest_report_pdf
from app.domain.offsec.shared import normalize_report_template_payload


def test_occurrence_metrics_split_open_and_fixed():
    findings = [
        normalize_finding(
            {
                "title": "XSS",
                "baseScore": 9.1,
                "occurrences": [
                    {"dns_name": "a", "environment_slug": "prod", "status": "open"},
                    {"dns_name": "b", "environment_slug": "stg", "status": "fixed"},
                ],
            }
        ),
        normalize_finding(
            {
                "title": "Info",
                "baseScore": 3.1,
                "occurrences": [{"dns_name": "c", "environment_slug": "qa", "status": "accepted"}],
            }
        ),
    ]
    metrics, severity, occ = compute_metrics(findings, host_count=3)
    assert metrics["vulnerability_count"] == 2
    assert metrics["critical_count"] == 1
    assert metrics["open_like_count"] == 1
    assert metrics["occurrence_fixed"] == 1
    assert metrics["occurrence_accepted"] == 1
    assert metrics["fixed_findings"] == 1
    assert severity["Critical"] == 1
    assert occ["open"] == 1


def test_host_context_does_not_use_vulnerability_fixed_flag():
    context = context_from_host_record(
        {
            "name": "api.example.com",
            "ip_address": "10.0.0.2",
            "application_name": "API",
            "vulnerability_fixed": 1,
            "vulnerabilities": [
                {
                    "title": "SQLi",
                    "baseScore": 9.8,
                    "status": "open",
                    "occurrences": [{"dns_name": "api.example.com", "environment_slug": "prod", "status": "open"}],
                }
            ],
        }
    )
    assert context["metrics"]["open_like_count"] == 1
    assert context["metrics"]["fixed_findings"] == 0
    assert "ip_address" in context["record"]
    assert context["scope"] == "host"


def test_sheet_context_has_no_host_ip_requirement():
    context = build_sheet_context(
        scope="application",
        package="owner_delivery",
        app={"id": 1, "name": "Payments", "roe_link": "https://roe"},
        selected_envs=[{"id": 9, "slug": "prod", "is_production": True}],
        packed_findings=[
            {
                "id": "f1",
                "title": "CORS",
                "baseScore": 7.1,
                "occurrences": [{"dns_name": "www", "environment_slug": "prod", "status": "open"}],
                "also_observed": [],
            }
        ],
        username="alice",
        watermark="PRODUCTION",
        content_hash="abc",
        signature="sig",
    )
    assert context["record"]["ip_address"] == ""
    assert context["record"]["name"] == "Payments"
    assert "PRODUCTION" not in context["record"]["name"]
    assert context["export"]["watermark"] == "PRODUCTION"
    assert context["findings"][0]["title"] == "CORS"
    assert "Hosts:" not in context["findings"][0]["description"]


def test_retest_pack_sample_omits_fixed():
    context = sample_report_context("retest_pack")
    statuses = {
        occ["status"]
        for finding in context["findings"]
        for occ in finding["occurrences"]
    }
    assert "fixed" not in statuses


def test_unknown_token_lints_and_raises():
    payload = {
        "key": "tok",
        "name": "Tok",
        "template": {
            "blocks": [{"type": "text", "title": "X", "content": "{{not.a.token}}"}],
        },
    }
    _normalized, error = normalize_report_template_payload(payload)
    assert error and "Unknown template token" in error

    flat = token_flat_context(sample_report_context("host"))
    try:
        resolve_placeholders_strict("{{missing.thing}}", flat)
        assert False, "expected UnknownTokenError"
    except UnknownTokenError:
        pass


def test_layout_stripped_and_unknown_chart_rejected():
    payload = {
        "key": "lay",
        "name": "Lay",
        "template": {
            "blocks": [
                {
                    "type": "chart",
                    "title": "Severity",
                    "chart": "vulnerability_severity",
                    "layout": {"x": 0, "y": 0, "w": 6, "h": 4},
                    "_uiId": "gone",
                }
            ]
        },
    }
    normalized, error = normalize_report_template_payload(payload)
    assert error is None
    import json

    parsed = json.loads(normalized["template_json"])
    assert "layout" not in parsed["blocks"][0]
    assert "_uiId" not in parsed["blocks"][0]

    bad = {
        "key": "badchart",
        "name": "Bad",
        "template": {"blocks": [{"type": "chart", "title": "X", "chart": "rainbow_pie"}]},
    }
    _normalized, error = normalize_report_template_payload(bad)
    assert error and "Unknown chart" in error


def test_export_cap_fails_loud():
    error, status = export_cap_error(201)
    assert status == 400
    assert "200" in error["error"]
    assert export_cap_error(10) is None


def test_sample_env_and_wave_kinds_set_scope():
    env_ctx = sample_report_context("env")
    assert env_ctx["scope"] == "environment"
    assert env_ctx["package"] == "owner_delivery"
    wave_ctx = sample_report_context("wave")
    assert wave_ctx["scope"] == "wave"
    assert wave_ctx["wave"]["name"]
    archive = sample_report_context("wave_archive")
    assert archive["package"] == "wave_archive"
    assert archive["scope"] == "wave"


def test_render_unknown_token_errors():
    template = {
        "version": 1,
        "branding": {"company_name": "Acme", "primary_color": "#067A8A", "accent_color": "#1E293B"},
        "placeholders": {"report_title": "Report"},
        "blocks": [{"type": "text", "title": "Nope", "content": "{{definitely.missing}}"}],
    }
    try:
        render_pentest_report_pdf(sample_report_context("host"), template, checklist_templates=[])
        assert False, "expected unknown token to raise"
    except UnknownTokenError:
        pass


def test_render_app_context_keeps_hosts_out_of_description():
    context = build_sheet_context(
        scope="application",
        package="owner_delivery",
        app={"id": 1, "name": "Payments"},
        selected_envs=[{"id": 9, "slug": "prod", "is_production": True}],
        packed_findings=[
            {
                "id": "f1",
                "title": "CORS",
                "description": "Origin reflection.",
                "baseScore": 7.1,
                "occurrences": [{"dns_name": "www.pay.example", "environment_slug": "prod", "status": "open"}],
                "also_observed": [],
            }
        ],
        username="alice",
        watermark="PRODUCTION",
        content_hash="deadbeef",
        signature="cafebabe",
    )
    template = {
        "version": 1,
        "branding": {"company_name": "Acme", "primary_color": "#067A8A", "accent_color": "#1E293B"},
        "placeholders": {"report_title": "Report"},
        "blocks": [
            {"type": "cover", "title": "{{report_title}}", "show_logo": False},
            {"type": "vulnerabilities", "title": "Findings", "include_descriptions": True},
        ],
    }
    pdf_bytes = render_pentest_report_pdf(context, template, checklist_templates=[])
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 500
    assert "Hosts:" not in context["findings"][0]["description"]
    assert context["export"]["watermark"] == "PRODUCTION"


def test_split_finding_narrative_strips_host_wave_auth_and_keeps_sections():
    from app.integrations.reporting.report_context import split_finding_narrative

    description, impact, evidence, remediation = split_finding_narrative(
        {
            "description": (
                "Password reset is weak.\n"
                "**Host:** `auth.atlas-iam.corp`\n"
                "**Wave:** FY26 Q3 — Live\n"
                "**Auth context:** reset token\n\n"
                "### Impact\n\n"
                "Confirmed in QA.\n\n"
                "**Evidence**\n\n"
                "Request replayed without MFA.\n\n"
                "## Remediation\n\n"
                "Raise the password floor."
            ),
            "occurrences": [{"dns": "auth.atlas-iam.corp", "evidence_note": "Screenshot on the finding."}],
        }
    )
    assert "Host:" not in description
    assert "Wave:" not in description
    assert "Auth context:" not in description
    assert "Password reset is weak." in description
    assert impact == "Confirmed in QA."
    assert "Request replayed without MFA." in evidence
    assert "Screenshot on the finding." in evidence
    assert remediation == "Raise the password floor."


def test_sheet_prepared_by_lists_finding_people_not_exporter():
    context = build_sheet_context(
        scope="wave",
        package="wave_archive",
        app={"id": 1, "name": "Atlas IAM"},
        selected_envs=[{"id": 9, "slug": "prod", "is_production": True}],
        packed_findings=[
            {
                "id": "f1",
                "title": "SQLi",
                "description": "Union select.",
                "created_by": "alice",
                "collaborators": ["bob"],
                "baseScore": 9.1,
                "occurrences": [{"dns_name": "jobs.atlas-iam.corp", "environment_slug": "prod", "status": "retest"}],
            }
        ],
        username="awadmin",
        watermark="NON-PROD",
        wave={"id": 4, "name": "FY26 Q3 — Live"},
    )
    assert "alice" in context["pentest"]["tested_by"]
    assert "bob" in context["pentest"]["tested_by"]
    assert context["pentest"]["tested_by"] != "awadmin"
    assert "August" in context["generated_at"] or context["generated_at"].split()[1].isalpha()
    assert ":" not in context["generated_at"]


def test_canonical_template_accepts_table_of_contents():
    from app.domain.catalogs.report_template_catalog import DEFAULT_REPORT_TEMPLATE
    from app.integrations.reporting.report_pdf_blocks import ensure_report_blocks

    types = [block["type"] for block in DEFAULT_REPORT_TEMPLATE["blocks"]]
    assert "table_of_contents" in types
    injected = ensure_report_blocks(
        [
            {"type": "cover", "title": "Report"},
            {"type": "engagement_overview", "title": "Overview"},
            {"type": "key_metrics", "title": "Risk"},
            {"type": "chart", "title": "Severity", "chart": "vulnerability_severity"},
        ]
    )
    assert [block["type"] for block in injected].count("table_of_contents") == 1
    payload = {
        "key": "toc",
        "name": "Toc",
        "template": {"blocks": [{"type": "table_of_contents", "title": "Contents"}]},
    }
    _normalized, error = normalize_report_template_payload(payload)
    assert error is None
