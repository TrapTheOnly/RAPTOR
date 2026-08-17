"""Gunicorn application entry for the RAPTOR job worker (RAPTOR_ROLE=worker)."""

from app import create_app
from app.worker import start_job_loop

app = create_app()
start_job_loop()
