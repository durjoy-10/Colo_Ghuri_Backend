#!/bin/sh
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

gunicorn colo_ghuri.wsgi:application --bind 0.0.0.0:${PORT:-10000} --workers ${WEB_CONCURRENCY:-1} --timeout 180
