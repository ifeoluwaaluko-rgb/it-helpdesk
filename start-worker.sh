#!/bin/bash
set -e
exec python manage.py fetch_emails --loop --sleep ${EMAIL_POLL_SECONDS:-15}
