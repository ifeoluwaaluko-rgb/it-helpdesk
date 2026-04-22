#!/bin/bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn helpdesk.wsgi --bind 0.0.0.0:$PORT --log-file -
