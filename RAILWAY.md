# Railway Deploy Notes

This app is deployed with Django on Railway and expects the canonical settings module:

- `DJANGO_SETTINGS_MODULE=helpdesk.settings`

Recommended environment variables:

- `SECRET_KEY`
- `DEBUG=False`
- `DATABASE_URL`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `RAILWAY_PUBLIC_DOMAIN`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `IMAP_HOST`
- `IMAP_PORT`
- `IMAP_USER`
- `IMAP_PASSWORD`
- `RUN_SEED_ON_DEPLOY=false`

Notes:

- `SECRET_KEY` is required in production.
- `ALLOWED_HOSTS` should be a comma-separated list. If `RAILWAY_PUBLIC_DOMAIN` is present, it is appended automatically.
- `CSRF_TRUSTED_ORIGINS` should be a comma-separated list of full origins, such as `https://your-app.up.railway.app`. If `RAILWAY_PUBLIC_DOMAIN` is present, that origin is appended automatically.
- `RAILWAY_PUBLIC_DOMAIN` is the cleanest way to let the app derive its Railway host and CSRF origin.
- Static files are served with WhiteNoise.
- The app supports PostgreSQL through `DATABASE_URL`.
- Seeding is now opt-in. Leave `RUN_SEED_ON_DEPLOY` unset or `false` in production unless you intentionally want seed data.
- SMTP and IMAP can run from Railway environment variables alone. If you save SMTP or IMAP inside the app settings, the saved integration config takes precedence over the environment values.
- The rebuilt baseline no longer bakes in a specific Railway hostname. Production host handling should come from `ALLOWED_HOSTS` and/or `RAILWAY_PUBLIC_DOMAIN`.

Release checklist:

1. Ensure migrations are committed.
2. Ensure Railway env vars are set.
3. Deploy and run migrations before validating app flows.
4. Verify login, ticket creation, KB access, assets, and settings access with production roles.

Smoke check after deploy:

1. Sign in with a helpdesk staff account and confirm `/dashboard/` loads.
2. Create a ticket and confirm it appears in `/tickets/`.
3. Open one ticket detail page and confirm status/category updates still work.
4. Open `/knowledge/` and confirm article create/edit remains staff-only.
5. Open `/assets/` and confirm create/import/update remains staff-only.
6. Open `/settings/` with a manager account and confirm save/test actions return visible success or error messages.
