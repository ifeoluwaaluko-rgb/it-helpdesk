#!/bin/bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
if [ "$RUN_SEED_ON_DEPLOY" = "true" ]; then
  python seed.py
fi
gunicorn helpdesk.wsgi --bind 0.0.0.0:$PORT --log-file -
