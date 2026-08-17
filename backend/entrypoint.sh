#!/bin/sh
set -e
cd /usr/app/src/backend
export PYTHONPATH="/usr/app/src/backend${PYTHONPATH:+:$PYTHONPATH}"

python -c "from app.bootstrap.db_init import init_db; from app.services.admin_auth_service import init_admin_db; init_db(); init_admin_db()"

PORT="${APP_PORT:-5000}"
if [ "${RAPTOR_ROLE:-app}" = "worker" ]; then
  exec gunicorn --bind "0.0.0.0:${PORT}" --workers 1 --threads 1 --timeout 120 worker_wsgi:app
fi
exec gunicorn --bind "0.0.0.0:${PORT}" --workers "${GUNICORN_WORKERS:-2}" --timeout 120 wsgi:app
