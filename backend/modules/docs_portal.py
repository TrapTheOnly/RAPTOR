"""Compatibility facade for docs portal services."""

from app.services.docs_manifest_service import (
    get_docs_access_matrix_for_user,
    get_docs_manifest_for_user,
    get_docs_page_for_user,
)

__all__ = [
    "get_docs_access_matrix_for_user",
    "get_docs_manifest_for_user",
    "get_docs_page_for_user",
]
