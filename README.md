# Neurealm Service Desk

An IT service management app for Neurealm: incidents, requests, problems, changes, assets, knowledge, portal, analytics and more, with **Neurealm AI** (off by default; smart rules when no AI key is set).

- **Backend:** FastAPI + SQLAlchemy (`backend/`). Postgres in production (Neon), SQLite for tests and local runs.
- **Frontend:** React + Vite + Tailwind (`frontend/`). Light theme, 7 languages (English and Hindi full), right-to-left ready.
- **No prices** or money values are stored or shown.

## Rename the product
- Frontend: edit `frontend/src/brand.ts` (product, company, AI name, sign-up domain).
- Backend: set the `BRAND_NAME` environment variable.

## Run locally
```bash
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000 (SQLite, demo data seeded)
cd ../frontend && npm ci && npm run dev # http://localhost:5173 (proxies /api to :8000)
```
Tests: `cd backend && pytest -q`. Build: `cd frontend && npm run build`.

## Demo logins (change these after first login)
| Role | Email | Password |
|---|---|---|
| Admin | admin@neurealm.com | Admin@123 |
| Agent | agent@neurealm.com | Agent@123 |
| Employee | user@neurealm.com | User@123 |

Self sign-up is limited to `@neurealm.com` addresses.

## Deploy
See [DEPLOY_RENDER.md](DEPLOY_RENDER.md). User guide: [docs/USER_GUIDE.md](docs/USER_GUIDE.md) (also in the app at `/help`).
