#!/bin/bash
set -e
while true; do
  python manage.py fetch_emails || true
  sleep ${EMAIL_POLL_SECONDS:-30}
done
