#!/usr/bin/env bash
set -e

# Fix ownership of bind-mounted data directories before dropping privileges.
# This runs as root (container default) so it can chown host-mounted paths.
mkdir -p /app/data/media /app/data/staticfiles
chown -R appuser:appgroup /app/data

echo "==> Running database migrations..."
gosu appuser python manage.py migrate --noinput

echo "==> Collecting static files..."
gosu appuser python manage.py collectstatic --noinput

echo "==> Starting Gunicorn (running as appuser)..."
exec gosu appuser gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
