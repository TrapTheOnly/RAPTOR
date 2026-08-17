"""Gunicorn application entry for the RAPTOR HTTP workers."""

from app import create_app

app = create_app()
