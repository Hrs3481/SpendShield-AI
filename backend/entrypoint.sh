#!/usr/bin/env sh
# Applies pending migrations, then starts the API.
#
# This is what makes a deploy self-contained: the previous process was to open a
# shell on the running service and call Base.metadata.create_all() by hand, which
# is not repeatable and leaves no schema version behind.
set -e

echo "Applying database migrations..."
alembic upgrade head

echo "Starting SpendShield API on port ${PORT:-8000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips '*'
