#!/bin/bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_demo_data --if-empty
exec gunicorn helpdesk.wsgi --bind 0.0.0.0:$PORT --log-file -
