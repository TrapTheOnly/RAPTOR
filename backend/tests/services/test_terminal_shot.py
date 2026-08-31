from app.services import terminal_shot


def test_command_for_step_prefers_kali_command_and_redacts_defaults():
    assert terminal_shot.command_for_step({"step": "weak_secret"}) == terminal_shot.JWT_TOOL_COMMANDS["weak_secret"]
    assert terminal_shot.command_for_step({"step": "decode", "command": "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np"}) == (
        "python3 /opt/jwt_tool/jwt_tool.py [jwt] -np"
    )


def test_trim_output_keeps_correct_key_when_truncated():
    lines = [f"noise {i}" for i in range(80)]
    lines.append("[+] your-256-bit-secret is the CORRECT key!")
    trimmed = terminal_shot.trim_output("\n".join(lines), max_lines=10)
    assert "CORRECT key" in trimmed
    assert trimmed.splitlines()[0] == "…"


def test_markdown_excerpt_drops_jwt_tool_banner():
    blob = "\n".join(
        [
            r" \______/ \__/     \__|   \__|      \__| \______/  \______/ \__",
            " Version 2.3.0                \\______|             @ticarpi",
            "Original JWT:",
            "[+] your-256-bit-secret is the CORRECT key!",
        ]
    )
    excerpt = terminal_shot.markdown_excerpt(blob)
    assert "ticarpi" not in excerpt
    assert "Original JWT:" in excerpt
    assert "CORRECT key" in excerpt


def test_transcript_looks_like_a_shell_session():
    text = terminal_shot.transcript_for(
        {
            "step": "weak_secret",
            "stdout": "[+] your-256-bit-secret is the CORRECT key!",
        }
    )
    assert text.startswith("$ python3 /opt/jwt_tool/jwt_tool.py [jwt] -np -C")
    assert "CORRECT key" in text


def test_evidence_steps_prefers_decode_and_crack():
    suite = [
        {"step": "none_alg", "stdout": "Exploit: none"},
        {"step": "decode", "stdout": "Decoded Token Values:\nalg: HS256"},
        {"step": "weak_secret", "stdout": "[+] secret is the CORRECT key!"},
    ]
    steps = terminal_shot.evidence_steps(suite, [{"step": "weak_secret", "kind": "weak_secret"}])
    assert [item["step"] for item in steps] == ["decode", "weak_secret"]


def test_render_terminal_png_uses_devnull_stdin(monkeypatch):
    seen = {}

    def fake_run(command, **kwargs):
        seen["stdin"] = kwargs.get("stdin")
        out = command[command.index("-o") + 1]
        from pathlib import Path

        Path(out).write_bytes(b"\x89PNG\r\n\x1a\n" + b"x")

        class Proc:
            returncode = 0
            stdout = b""
            stderr = b""

        return Proc()

    monkeypatch.setattr(terminal_shot, "freeze_bin", lambda: "/usr/local/bin/freeze")
    monkeypatch.setattr(terminal_shot.subprocess, "run", fake_run)
    png = terminal_shot.render_terminal_png("$ echo hi\n")
    assert png.startswith(terminal_shot.PNG_MAGIC)
    assert seen["stdin"] is terminal_shot.subprocess.DEVNULL


def test_render_terminal_png_returns_none_without_freeze(monkeypatch):
    monkeypatch.setattr(terminal_shot, "freeze_bin", lambda: "")
    assert terminal_shot.render_terminal_png("$ echo hi\n") is None


def test_attach_jwt_screenshots_stores_png_urls(monkeypatch):
    monkeypatch.setattr(terminal_shot, "render_terminal_png", lambda text: b"\x89PNG\r\n\x1a\n" + b"x")
    monkeypatch.setattr("app.integrations.storage.offsec_storage.save_image", lambda data, ext: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png")
    shots = terminal_shot.attach_jwt_screenshots(
        [{"step": "weak_secret", "stdout": "[+] secret is the CORRECT key!"}],
        [{"step": "weak_secret"}],
    )
    assert shots == [
        {
            "step": "weak_secret",
            "alt": "jwt_tool HMAC dictionary crack",
            "url": "/pentest/images/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.png",
        }
    ]
