import os

from app.domain.docs.manifest_schema import DOCS_CONTENT_ROOT, resolve_docs_content_path


def test_resolve_docs_content_path_rejects_traversal_inputs():
    assert resolve_docs_content_path("..", "secrets") is None
    assert resolve_docs_content_path("reporting", "../../etc/passwd") is None


def test_resolve_docs_content_path_allows_normal_docs_path():
    content_path = resolve_docs_content_path("getting-started", "platform-overview")

    assert content_path is not None
    assert os.path.commonpath([content_path, os.path.abspath(DOCS_CONTENT_ROOT)]) == os.path.abspath(
        DOCS_CONTENT_ROOT
    )
