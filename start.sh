#!/bin/bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python seed.py
gunicorn helpdesk.wsgi --bind 0.0.0.0:$PORT --log-file -
