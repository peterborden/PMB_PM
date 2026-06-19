# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repo. This file is loaded into the agent's context every session, so it holds **rules, commands, and pointers** — not narrative. Human-facing rationale lives in `docs/` and the `AGENTS.md` files; this file links to them rather than restating them.

## What this is

A Project Management MVP: a single-board Kanban app with cookie-based sign-in and an AI sidebar chat that can read and rewrite the board. Next.js frontend, FastAPI backend, SQLite storage, OpenRouter for AI. Runs as one Docker container in production-style local use, with a two-server mode for development.

Authoritative docs: `docs/PLAN.md` (incremental build plan, all 10 parts complete), `docs/AI_CONTRACT.md` (`/api/ai/chat` schemas), `docs/DATABASE.md` (schema + storage rationale). Component guides: `AGENTS.md` at root, `backend/`, `frontend/`, `scripts/`.

## Invariants (do not violate)

- **One board per user.** There is no multi-board path; don't add one.
- **Board JSON has one shape** shared by frontend, API, and AI contract (see Board data model below). Validate any board you produce against it.
- **Every `cardId` in a column must exist in `cards`, and each card's `id` must equal its map key.** `BoardData` enforces this on both client saves and AI output — don't bypass it.
- **All writes are version-checked.** Reads return a `version`; writes pass `expectedVersion`; a mismatch is a `VersionConflictError` -> HTTP 409. After any save or AI update, the frontend must refresh from the canonical board/version in the response — never assume the local copy is current.
- **Routes stay thin.** `main.py` only defines routes and maps exceptions to status codes; logic goes in `services.py` and below.

## Don'ts (defaults that will bite you)

- **Don't point the frontend at an absolute backend URL.** Dev fetches must stay relative (`/api/...`). In dev, `next dev` proxies `/api/*` to `:8000` via `rewrites()` to keep requests same-origin so the `pm_session` cookie flows without CORS. An absolute URL breaks the cookie.
- **Don't over-engineer.** No defensive code, no speculative abstractions, no unrequested features.
- **Don't guess when debugging.** Find the root cause with evidence before fixing.
- **No emojis, anywhere.**

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

The backend uses `uv` (no separate venv activation). Frontend config is mode-dependent (`frontend/next.config.ts`): production is a Next.js **static export** (`output: "export"`) served by FastAPI from `frontend/out` (same origin); development uses `next dev` with the `/api/*` proxy described in Don'ts.

## Architecture

For exact behavior, read the named symbol — this section is a map, not a spec.

### Request flow and serving model
`backend/app/main.py:create_app` builds the app and mounts everything. All API routes are under `/api/*`; a catch-all `GET /{path:path}` serves the static frontend export (SPA-style fallback to `index.html`), or a 503 placeholder if the export is missing. Container path is `/app/frontend-out` via `FRONTEND_STATIC_DIR`; locally it falls back to `frontend/out`.

`create_app(frontend_static_dir?, db_path?, ai_client?)` — the optional params are the seam tests use to inject a temp DB and a fake AI client.

### Backend layering (`backend/app/`)
- `main.py` — route definitions only; exceptions -> HTTP status codes.
- `services.py` — auth + orchestration: `login`/`logout`, `read_board`/`save_board`, `run_ai_chat`. Owns the `pm_session` cookie and the hardcoded `user`/`password` credentials. `require_authenticated_username` is the auth gate and returns the MVP username used for board lookup.
- `repository.py` — all SQLite access. `initialize_database` is idempotent (creates the DB file, applies migrations by `PRAGMA user_version`, bootstraps the MVP user + seeded `DEFAULT_BOARD`); it runs on the first board read/write per DB path (memoized via `_initialized_paths`), so a missing DB self-heals on startup. `update_board` does the version-checked write (see Invariants).
- `models.py` — Pydantic models. `BoardData` enforces the board consistency invariant.
- `ai.py` — `OpenRouterClient` (`from_env`). Model defaults to `openai/gpt-oss-120b`; configurable via `OPENROUTER_MODEL`/`OPENROUTER_BASE_URL`/`OPENROUTER_TIMEOUT_SECONDS`. Raises `AIConfigError` (-> 503) and `AIRequestError` (-> 502).

### Board data model (shared shape)
Stored as one JSON document in `boards.board_json`:
```
{ "columns": [{ "id": "...", "title": "...", "cardIds": ["card-id"] }],
  "cards": { "card-id": { "id": "card-id", "title": "...", "details": "..." } } }
```
Cards are a normalized map; columns own ordering via `cardIds`.

### AI chat flow
`POST /api/ai/chat` (exact schemas in `docs/AI_CONTRACT.md`). `run_ai_chat` injects the full current board JSON + conversation history, instructs the model to return strict JSON `{ reply, updatedBoard|null }`, then `ai.py` strips markdown fences, extracts the JSON object, and validates against `BoardAssistantOutput`/`BoardData` before persisting. `updatedBoard: null` returns the board unchanged with `boardUpdated: false`. The flow reads the current version and persists with it, so concurrent edits during an AI call surface as 409s.

### Frontend (`frontend/src/`)
Next.js App Router + React 19 + Tailwind v4, drag-and-drop via `@dnd-kit`. `components/AppShell.tsx` is the top-level controller: gates on auth, loads the board from `/api/board`, persists version-aware saves, hosts the AI chat panel. `KanbanBoard`/`KanbanColumn`/`KanbanCard` are presentation controlled by AppShell state. `lib/kanban.ts` holds board types and `moveCard` (within- and cross-column moves); `lib/aiChat.ts` holds chat history helpers. Full component map: `frontend/AGENTS.md`.

## Conventions

- Color tokens (`frontend/src/app/globals.css`): accent yellow `#ecad0a`, blue `#209dd7`, purple `#753991`, navy `#032147`, gray text `#888888`.
- (Code-style and simplicity rules are under Don'ts above.)

## Config

`.env` at the repo root holds `OPENROUTER_API_KEY` (required for AI routes; absent key makes AI routes return 503 but the rest of the app works). docker-compose passes it via `env_file`. DB path overridable with `PM_DB_PATH` (defaults to `db.sqlite3` at repo root).
