"""Compatibility facade for DB backend adapter."""

from app.integrations.db.postgres_adapter import ensure_db_backend

__all__ = ["ensure_db_backend"]
