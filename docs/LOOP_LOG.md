# Ralph Loop Log

Human-readable record of each improvement loop (newest at the bottom). Tracks
which loop we are in and the major changes that landed. Detailed plan and
remaining work live in `docs/IMPROVEMENT_PLAN.md`.

Goal (standing prompt): "significantly improve this project. Add user
management, multiple kanban boards in a user, and other features, testing
thoroughly as you go and maintaining strong test code coverage and good
integration tests."

| Loop | Theme | Major changes | Tests after loop |
|------|-------|---------------|------------------|
| 1 | Backend foundation | Real user accounts (PBKDF2 hashing), token sessions, multi-board schema (migration 0002) + per-user board CRUD scoped by `user_id`; new auth/board routes; legacy `/api/board` kept on the default board | backend 77 pass |
| 2 | Frontend multi-board | Typed `lib/api.ts` client; login/register; `BoardSwitcher` (create/rename/delete, last-board guard); AppShell tracks the active board and per-board AI chat; updated unit + Playwright tests | backend 77, FE unit 21, e2e 8 |
| 3 | Richer cards + search | Card `labels[]` + `dueDate` end to end (model + validators, AI prompt/contract, creation form, label chips + overdue due-date badge); board search box filtering by title/details/labels | backend 85, FE unit 31, e2e 8 |
| 4 | Card editing | `CardEditor` modal to edit an existing card's title/details/labels/due date and delete it; edit affordance on each card; accessible dialog (Escape/backdrop close) | backend 85, FE unit 38, e2e 9 |

## Loop details

### Loop 1 - Backend foundation (commit 03da5d2)
- `backend/app/auth.py`: PBKDF2-HMAC-SHA256 password hashing + session tokens.
- Migration `0002`: `sessions` table; `boards` rebuilt for many-per-user.
- Repository/services/routes for register/login/logout and board CRUD, all
  scoped by `user_id`. Legacy `/api/board` + `/api/ai/chat` retained.

### Loop 2 - Frontend multi-board (commit 1ae6949)
- `lib/api.ts` typed client (`ApiError` carries HTTP status).
- Register/login toggle; signed-in username shown.
- `BoardSwitcher.tsx` board tabs; AppShell rewritten around an active board.
- Tests migrated to the new endpoints (in-memory server mock) + new coverage.

### Loop 3 - Richer cards + search (this commit)
- Card metadata: optional `labels` (deduped, trimmed, max 10) and `dueDate`
  (ISO `YYYY-MM-DD`, validated) added to the shared Card model; backward
  compatible with existing boards.
- AI prompt + `docs/AI_CONTRACT.md` describe the new card fields and the
  per-board `/api/boards/{id}/ai/chat` route.
- `CardMeta` renders label chips and a due-date badge (red when overdue);
  `NewCardForm` gained labels + due-date inputs.
- Board search box filters cards by title/details/labels (`cardMatchesQuery`).
- New tests: backend `test_card_metadata.py`; frontend helpers
  (`cardMatchesQuery`/`isOverdue`/`formatDueDate`) and board create/search.

### Loop 4 - Card editing (this commit)
- `CardEditor.tsx`: accessible modal (role=dialog, Escape/backdrop close) to edit
  an existing card's title, details, labels, and due date, plus delete.
- Each card gained an Edit affordance next to delete; `onEditCard` threads through
  `KanbanColumn` to `KanbanBoard`, which owns `editingCardId` and applies updates
  via the normal version-checked board save.
- New tests: `CardEditor.test.tsx` (prefill, save/parse labels, empty-title guard,
  Escape/Cancel, clear due date), `KanbanBoard` edit + delete-from-editor, and a
  Playwright edit flow.
