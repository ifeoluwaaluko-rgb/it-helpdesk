#!/bin/bash
set -e
python manage.py fetch_emails --loop --sleep ${EMAIL_POLL_SECONDS:-15}
