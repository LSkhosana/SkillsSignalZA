# SkillSignalZA API

FastAPI service for SkillSignalZA. This package owns HTTP transport, configuration, logging and the future home of deterministic assessment work.

It does not own the Expo client (`Main/`) or the job-post collector (`Scraper/`). Assessment scoring must be implemented in `app/engine`, never in API routes. Secrets must never be committed.

## Boundaries

| Package | Owns |
| --- | --- |
| `app/api` | HTTP routing and request/response validation |
| `app/domain` | Stable SkillSignalZA concepts and rules |
| `app/engine` | Deterministic extraction, scoring, QA and reporting |
| `app/repositories` | Persistence ports and adapters |
| `app/services` | Use-case coordination |
| `app/core` | Settings, logging and the future auth boundary |

No scoring rules belong in routes. No Supabase-specific objects belong in the domain layer.

## Directory structure

```text
Server/
├── app/                  # Application source
├── tests/                # Unit and integration tests
├── migrations/           # PostgreSQL and private Storage setup SQL
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Requirements

- Python 3.13

## Setup

### Windows

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e ".[dev]"
```

### macOS / Linux

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
```

## Environment

Copy `.env.example` to `.env` and replace placeholders with local values.

The API starts without `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` or `SUPABASE_SECRET_KEY`. Leave them unset until a PostgreSQL database and private Storage bucket are configured.

PostgreSQL migrations live in `migrations/postgres/`. The private CV bucket setup lives in `migrations/supabase/`. Never commit `.env` or production secrets. `DATABASE_URL` and `SUPABASE_SECRET_KEY` must never appear in logs or API responses.

## Local startup

### Windows

```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload
```

### macOS / Linux

```bash
.venv/bin/python -m uvicorn app.main:app --reload
```

The server listens on `http://127.0.0.1:8000`.

## Health endpoint

```http
GET /api/v1/health
```

Returns HTTP 200 with `status`, `service`, `version` and `environment`. It does not contact Supabase or expose configuration.

Root `GET /` points developers to `/api/v1/health` and `/docs`.

## Tests, lint and formatting

### Windows

```powershell
.venv\Scripts\python -m compileall app
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
```

### macOS / Linux

```bash
.venv/bin/python -m compileall app
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Apply formatting with `python -m ruff format .`.

## Docker

Build and run from this directory:

```bash
docker build -t skillsignalza-api .
docker run --rm -p 8000:8000 skillsignalza-api
```

Uvicorn binds to `0.0.0.0` and uses `PORT` when set, otherwise `8000`.

## Render

Do not create the Render service from this repository task. When you deploy:

| Setting | Value |
| --- | --- |
| Service type | Web Service |
| Root directory | `Server` |
| Runtime | Docker |
| Health check path | `/api/v1/health` |

Set environment variables in the Render dashboard. Do not bake secrets into the image or this repository.

Useful variables:

- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `CORS_ORIGINS` — comma-separated production web origins, not `*` with credentials
- `DATABASE_URL` — PostgreSQL DSN for assessment persistence
- `DB_POOL_MIN_SIZE` / `DB_POOL_MAX_SIZE` — optional pool bounds, default 0/5
- `SUPABASE_*` — private Storage after the bucket is configured
- `SUPABASE_STORAGE_BUCKET` — default `candidate-evidence`

Render injects `PORT`. The Docker command already respects it.
