#!/bin/sh
set -e
if [ -n "${DATABASE_URL}" ]; then
  alembic upgrade head
fi
exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8002}"
