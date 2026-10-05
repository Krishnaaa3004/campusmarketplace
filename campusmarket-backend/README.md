# CampusMarket — Backend

FastAPI + SQLAlchemy API for CampusMarket, backed by Supabase Postgres. It handles OTP login
with a college email, marketplace listings, Looking For requests and the Resource Hub
(PDF previews and paid access requests).

The product overview, frontend setup and full API table are in the [root README](../README.md).

## Setup

```bash
uv sync                  # runtime deps + dev deps (pytest, httpx)
cp .env.example .env     # fill in the values below
uv run alembic upgrade head
```

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Supabase Postgres URI: Project Settings → Database → Connection string → URI. The transaction pooler (port 6543) works fine. |
| `JWT_SECRET_KEY` | Long random string used to sign login tokens |
| `OTP_PEPPER` | Extra secret mixed into stored OTP hashes |
| `ALLOWED_EMAIL_DOMAINS` | JSON list of college domains allowed to sign up, e.g. `["medhaviskillsuniversity.edu.in"]` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` | Gmail SMTP for OTP emails (use an app password) |
| `CORS_ORIGINS` | Frontend origins, e.g. `["http://localhost:5173"]` |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `OTP_EXPIRE_MINUTES` | Optional; defaults are 7 days and 10 minutes |

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- http://localhost:8000/health returns `{"status": "ok"}` only when the database is reachable
- http://localhost:8000/docs has the interactive API docs

## Migrations

```bash
uv run alembic upgrade head        # apply everything (run after every pull)
uv run alembic current             # what the database is on
uv run alembic revision -m "..."   # new migration; chain it after the current head
```

The migrations in `alembic/versions/` were written by hand. Keep them in sync with
`app/models/`, and import every new model in `alembic/env.py`.

If the database is behind the code, the affected endpoints return 500. Unhandled 500s go out
without CORS headers, so the browser reports them as "Failed to fetch". Run
`alembic current` first when you see that.

## Tests

```bash
uv run pytest
```

The suite uses an in-memory SQLite database and temporary file folders, and sets its own
environment variables, so it never touches Supabase or the real `uploads/` and `private/`
folders. It covers the Resource Hub:

- `test_resource_access.py`: the access rules (guest, unverified, locked, pending, denied,
  approved, free, closed, owner, admin), and which fields each viewer receives
- `test_resource_validation.py`: form rules, the drive-link allowlist, rejected PDFs leaving
  nothing behind, update/delete file cleanup, filters and facets
- `test_pdf_preview.py`: page 1 sharp, pages 2–4 measurably blurred, at most 4 pages
  rendered, and the half-blurred single-page sale

## Structure

```
app/
  main.py               app, routers, CORS, /uploads static mount, /health
  api/routes/
    auth.py             signup/login (OTP), onboarding, profile, avatar
    listings.py         marketplace listings + photos + recommendations
    requests.py         Looking For requests
    resources.py        Resource Hub: CRUD, previews, access requests, protected file download
  core/
    config.py           settings from .env
    security.py         JWT, get_current_user, get_optional_user, require_seller, require_admin
    email.py            OTP email over SMTP
    pdf_preview.py      PDF validation and preview rendering (PyMuPDF + Pillow)
  db/                   Base, engine, get_db
  models/               User, OTPCode, Listing, ProductRequest, Resource, ResourceAccess
  schemas/              Pydantic request/response models
alembic/                migrations
tests/                  pytest suite
uploads/                public files served at /uploads (gitignored)
private/                original resource PDFs, never served directly (gitignored)
```

## Files and storage

- **Listing photos and avatars** are saved in `uploads/` and served publicly.
- **Resource PDFs** are checked first: they must start with `%PDF`, be unencrypted and be
  under 15 MB. The original goes to `private/resources/` and is only streamed through
  `GET /api/resources/{id}/file` after an access check.
- **Resource previews** are JPEGs in `uploads/resource-previews/`: page 1 sharp, and pages 2–4
  small and blurred on the server. A single-page PDF sold through hosted delivery has its
  lower half blurred. The blur happens on the pixels, so viewers without access never
  receive the real pages.

Both folders live on the server's local disk. If you deploy somewhere with an ephemeral
filesystem, move them to persistent storage.

## Permissions

The frontend route guards are for convenience only. The real checks are these dependencies:

| Dependency | Allows |
|---|---|
| `get_optional_user` | Anyone; guests get `None` (used where the response depends on the viewer) |
| `get_current_user` | Any logged-in user |
| `require_seller` | `account_type = "seller"` or admin |
| `require_admin` | `role = "admin"` |

Routes also check ownership (`_get_owned_listing`, `_get_owned_resource`) and, where it
matters, `user.verified`.
