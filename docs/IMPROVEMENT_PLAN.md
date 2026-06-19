# Improvement Plan: user management, multiple boards, and more

Tracking doc for the multi-iteration effort to add user accounts, multiple
Kanban boards per user, and additional features. Each iteration should leave the
tree green (`uv run --project backend pytest`, `npm run test:unit` in
`frontend/`) and commit a coherent chunk. Read this first, then check git log.

## Status

- [x] **Iteration 1 — Backend foundation (commit 03da5d2)**
  - PBKDF2 password hashing + session tokens (`backend/app/auth.py`)
  - Migration `0002`: `sessions` table; `boards` rebuilt for many-per-user
    (`name`, `position`, dropped `UNIQUE(user_id)`)
  - Repository: user/session CRUD; board CRUD scoped by `user_id`
  - Routes: `/api/auth/register|login|logout|session`,
    `/api/boards` (list/create), `/api/boards/{id}` (get/put/patch/delete),
    `/api/boards/{id}/ai/chat`. Legacy `/api/board` + `/api/ai/chat` kept on the
    user's default board for the not-yet-migrated frontend.
  - Tests: `test_auth.py`, `test_repository.py`, `test_boards_api.py`.

## Next iterations (suggested order)

- [ ] **Iteration 2 — Frontend auth + API client**
  - Register screen (in addition to login); show signed-in username + logout.
  - `frontend/src/lib/api.ts` (or similar) typed client for the new endpoints.
  - Keep dev fetches relative (`/api/...`) — see CLAUDE.md Don'ts.
- [ ] **Iteration 3 — Frontend multi-board UI**
  - Board switcher/sidebar listing `/api/boards`; create/rename/delete.
  - AppShell loads a selected board via `/api/boards/{id}`, saves version-aware,
    and points AI chat at `/api/boards/{id}/ai/chat`. Retire legacy `/api/board`
    usage from the frontend once migrated.
- [ ] **Iteration 4 — Card-level features**
  - Candidates: card labels/tags, due dates, assignee, description markdown,
    card search/filter. Extend `BoardData` (keep the shared shape in sync across
    frontend, API, AI contract) and migrate `board_json` defensively.
- [ ] **Iteration 5 — Hardening + e2e**
  - Playwright flows for register -> create board -> drag cards -> AI edit.
  - Backend e2e for multi-user. Tighten coverage of new code paths.
- [ ] **Iteration 6 — Polish + docs**
  - Update `docs/AI_CONTRACT.md`, `frontend/AGENTS.md`, `backend/AGENTS.md`.
  - Review for the "Don'ts" (no over-engineering, no emojis), final test pass.

## Notes / gotchas

- Seeded MVP account stays `user`/`password`; bootstrap heals its old
  placeholder hash to a real PBKDF2 hash on first init.
- Board access MUST be scoped by `user_id` (see CLAUDE.md invariants).
- Session cookie name is `pm_session`; value is now an opaque token, not the
  old static `"authenticated"` string.
