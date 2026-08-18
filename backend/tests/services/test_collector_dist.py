from pathlib import Path

from app.services import collector_dist


def test_artifact_path_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("COLLECTOR_DIST_DIR", str(tmp_path))
    assert collector_dist.artifact_path("linux-amd64") is None
    payload = collector_dist.version_payload()
    assert payload["version"]
    assert payload["downloads"]["linux-amd64"]["available"] is False


def test_artifact_path_finds_binary(tmp_path, monkeypatch):
    monkeypatch.setenv("COLLECTOR_DIST_DIR", str(tmp_path))
    binary = Path(tmp_path) / "raptor-collector-linux-amd64"
    binary.write_bytes(b"fake")
    found = collector_dist.artifact_path("linux-amd64")
    assert found == binary
    assert collector_dist.available_downloads()["linux-amd64"]["available"] is True
