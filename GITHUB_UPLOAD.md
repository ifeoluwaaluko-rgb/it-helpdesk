# GitHub Upload Notes

Push the contents of this project folder as the root of your GitHub repository:

- [it-helpdesk-6d5ef855bfdba177e3525011005677587bd8fb66](C:/Users/Ifeoluwa/Documents/Codex/2026-04-23-files-mentioned-by-the-user-it/it-helpdesk-MVP-PHASE-1/it-helpdesk-6d5ef855bfdba177e3525011005677587bd8fb66)

Do commit:

- Application code
- `requirements.txt`
- `Procfile`
- `start.sh`
- `README.md`
- `RAILWAY.md`
- `RELEASE_READY.md`
- `.env.example`

Do not commit:

- `.env`
- `db.sqlite3`
- `staticfiles/`
- `media/`
- local virtualenv folders such as `.venv/` or `venv/`
- any downloaded zip file

Recommended GitHub flow:

1. Extract the zip if needed.
2. Open the project folder listed above.
3. Initialize a git repo there if one does not already exist.
4. Commit the folder contents.
5. Push that repo to GitHub.
6. Point Railway at that GitHub repository.

After push, confirm Railway has:

- `SECRET_KEY`
- `DATABASE_URL`
- `DJANGO_SETTINGS_MODULE=helpdesk.settings`
- either `RAILWAY_PUBLIC_DOMAIN` or explicit `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`
- `RUN_SEED_ON_DEPLOY=false` unless you intentionally want demo data
