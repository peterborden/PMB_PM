# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Project Management MVP: a single-board Kanban app with cookie-based sign-in and an AI sidebar chat that can read and rewrite the board. Next.js frontend, FastAPI backend, SQLite storage, OpenRouter for AI. Designed to run as one Docker container in production-style local use, with a two-server mode for development.

Authoritative docs live in `docs/`: `PLAN.md` (the incremental build plan, all 10 parts complete), `AI_CONTRACT.md` (the `/api/ai/chat` request/output/response schemas), `DATABASE.md` (schema and storage rationale). Component-level guides are in `AGENTS.md` files at the root, `backend/`, `frontend/`, and `scripts/`.

## Commands

Run from the repo root unless noted.

```bash
# Production-style: single container serving API + built frontend at http://127.0.0.1:8000
./scripts/start-mac.sh            # or start-linux.sh; docker mode is the default
./scripts/stop-mac.sh

# Local dev: backend (uvicorn :8000) + Next dev server (:3000) with hot reload
./scripts/start-mac.sh local      # pids/logs land in .run/
./scripts/stop-mac.sh local

# Backend tests (uv-managed; pytest config in backend/pyproject.toml)
# Runs from repo root or backend/ — backend/conftest.py puts backend/ on sys.path either way.
uv run --project backend pytest                         # unit + integration
uv run --project backend pytest backend/tests/unit/test_ai.py::test_name   # single test
# e2e tests under backend/tests/e2e hit a live server/OpenRouter and are env-gated

# Frontend (run inside frontend/)
npm run dev            # Next dev server
npm run build          # static export -> frontend/out (what the container serves)
npm run lint
npm run test:unit      # vitest
npm run test:e2e       # playwright (auto-starts dev server on :3000)
npm run test:all
```

The backend uses `uv` (no separate venv activation needed). Frontend config is mode-dependent (`frontend/next.config.ts`): in production it is a Next.js **static export** (`output: "export"`) served by FastAPI from `frontend/out` (same origin); in development `next dev` instead proxies `/api/*` to the backend on `:8000` via `rewrites()`, keeping requests same-origin so the session cookie flows without CORS. Because of this, dev fetches must stay relative (`/api/...`) — do not point the frontend at an absolute backend URL in local mode.

## Architecture

### Request flow and serving model
`backend/app/main.py:create_app` builds the FastAPI app and mounts everything. All API routes are under `/api/*`; a catch-all `GET /{path:path}` serves the static frontend export for any non-API path (with SPA-style fallback to `index.html`). In the container the export is at `/app/frontend-out` via `FRONTEND_STATIC_DIR`; locally it falls back to `frontend/out`. If the export is missing, the catch-all returns a 503 placeholder page instead of crashing.

`create_app` takes optional `frontend_static_dir`, `db_path`, and `ai_client` parameters — this is the seam tests use to inject a temp DB and a fake AI client.

### Backend layering (`backend/app/`)
Routes are thin and delegate downward:
- `main.py` — route definitions only; translates exceptions to HTTP status codes.
- `services.py` — auth + request orchestration (`login`/`logout`, `read_board`/`save_board`, `run_ai_chat`). Owns the cookie session (`pm_session`) and the hardcoded `user`/`password` credentials. `require_authenticated_username` is the auth gate; it returns the MVP username used for board lookup.
- `repository.py` — all SQLite access. `initialize_database` is idempotent: it creates the DB file, applies migrations by `PRAGMA user_version`, and bootstraps the MVP user + a seeded `DEFAULT_BOARD` if absent. **It is called on every board read/write**, so the DB self-heals if deleted. Writes use `update_board` with optimistic concurrency via a `version` integer.
- `models.py` — Pydantic models. `BoardData` enforces internal consistency (every `cardId` in a column must exist in `cards`, and each card's `id` must match its map key). This validation runs on both client saves and AI output.
- `ai.py` — `OpenRouterClient` (built from env via `from_env`). Model defaults to `openai/gpt-oss-120b`; configurable via `OPENROUTER_MODEL`/`OPENROUTER_BASE_URL`/`OPENROUTER_TIMEOUT_SECONDS`. Raises `AIConfigError` (-> 503) and `AIRequestError` (-> 502).

### Board data model (shared shape)
The board is a single JSON document stored in `boards.board_json`, the same shape used by the frontend, the API, and the AI contract:
```
{ "columns": [{ "id, title, cardIds: [] }], "cards": { "card-id": { id, title, details } } }
```
Cards are a normalized map; columns own the ordering via `cardIds`. There is one board per user.

### Optimistic concurrency (important when editing save logic)
Every board read returns a `version`. Writes pass `expectedVersion`; if it doesn't match the stored version, `update_board` raises `VersionConflictError` -> HTTP 409. The frontend must refresh from the canonical board/version in the response after any save or AI update. The AI chat flow reads the current version, applies the model's `updatedBoard`, and persists with that version — so concurrent edits during an AI call surface as 409s.

### AI chat flow
`POST /api/ai/chat` (see `docs/AI_CONTRACT.md` for exact schemas). `run_ai_chat` injects the full current board JSON + conversation history into the prompt. The model is instructed to return strict JSON `{ reply, updatedBoard|null }`. `ai.py` strips markdown fences, extracts the JSON object, and validates it against `BoardAssistantOutput`/`BoardData` before anything is persisted. If `updatedBoard` is null, the board is returned unchanged with `boardUpdated: false`.

### Frontend (`frontend/src/`)
Next.js App Router + React 19 + Tailwind v4, drag-and-drop via `@dnd-kit`. `components/AppShell.tsx` is the top-level controller: it gates on auth, loads the board from `/api/board`, persists edits with version-aware saves, and hosts the AI chat panel. `KanbanBoard`/`KanbanColumn`/`KanbanCard` are presentation controlled by AppShell state. `lib/kanban.ts` holds board types and `moveCard` (within- and cross-column move logic); `lib/aiChat.ts` holds chat history helpers. See `frontend/AGENTS.md` for the full component map.

## Conventions (from AGENTS.md)

- Keep it simple; do not over-engineer or add defensive code or unrequested features.
- When debugging, find the root cause with evidence before fixing — do not guess.
- No emojis, anywhere.
- Color tokens (in `frontend/src/app/globals.css`): accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`, navy `#032147`, gray text `#888888`.

## Config

`.env` at the repo root holds `OPENROUTER_API_KEY` (required for AI routes; absent key makes AI routes return 503 but the rest of the app works). docker-compose passes it via `env_file`. DB path overridable with `PM_DB_PATH` (defaults to `db.sqlite3` at repo root).
