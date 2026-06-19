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

- [x] **Iteration 2 — Frontend auth + multi-board UI (this commit)**
  - `frontend/src/lib/api.ts`: typed client for auth/boards/AI chat (`ApiError`).
  - Register screen + login toggle; signed-in username shown in the AI panel.
  - `components/BoardSwitcher.tsx`: board tabs with select/create/rename/delete
    (last-board guard), rendered in the `KanbanBoard` header `toolbar` slot.
  - AppShell rewritten to list boards, track the active board, save version-aware
    via `/api/boards/{id}`, and chat via `/api/boards/{id}/ai/chat`. Frontend no
    longer calls the legacy `/api/board` route.
  - Tests: rewrote `AppShell.test.tsx` (in-memory server) + `BoardSwitcher.test.tsx`
    + updated Playwright `kanban.spec.ts` to the new endpoints. 21 unit + 8 e2e green.
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
