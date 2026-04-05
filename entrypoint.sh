#!/bin/bash
set -e

echo "⏳ Waiting for PostgreSQL..."
while ! python -c "
import socket, os
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((os.environ.get('DB_HOST','db'), int(os.environ.get('DB_PORT','5432'))))
s.close()
" 2>/dev/null; do
    sleep 1
done
echo "✅ PostgreSQL is ready."

echo "🔄 Running migrations..."
python manage.py migrate --noinput

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "🚀 Starting Gunicorn..."
exec gunicorn autibloom.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120
