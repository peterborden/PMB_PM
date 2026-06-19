## Backend Overview

The backend is a FastAPI service for the Project Management MVP. It serves the
exported frontend and provides the JSON API for auth, the Kanban board, and the
AI assistant. The MVP (PLAN.md Parts 1-10) is complete.

### API Endpoints

- `GET /api/health` - service health
- `GET /api/auth/session` - login state check
- `POST /api/auth/login` - cookie sign-in (`user` / `password`)
- `POST /api/auth/logout` - clear session
- `GET /api/hello` - protected hello-world payload
- `GET /api/board` / `PUT /api/board` - authenticated board read/update with
  optimistic concurrency (`version` / `expectedVersion`, 409 on conflict)
- `GET /api/ai/diagnostic` - OpenRouter `2+2` connectivity check
- `POST /api/ai/chat` - structured AI reply plus optional board update
- `GET /{path:path}` - fallback that serves the static frontend export

### Structure (`backend/app/`)

- `main.py` - app factory (`create_app`) and route definitions; maps exceptions
  to HTTP status codes
- `services.py` - auth and request orchestration; owns the cookie session and
  hardcoded MVP credentials
- `repository.py` - SQLite access; idempotent DB init (migrations via
  `PRAGMA user_version`), MVP user/board bootstrap, optimistic-locked updates
- `models.py` - Pydantic models; `BoardData` enforces board integrity
  (referenced cards exist, ids match keys, unique columns, no duplicate
  placement or orphan cards) on every write path
- `ai.py` - `OpenRouterClient` (model `openai/gpt-oss-120b`); requests JSON
  output and validates structured results before applying board changes

### Conventions

- Managed with `uv` (`backend/pyproject.toml`); run tests with
  `uv run --project backend pytest` from the repo root or `backend/`
  (`backend/conftest.py` handles the import path)
- Tests live under `backend/tests/{unit,integration,e2e}`; the live OpenRouter
  e2e test is env-gated
