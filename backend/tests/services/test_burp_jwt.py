from app.services import burp_jwt


def test_queue_jwt_rejects_when_destructive_off(monkeypatch):
    monkeypatch.setattr(burp_jwt, "destructive_allowed", lambda wave, host: (False, "Global scanner destructive tools are disabled."))
    payload, status = burp_jwt.queue_jwt_job(
        wave={"id": 9, "application_id": 1},
        agent_id=1,
        host="app.example",
        path="/api",
        token="eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.sig",
    )
    assert status == 403
    assert "destructive" in payload["error"]


def test_suite_hits_reads_cracked_secret_and_ignores_empty_suite():
    assert burp_jwt.suite_hits({"success": True, "suite": []}) == []
    hits = burp_jwt.suite_hits(
        {
            "suite": [
                {
                    "step": "weak_secret",
                    "stdout": "\x1b[32m[+] your-256-bit-secret is the CORRECT key!\x1b[0m",
                    "return_code": 0,
                }
            ]
        }
    )
    assert hits == [
        {"step": "weak_secret", "kind": "weak_secret", "detail": "your-256-bit-secret"}
    ]


def test_finding_writeup_is_a_finding_not_live_status():
    writeup = burp_jwt.finding_writeup(
        host="example.com",
        path="/login",
        hits=[{"kind": "weak_secret", "detail": "your-256-bit-secret"}],
        suite=[
            {
                "step": "decode",
                "command": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np",
                "stdout": "Decoded Token Values:\n[+] jwttool.py\nalg = HS256",
            },
            {
                "step": "weak_secret",
                "stdout": "[+] your-256-bit-secret is the CORRECT key!",
            },
        ],
        screenshots=[
            {
                "step": "weak_secret",
                "alt": "jwt_tool HMAC dictionary crack",
                "url": "/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
            }
        ],
        http_exchange=(
            "```http\n"
            "GET /login HTTP/1.1\n"
            "Host: example.com\n"
            "Authorization: Bearer [jwt]\n"
            "\n"
            "===\n"
            "\n"
            "HTTP/1.1 200\n"
            "```\n"
        ),
    )
    assert writeup["title"] == "Weak JWT HMAC secret on example.com"
    assert "your-256-bit-secret" in writeup["description"]
    assert "forge" in writeup["description"].lower()
    assert "draft" not in writeup["description"].lower()
    assert writeup["impact"]
    evidence = writeup["evidence"]
    assert "###" not in evidence
    assert "Kali commands" not in evidence
    assert "Command screenshots" not in evidence
    assert "Tool output" not in evidence
    assert "```shell" in evidence
    assert "jwt_tool.py" in evidence
    assert "```http" in evidence
    assert "GET /login HTTP/1.1" in evidence
    assert evidence.index("```http") < evidence.index("```shell")
    crack_cmd = "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -C -d /opt/jwt_tool/jwt-secrets.txt"
    assert evidence.index(crack_cmd) < evidence.index(
        "![jwt_tool HMAC dictionary crack](/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png)"
    )
    assert "RAPTOR did not" not in evidence
    assert writeup["remediation"]
    assert writeup["base_score"] == 9.1


def test_suite_ran_requires_jwt_tool_output():
    assert burp_jwt.suite_ran({"success": True, "suite": []}) is False
    assert burp_jwt.suite_ran({"suite": [{"return_code": 1, "stderr": "Traceback (most recent call last):\nKeyError: argvals"}]}) is False
    assert burp_jwt.suite_ran({"suite": [{"return_code": 1, "stdout": "Original JWT:\nDecoded Token Values:"}]}) is True


def _job_harness(monkeypatch, kali_payload):
    monkeypatch.setattr(
        burp_jwt.burp_repository,
        "get_job",
        lambda job_id: {
            "id": job_id,
            "wave_id": 9,
            "application_id": 1,
            "host": "app.example",
            "path": "/api",
            "payload_json": {"jwt": "eyJhbGciOiJub25lIn0.eyJzdWIiOiJhIn0.sig"},
        },
    )
    monkeypatch.setattr(
        burp_jwt.phase2b_repository,
        "get_wave",
        lambda wave_id: {"id": wave_id, "application_id": 1},
    )
    monkeypatch.setattr(burp_jwt, "destructive_allowed", lambda wave, host: (True, ""))
    monkeypatch.setattr(burp_jwt, "_name_job", lambda job, wave: "Preprod JWT on api")
    monkeypatch.setattr(burp_jwt, "_call_kali", lambda token, host, path: kali_payload)
    monkeypatch.setattr("app.services.burp_hacktricks.search_hacktricks", lambda *args, **kwargs: [])
    monkeypatch.setattr(burp_jwt.burp_repository, "latest_http_event", lambda *args, **kwargs: None)
    updates = []
    monkeypatch.setattr(burp_jwt.burp_repository, "update_job", lambda *args, **kwargs: updates.append(kwargs))
    proposals = []
    monkeypatch.setattr(
        burp_jwt.burp_repository,
        "insert_proposal",
        lambda **kwargs: proposals.append(kwargs) or 77,
    )
    return updates, proposals


def test_run_jwt_job_fails_when_jwt_tool_never_runs(monkeypatch):
    updates, proposals = _job_harness(
        monkeypatch,
        {"success": False, "suite": [{"step": "decode", "return_code": 1, "stderr": "KeyError: argvals"}], "error": "jwt_tool failed"},
    )
    result = burp_jwt.run_jwt_job(3)
    assert result["success"] is False
    assert updates[-1]["status"] == "failed"
    assert proposals == []


def test_run_jwt_job_completes_without_proposal_when_no_hit(monkeypatch):
    updates, proposals = _job_harness(
        monkeypatch,
        {"success": True, "suite": [{"step": "decode", "return_code": 1, "stdout": "Original JWT:\nalg: HS256", "success": True}]},
    )
    result = burp_jwt.run_jwt_job(3)
    assert result["proposal_id"] is None
    assert result["status"] == "completed"
    assert updates[-1]["status"] == "completed"
    assert proposals == []


def test_run_jwt_job_writes_proposal_only_on_cracked_secret(monkeypatch):
    updates, proposals = _job_harness(
        monkeypatch,
        {
            "success": True,
            "suite": [
                {
                    "step": "weak_secret",
                    "return_code": 1,
                    "stdout": "[+] CORRECT key found:\nsecret",
                }
            ],
        },
    )
    result = burp_jwt.run_jwt_job(3)
    assert result["proposal_id"] == 77
    assert result["status"] == "completed"
    assert updates[-1]["status"] == "completed"
    assert proposals[0]["title"] == "Weak JWT HMAC secret on app.example"
    assert proposals[0]["kind"] == "jwt"
    assert "forge" in proposals[0]["description"].lower()
    assert "secret" in proposals[0]["description"]
    assert "draft" not in proposals[0]["description"].lower()


def test_refresh_finding_evidence_rewrites_markdown(monkeypatch):
    monkeypatch.setattr(
        burp_jwt.burp_repository,
        "get_proposal_for_finding",
        lambda finding_id: {
            "id": 7,
            "job_id": 4,
            "result_json": {
                "hits": [{"step": "weak_secret", "kind": "weak_secret", "detail": "secret"}],
                "suite": [{"step": "weak_secret", "stdout": "[+] secret is the CORRECT key!"}],
            },
        },
    )
    monkeypatch.setattr(
        burp_jwt.burp_repository,
        "get_job",
        lambda job_id: {"id": job_id, "host": "example.com", "path": "/"},
    )
    monkeypatch.setattr(
        "app.services.terminal_shot.attach_jwt_screenshots",
        lambda suite, hits=None: [
            {
                "step": "weak_secret",
                "alt": "jwt_tool HMAC dictionary crack",
                "url": "/pentest/images/bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png",
            }
        ],
    )
    updated = {}
    monkeypatch.setattr(
        "app.repositories.pentest_findings_repository.update_finding_fields",
        lambda finding_id, fields: updated.update({"id": finding_id, **fields}) or {"id": finding_id},
    )
    monkeypatch.setattr(burp_jwt.burp_repository, "latest_http_event", lambda *args, **kwargs: None)
    payload = burp_jwt.refresh_finding_evidence("f-1")
    assert payload["finding_id"] == "f-1"
    assert "```shell" in updated["evidence"]
    assert "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.png" in updated["evidence"]
    assert "###" not in updated["evidence"]
    assert "guessable" in updated["description"]
