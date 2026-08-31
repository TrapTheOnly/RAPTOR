from app.domain.integrations import fields as field_domain
from app.integrations.secrets import decrypt_secret, encrypt_secret


def test_severity_from_score_bands():
    assert field_domain.severity_from_score(9.8) == "critical"
    assert field_domain.severity_from_score(7.5) == "high"
    assert field_domain.severity_from_score(5.0) == "medium"
    assert field_domain.severity_from_score(2.1) == "low"
    assert field_domain.severity_from_score(0) == "info"


def test_to_adf_splits_paragraphs():
    doc = field_domain.to_adf("one\n\ntwo")
    assert doc["type"] == "doc"
    assert len(doc["content"]) == 3
    assert doc["content"][0]["content"][0]["text"] == "one"
    assert doc["content"][2]["content"][0]["text"] == "two"


def test_parse_jira_fields_skips_system_and_keeps_custom_selects():
    parsed = field_domain.parse_jira_fields(
        {
            "summary": {"name": "Summary", "required": True, "schema": {"type": "string", "system": "summary"}},
            "project": {"name": "Project", "required": True, "schema": {"type": "project", "system": "project"}},
            "customfield_10010": {
                "name": "Dev team",
                "required": True,
                "schema": {"type": "option", "custom": "com.atlassian.jira.plugin.system.customfieldtypes:select"},
                "allowedValues": [{"id": "1", "value": "AppSec"}, {"id": "2", "value": "Platform"}],
            },
            "attachment": {"name": "Attachment", "required": False, "schema": {"type": "array", "system": "attachment"}},
        }
    )
    ids = {item["id"] for item in parsed}
    assert "summary" in ids
    assert "customfield_10010" in ids
    assert "project" not in ids
    assert "attachment" not in ids
    team = next(item for item in parsed if item["id"] == "customfield_10010")
    assert team["type"] == "option"
    assert team["allowed_values"][0]["label"] == "AppSec"


def test_seed_mappings_auto_maps_summary_and_asks_required_custom():
    fields = field_domain.parse_jira_fields(
        {
            "summary": {"name": "Summary", "required": True, "schema": {"type": "string", "system": "summary"}},
            "description": {"name": "Description", "required": True, "schema": {"type": "string", "system": "description"}},
            "customfield_10010": {
                "name": "Dev team",
                "required": True,
                "schema": {"type": "option", "custom": "select"},
                "allowedValues": [{"id": "1", "value": "AppSec"}],
            },
            "labels": {"name": "Labels", "required": False, "schema": {"type": "array", "items": "string", "system": "labels"}},
        }
    )
    mappings = field_domain.seed_mappings("jira", fields)
    by_id = {item["external_field_id"]: item for item in mappings}
    assert by_id["summary"]["fill_mode"] == "mapped"
    assert by_id["summary"]["raptor_field"] == "title"
    assert by_id["description"]["fill_mode"] == "mapped"
    assert by_id["description"]["raptor_field"] == "description,impact,evidence,remediation"
    assert by_id["customfield_10010"]["fill_mode"] == "ask"
    assert by_id["labels"]["fill_mode"] == "mapped"


def test_merge_mappings_keeps_saved_fill_mode_for_known_fields():
    live = [
        {"id": "summary", "name": "Summary", "type": "string", "required": True, "allowed_values": []},
        {"id": "customfield_1", "name": "New", "type": "option", "required": True, "allowed_values": [{"id": "a", "label": "A", "value": "A"}]},
    ]
    saved = [
        {
            "external_field_id": "summary",
            "fill_mode": "static",
            "static_value": "Fixed title",
            "raptor_field": "",
            "external_field_name": "Summary",
            "external_field_type": "string",
            "required": True,
            "allowed_values": [],
        }
    ]
    merged = field_domain.merge_mappings(live, saved, "jira")
    assert merged[0]["fill_mode"] == "static"
    assert merged[0]["static_value"] == "Fixed title"
    assert merged[1]["external_field_id"] == "customfield_1"
    assert merged[1]["fill_mode"] == "ask"


def test_raptor_values_and_jira_payload():
    values = field_domain.raptor_values(
        {
            "finding": {
                "title": "CORS on API",
                "description": "Any origin.",
                "impact": "Tokens leak to a foreign origin.",
                "evidence": "curl with Origin: https://evil.example",
                "remediation": "Echo a strict Access-Control-Allow-Origin.",
                "baseScore": 7.5,
                "categoryName": "CORS",
                "status": "open",
                "created_by": "ada",
                "collaborators": ["ada", "al"],
                "occurrences": [
                    {"dns_name": "api.example.com", "environment_slug": "prod"},
                    {"dns_name": "api-stg.example.com", "environment_slug": "stg"},
                ],
            },
            "application": {"name": "Payments"},
            "wave": {"name": "FY26 Q1"},
            "found_here": {"name": "api.example.com"},
        }
    )
    assert values["severity"] == "high"
    assert values["hosts"] == "api.example.com, api-stg.example.com"
    assert values["impact"] == "Tokens leak to a foreign origin."
    assert values["evidence"] == "curl with Origin: https://evil.example"
    assert values["remediation"] == "Echo a strict Access-Control-Allow-Origin."
    assert "impact" in {item["id"] for item in field_domain.RAPTOR_FIELDS}
    assert "evidence" in {item["id"] for item in field_domain.RAPTOR_FIELDS}
    assert "remediation" in {item["id"] for item in field_domain.RAPTOR_FIELDS}
    mappings = [
        {
            "external_field_id": "summary",
            "external_field_type": "string",
            "fill_mode": "mapped",
            "raptor_field": "title",
            "required": True,
        },
        {
            "external_field_id": "priority",
            "external_field_type": "priority",
            "fill_mode": "mapped",
            "raptor_field": "severity",
            "required": False,
            "allowed_values": [{"id": "2", "label": "High", "value": "High"}],
        },
        {
            "external_field_id": "customfield_10010",
            "external_field_name": "Dev team",
            "external_field_type": "option",
            "fill_mode": "ask",
            "required": True,
            "allowed_values": [{"id": "9", "label": "AppSec", "value": "AppSec"}],
        },
    ]
    fields, errors = field_domain.build_jira_issue_fields(
        mappings, values, {"customfield_10010": "AppSec"}, "SEC", "10001", adf=True
    )
    assert errors == []
    assert fields["summary"] == "CORS on API"
    assert fields["priority"] == {"id": "2"}
    assert fields["customfield_10010"] == {"id": "9"}
    assert fields["project"] == {"key": "SEC"}
    assert fields["issuetype"] == {"id": "10001"}


def test_build_jira_issue_fields_requires_ask_values():
    mappings = [
        {
            "external_field_id": "customfield_1",
            "external_field_name": "Dev team",
            "external_field_type": "option",
            "fill_mode": "ask",
            "required": True,
            "allowed_values": [],
        }
    ]
    _fields, errors = field_domain.build_jira_issue_fields(mappings, {"title": "x"}, {}, "SEC", "1", adf=False)
    assert errors == ["Dev team is required."]


def test_defectdojo_payload_maps_severity():
    mappings = field_domain.seed_mappings("defectdojo", field_domain.defectdojo_fields())
    values = field_domain.raptor_values(
        {"finding": {"title": "XSS", "description": "reflected", "baseScore": 6.1, "occurrences": []}}
    )
    payload, errors = field_domain.build_defectdojo_finding(mappings, values, {})
    assert errors == []
    assert payload["title"] == "XSS"
    assert payload["severity"] == "Medium"
    assert payload["numerical_severity"] == "S2"


def test_defectdojo_replaces_raptor_images_with_attach_notes():
    mappings = field_domain.seed_mappings("defectdojo", field_domain.defectdojo_fields())
    values = field_domain.raptor_values(
        {
            "finding": {
                "title": "JWT",
                "description": "weak secret",
                "evidence": "![jwt_tool decode](/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png)",
                "baseScore": 9.1,
                "occurrences": [],
            }
        }
    )
    payload, errors = field_domain.build_defectdojo_finding(mappings, values, {})
    assert errors == []
    assert "/pentest/images/" not in payload["steps_to_reproduce"]
    assert "Screenshot attached as `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png`" in payload["steps_to_reproduce"]
    assert "jwt_tool decode" in payload["steps_to_reproduce"]


def test_defectdojo_catalog_includes_fields_raptor_does_not_have():
    ids = {item["id"] for item in field_domain.defectdojo_fields()}
    assert "mitigation" in ids
    assert "impact" in ids
    assert "references" in ids
    assert "component_name" in ids
    assert "planned_remediation_date" in ids
    raptor_ids = {item["id"] for item in field_domain.RAPTOR_FIELDS}
    assert "impact" in raptor_ids
    assert "evidence" in raptor_ids
    assert "remediation" in raptor_ids
    assert not {"mitigation", "references", "component_name"} & raptor_ids


def test_to_adf_turns_markdown_headings_into_nodes():
    doc = field_domain.to_adf("## Impact\n\nAccount takeover.")
    assert doc["content"][0]["type"] == "heading"
    assert doc["content"][0]["attrs"]["level"] == 2
    assert doc["content"][0]["content"][0]["text"] == "Impact"


def test_to_jira_wiki_turns_markdown_headings_into_wiki_headings():
    wiki = field_domain.to_jira_wiki("## Description\n\nReflected next.\n\n## Impact\n\nSession theft.")
    assert wiki.startswith("h2. Description")
    assert "h2. Impact" in wiki
    assert "## " not in wiki
    fenced = field_domain.to_jira_wiki("## Evidence\n\n```shell\n# cracked HS256\n```")
    assert fenced.startswith("h2. Evidence")
    assert "{code:bash}" in fenced
    assert "{code:shell}" not in fenced
    assert "{code}" in fenced
    assert "```" not in fenced
    assert "# cracked HS256" in fenced


def test_to_jira_wiki_maps_unknown_fence_languages_and_inline_backticks():
    wiki = field_domain.to_jira_wiki(
        "JWT at `example.com/` uses `your-256-bit-secret`.\n\n```http\nGET /admin HTTP/1.1\n```"
    )
    assert "{{example.com/}}" in wiki
    assert "{{your-256-bit-secret}}" in wiki
    assert "`example.com/`" not in wiki
    assert "{code:http}" not in wiki
    assert wiki.count("{code}") >= 2
    assert "GET /admin HTTP/1.1" in wiki


def test_to_jira_wiki_turns_markdown_images_into_wiki_thumbnails():
    wiki = field_domain.to_jira_wiki(
        "![jwt_tool decode](/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png)"
    )
    assert '!aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png|thumbnail, alt="jwt_tool decode"!' in wiki
    assert "![" not in wiki


def test_to_adf_turns_fences_into_code_blocks():
    doc = field_domain.to_adf("## Evidence\n\n```shell\njwt_tool -C\n```")
    types = [block["type"] for block in doc["content"]]
    assert "heading" in types
    code = next(block for block in doc["content"] if block["type"] == "codeBlock")
    assert code["attrs"]["language"] == "bash"
    assert "jwt_tool -C" in code["content"][0]["text"]


def test_jira_description_combines_narrative_sections():
    values = {
        "description": "Replay the request without MFA.",
        "impact": "An attacker can impersonate any user.",
        "evidence": "```http\nGET /admin HTTP/1.1\n```",
        "remediation": "Require MFA on that route.",
    }
    mapping = {
        "external_field_id": "description",
        "external_field_type": "doc",
        "fill_mode": "mapped",
        "raptor_field": "description,impact,evidence,remediation",
        "required": True,
    }
    preview = field_domain.mapped_preview(mapping, values)
    assert preview.startswith("## Description")
    assert "## Impact" in preview
    assert "## Evidence" in preview
    assert "## Remediation" in preview
    fields, errors = field_domain.build_jira_issue_fields(
        [mapping], values, {}, "SEC", "10004", adf=True
    )
    assert errors == []
    assert fields["description"]["type"] == "doc"
    headings = [block["content"][0]["text"] for block in fields["description"]["content"] if block["type"] == "heading"]
    assert headings == ["Description", "Impact", "Evidence", "Remediation"]
    wiki_fields, wiki_errors = field_domain.build_jira_issue_fields(
        [{**mapping, "external_field_type": "text"}], values, {}, "SEC", "10004", adf=False
    )
    assert wiki_errors == []
    assert wiki_fields["description"].startswith("h2. Description")
    assert "h2. Impact" in wiki_fields["description"]
    assert "## Description" not in wiki_fields["description"]
    assert "{code:http}" not in wiki_fields["description"]
    assert "GET /admin HTTP/1.1" in wiki_fields["description"]


def test_compose_narrative_skips_empty_sections_and_omits_heading_for_one():
    assert field_domain.compose_narrative(["impact"], {"impact": "Session theft."}) == "Session theft."
    combined = field_domain.compose_narrative(
        ["evidence", "description"],
        {"description": "Weak JWT.", "evidence": "jwt_tool cracked HS256.", "impact": ""},
    )
    assert combined.startswith("## Description")
    assert "## Evidence" in combined
    assert "## Impact" not in combined


def test_is_narrative_combine_field_is_jira_description():
    assert field_domain.is_narrative_combine_field("description", "Description", "doc")
    assert field_domain.is_narrative_combine_field("customfield_9", "Issue Description", "text")
    assert not field_domain.is_narrative_combine_field("summary", "Summary", "string")
    assert not field_domain.is_narrative_combine_field("environment", "Environment", "string")


def test_encrypt_roundtrip():
    token = encrypt_secret("jira-token")
    assert token != "jira-token"
    assert decrypt_secret(token) == "jira-token"


def test_jira_issuetype_meta_values_list():
    from app.integrations.jira.client import _fields_from_issuetype_meta

    fields = _fields_from_issuetype_meta(
        {
            "values": [
                {"fieldId": "summary", "name": "Summary", "required": True, "schema": {"type": "string"}},
                {
                    "fieldId": "customfield_10112",
                    "name": "Dev Team",
                    "required": False,
                    "schema": {"type": "option", "custom": "select"},
                    "allowedValues": [{"id": "10000", "value": "Red Team"}],
                },
            ]
        }
    )
    assert "summary" in fields
    assert fields["customfield_10112"]["name"] == "Dev Team"
