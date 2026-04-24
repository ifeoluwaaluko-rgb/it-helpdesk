# Release Ready Notes

This project has been rebuilt in place with Railway kept as the deployment target.

What is now true:

- Django uses the canonical settings module `helpdesk.settings`.
- Root `settings.py` and `urls.py` remain as compatibility shims only.
- Railway startup remains `Procfile -> start.sh -> gunicorn helpdesk.wsgi`.
- Production `SECRET_KEY` is required.
- Ticket, knowledge base, directory, asset, and settings write paths now enforce stronger role and staff boundaries.
- Core mutation-heavy flows now use Django forms or service helpers instead of raw POST handling.
- SMTP and IMAP runtime behavior is consistent between Railway env vars and saved integration config.
- Seed data is opt-in only through `RUN_SEED_ON_DEPLOY=true`.

Recommended release steps:

1. Confirm Railway has `SECRET_KEY`, `DATABASE_URL`, and either `RAILWAY_PUBLIC_DOMAIN` or explicit `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`.
2. Keep `RUN_SEED_ON_DEPLOY=false` unless you explicitly want demo data.
3. Deploy.
4. Let Railway run `start.sh`, which applies migrations and collects static files.
5. Perform the smoke check in `RAILWAY.md`.

Legacy files intentionally retained:

- `settings.py`: compatibility shim to `helpdesk.settings`
- `urls.py`: compatibility shim to `helpdesk.urls`
- `fix_article_content.py`: one-off maintenance utility for older knowledge-base content

Known limitation of this rebuild session:

- The Django test suite and management checks were not executed here because this session did not have a working `python` or `py` runtime.
