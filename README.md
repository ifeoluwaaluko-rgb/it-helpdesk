# Zynaros

Clean rebuilt MVP for an AI-assisted IT helpdesk/ticketing system.

## Default seeded users

The project still runs `seed.py` on startup as requested. If the database is empty, it creates demo users:

- manager / manager
- senior1 / senior1
- consultant1 / consultant1
- consultant2 / consultant2
- associate1 / associate1
- associate2 / associate2

## Railway processes

Use:

```
web: bash start.sh
worker: bash start-worker.sh
```

The web process runs migrations, collectstatic, seed, and Gunicorn.
The worker polls inbound IMAP every `EMAIL_POLL_SECONDS` seconds, default 15.

## Outbound email

Outbound email is disabled by default:

```
EMAIL_ENABLED=False
```

Inbound IMAP can still be configured from Settings.

## Validation done before packaging

- Python compile check passed for all project `.py` files.
- Static code sanity checks were performed.
- Django runtime tests could not be executed in this environment because Django is not installed here.
