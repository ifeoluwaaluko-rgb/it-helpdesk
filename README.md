# IT Helpdesk MVP

An in-place rebuilt Django helpdesk app for internal IT operations, with Railway kept as the deployment target.

## Product Areas

- Tickets for intake, triage, assignment, SLA tracking, comments, and resolution.
- Knowledge base for reusable support articles and revision history.
- Directory for staff records and department links.
- Assets for inventory, assignment, and incident logging.
- Settings and integrations for email, webhooks, Graph, WhatsApp, and OpenAI.

## Current Rebuild Baseline

- Canonical Django settings module: `helpdesk.settings`
- Railway startup path: `Procfile -> start.sh -> gunicorn helpdesk.wsgi`
- Production `SECRET_KEY` is required
- Stronger role checks are in place for write-heavy flows
- Major mutation paths now use Django forms or service helpers instead of raw POST handling
- SMTP and IMAP runtime config resolve consistently from Railway env vars or saved integration settings
- Seed data is opt-in through `RUN_SEED_ON_DEPLOY=true`

## Local Run

1. Install dependencies from `requirements.txt`.
2. Set `DJANGO_SETTINGS_MODULE=helpdesk.settings`.
3. Provide a `SECRET_KEY`.
4. Run `python manage.py migrate`.
5. Run `python manage.py collectstatic --noinput`.
6. Run `python manage.py runserver`.

## Railway

Railway-specific notes live in [RAILWAY.md](C:/Users/Ifeoluwa/Documents/Codex/2026-04-23-files-mentioned-by-the-user-it/it-helpdesk-MVP-PHASE-1/it-helpdesk-6d5ef855bfdba177e3525011005677587bd8fb66/RAILWAY.md).

Release and handoff notes live in [RELEASE_READY.md](C:/Users/Ifeoluwa/Documents/Codex/2026-04-23-files-mentioned-by-the-user-it/it-helpdesk-MVP-PHASE-1/it-helpdesk-6d5ef855bfdba177e3525011005677587bd8fb66/RELEASE_READY.md).

## Demo Data

`start.sh` only runs `seed.py` when `RUN_SEED_ON_DEPLOY=true`. Keep that disabled in production unless you explicitly want sample users, tickets, articles, directory entries, and assets.

## Known Limitation In This Session

The Django test suite and management checks were not executed here because this session did not have a working `python` or `py` runtime.
