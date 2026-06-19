# Code Review

Date: 2026-06-16
Scope: entire repository (backend FastAPI, frontend Next.js, Docker, scripts, docs, tests)

Overall the MVP is well-structured: clean route/service/repository layering, a single shared board-JSON shape across frontend/API/DB/AI, optimistic concurrency, and unit/integration/e2e tests at every layer (60 passing). The findings below are improvements, ordered by severity. Each has a concrete action. Nothing here blocks the documented Docker MVP path; several items matter for the local-dev path, data integrity, and future hardening.

---

## High

### H1. Local (non-Docker) dev mode auth is broken: cross-origin + `credentials: "same-origin"` + no CORS — STATUS: FIXED (2026-06-16)
> Resolved via option (a): `frontend/next.config.ts` now adds a dev-only `/api/*` → `:8000` rewrite (and keeps `output: "export"` only for production builds); `scripts/start-unix.sh` and `start-windows.ps1` no longer set `NEXT_PUBLIC_API_BASE_URL`, so dev fetches stay same-origin on `:3000`. CLAUDE.md updated.
- **Where:** `scripts/start-unix.sh` (sets `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` for the frontend on `:3000`), `frontend/src/components/AppShell.tsx` (all `fetch` use `credentials: "same-origin"`), `backend/app/main.py` (no CORS middleware).
- **Problem:** In `local` mode the frontend runs on `:3000` and calls the backend on `:8000` — a different origin. `credentials: "same-origin"` means the `pm_session` cookie is **not** sent cross-origin, and there is no CORS middleware, so the browser also blocks the responses. Result: login appears to succeed but the session never sticks; the board never loads. The Docker single-origin path is unaffected (everything is served from `:8000`).
- **Action:** Either (a) document that local mode requires a same-origin proxy and add a Next.js `rewrites()` proxy from `/api/*` to `:8000` (keeps `credentials: "same-origin"` valid), or (b) switch fetches to `credentials: "include"` **and** add `CORSMiddleware` with `allow_origins=["http://127.0.0.1:3000"]`, `allow_credentials=True`. Option (a) is simpler and keeps prod/dev behavior identical.

### H2. Column rename fires a board PUT on every keystroke — STATUS: FIXED (2026-06-16)
> `AppShell.persistBoardUpdate` now accepts `{ debounce }`; `KanbanBoard.handleRenameColumn` passes `debounce: true`, so rename edits persist on a 500ms trailing debounce (drag/add/delete still save immediately). Pending debounced saves are flushed before AI chat and cleared on logout/unmount.
- **Where:** `frontend/src/components/KanbanColumn.tsx:42-47` (`onChange={(e) => onRename(...)}`) → `KanbanBoard.handleRenameColumn` → `AppShell.persistBoardUpdate`.
- **Problem:** Each character typed in a column title triggers a full `PUT /api/board`. This is wasteful and is the exact rapid-edit pattern that triggers the version-lag bug in H3, producing spurious 409s and reload churn while typing.
- **Action:** Debounce persistence for text edits (e.g. 400–600ms trailing debounce on rename), or commit on blur/Enter while keeping local state responsive. Keep drag/add/delete as immediate saves.

---

## Medium

### M1. `boardVersionRef` lags behind state, causing spurious 409s on rapid successive saves — STATUS: FIXED (2026-06-16)
> `boardVersion` state and its syncing `useEffect` were removed; `boardVersionRef` is now the synchronous source of truth, updated inline at every version change (load, save success, AI chat, logout). Queued saves now always read a current `expectedVersion`.
- **Where:** `frontend/src/components/AppShell.tsx:49-54, 161-208`.
- **Problem:** `persistBoardUpdate` reads the expected version from `boardVersionRef.current`, but that ref is only updated in a `useEffect` after render. Queued saves run synchronously in the promise chain after `setBoardVersion(payload.version)`, before the effect flushes — so the next save can send a stale `expectedVersion`, get a 409, and `loadBoard()` then overwrites in-flight local edits with server state.
- **Action:** Update the ref synchronously inside the save callback right after reading the response (`boardVersionRef.current = payload.version`) instead of relying on the effect. Consider also dropping the separate `boardVersion` state if the ref becomes the source of truth for saves.

### M2. AI board replacement is full-document overwrite with only structural validation — STATUS: PARTIALLY ADDRESSED (2026-06-16)
> Reliability improved: `run_board_assistant` now sends `response_format: {"type": "json_object"}` (with the existing `_parse_json_from_text` retained as a fallback). The deeper safety concern — preventing semantically destructive AI overwrites (preview/diff or identity-preservation) — is NOT yet implemented and remains open.
- **Where:** `backend/app/services.py:run_ai_chat`, `backend/app/ai.py:run_board_assistant`, `backend/app/models.py:BoardData`.
- **Problem:** The model returns a complete `updatedBoard` that wholesale replaces stored state. `BoardData` validates referential consistency (every `cardId` resolves, `card.id == key`) but not semantic safety — a confused model can drop columns/cards, reorder everything, or rewrite card text, and it will validate and persist. There is no diff/confirmation.
- **Action (MVP-appropriate):** At minimum, request OpenRouter JSON/structured output mode instead of relying on prompt + regex JSON extraction (`_parse_json_from_text`) for reliability. For safety, consider validating that the AI result preserves card/column identity unless the user explicitly asked to delete, or surface a preview before applying. Document the trade-off either way.

### M3. Board model permits orphan cards and duplicate card placement — STATUS: FIXED (2026-06-16)
> `BoardData.validate_card_references` now also rejects duplicate column ids, a card placed in multiple columns, and orphan cards (in `cards` but no column). Covered by three new tests in `backend/tests/unit/test_models.py`.
- **Where:** `backend/app/models.py:BoardData.validate_card_references`.
- **Problem:** Validation guarantees every referenced `cardId` exists, but does not require every card in `cards` to be referenced by a column (orphans persist invisibly and bloat storage), nor that a `cardId` appears in only one column (a card could be listed in two columns). It also does not enforce unique column `id`s.
- **Action:** Add validation: (1) each card key appears in exactly one column's `cardIds`, (2) no duplicate `cardId` across columns, (3) unique column ids. Keep messages specific for debuggability.

### M4. Session cookie is a static, unsigned constant
- **Where:** `backend/app/services.py:SESSION_COOKIE_VALUE = "authenticated"`.
- **Problem:** Auth is "is the cookie value the literal string `authenticated`." Anyone can set `pm_session=authenticated` and bypass login entirely; there is no per-user binding or expiry beyond the cookie max-age. This is acceptable for a local single-user MVP but is a real auth gap to track before any shared/remote deployment.
- **Action:** When moving beyond local MVP, issue a signed/opaque session token (e.g. `itsdangerous`-signed or random token stored server-side) bound to the `users` row, and align it with the DB user identity that board lookups already assume (`DATABASE.md` notes this alignment is still pending).

---

## Low / Maintainability

### L1. `initialize_database()` runs on every board read and write — STATUS: FIXED (2026-06-16)
> Gated with a module-level `_initialized_paths` set so init (migrations + bootstrap) runs once per DB path; subsequent reads/writes skip straight to their own connection.
- **Where:** `backend/app/repository.py:get_board`, `update_board` both call `initialize_database`, which opens a connection, globs/applies migrations, and bootstraps on **every** call.
- **Action:** Run initialization once at startup (it is already called in `create_app`) and have `get_board`/`update_board` assume an initialized DB, or guard with a module-level "initialized" flag. Minor for SQLite/MVP scale but easy to fix.

### L2. Duplicated default board data and stale frontend seed
- **Where:** `backend/app/repository.py:DEFAULT_BOARD` and `frontend/src/lib/kanban.ts:initialData` are byte-for-byte the same board; the frontend now loads from the API, so `initialData` is effectively dead at runtime.
- **Action:** Confirm `initialData` is only used by tests; if so, move it into the test fixture or clearly mark it test-only to prevent drift between two "source of truth" boards.

### L3. Backend `AGENTS.md` is stale (says "Current Scope (Part 6)", "Planned: add AI routes") — STATUS: FIXED (2026-06-16)
> Rewritten to reflect the completed Part 10 scope (full endpoint list, module responsibilities, test/uv conventions).
- **Where:** `backend/AGENTS.md`.
- **Problem:** AI routes, board API, and structured chat are all implemented (Part 10 complete per `docs/PLAN.md`), but the doc still frames AI as planned future work.
- **Action:** Update to reflect the current Part 10 scope, or delete in favor of `CLAUDE.md` + `docs/`.

### L4. Unused/extra secrets in `.env` — STATUS: FIXED (2026-06-16)
> Removed `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`; only `OPENROUTER_API_KEY` remains. (`.env` is gitignored and was never committed.)
- **Where:** `.env` contains `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and `OPENROUTER_API_KEY`; only `OPENROUTER_API_KEY` is read (`backend/app/ai.py`).
- **Action:** Remove the two unused keys to follow least-privilege and avoid shipping unnecessary secrets into the container via `env_file`. (`.env` is correctly gitignored and absent from history — verified.)

### L5. AI error fallback pollutes conversation history — STATUS: FIXED (2026-06-16)
> `ChatMessage` gained a `transient` flag; the error notice is appended with `transient: true`, and `trimChatHistory` filters transient messages out of the payload sent to the AI (still rendered in the thread).
- **Where:** `frontend/src/components/AppShell.tsx:248-256`.
- **Problem:** On a failed chat request, a synthetic assistant message ("I could not process that request...") is appended to `chatMessages`, which then gets sent as real assistant context in the next request's `history`.
- **Action:** Track transient error messages separately (or flag them) so they are rendered but excluded from `trimChatHistory` payloads.

### L6. Unnecessary indirection: `json_loads` / `json_dumps` wrappers with inline imports — STATUS: FIXED (2026-06-16)
> Removed both wrappers; `ai.py` imports `json` at module top and calls `json.loads`/`json.dumps` directly.
- **Where:** `backend/app/ai.py` defines `json_loads`/`json_dumps` that `import json` inside the function body.
- **Action:** Import `json` at module top and call it directly; drop the wrappers. Minor simplification consistent with the project's "keep it simple" standard.

### L7. Container runs as root; new `httpx.Client` per AI call
- **Where:** `Dockerfile` (no `USER`), `backend/app/ai.py:_post_chat`.
- **Action:** Add a non-root `USER` in the final image stage for basic hardening. Optionally reuse a single `httpx.Client` for AI calls. Both are low priority for local MVP.

---

## Tests

### T1. Backend pytest path fragility (already addressed this session)
- A `backend/conftest.py` now puts `backend/` on `sys.path` so `uv run --project backend pytest` works from the repo root or `backend/`. No further action; noting for completeness.

### T2. Coverage gaps worth adding
- No test asserts the version-conflict/reload UX in `persistBoardUpdate` (relevant to M1), and no backend test covers orphan/duplicate-card rejection (relevant to M3). The e2e suite fully mocks `/api/*`, so it does not exercise the real backend contract end-to-end.
- **Action:** Add a unit test for rapid sequential saves (M1), backend validation tests for M3 once implemented, and consider one e2e (or integration) test that runs against the real FastAPI app rather than mocked routes.

---

## Notable strengths (keep)
- Clean separation: routes (`main.py`) → orchestration (`services.py`) → data (`repository.py`) → validation (`models.py`).
- Optimistic concurrency with `version` is implemented consistently across manual saves and AI updates.
- Path-traversal guard in the static catch-all (`is_relative_to`), and `api/` paths explicitly excluded from the frontend fallback.
- AI failures map to clean HTTP codes (502/503) and never crash the app; key-absent degrades gracefully.
- Migrations tracked via `PRAGMA user_version`; DB auto-creates and self-heals.
- `SameSite=Lax` + `HttpOnly` on the session cookie mitigates CSRF and JS access for the MVP.

---

## Suggested order of work
1. H1 (local dev proxy/CORS) and H2 (debounce rename) — restore dev mode and stop save churn.
2. M1 (version ref sync) — fixes the correctness bug H2 exposes.
3. M3 (board integrity validation) and M2 (AI structured output) — data safety.
4. M4 + DB user alignment — before any non-local deployment.
5. L-series cleanups and T2 coverage as follow-ups.
