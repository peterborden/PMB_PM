# Code Review

**Date:** 2026-06-16
**Scope:** Full repository (backend FastAPI, frontend Next.js, Docker, scripts, docs, tests)
**Total files reviewed:** ~74 source/config files

---

## Summary

The MVP is well-structured overall: clean route/service/repository layering, a consistent board-JSON shape across all layers (frontend, API, DB, AI contract), optimistic concurrency with versioning, and tests at unit/integration/e2e levels. An earlier review (in `code_review.md`) identified 13 items, of which 9 were fixed. This fresh review covers what remains open and identifies new issues.

Total open items: 6 (1 high, 3 medium, 6 low/maintainability, 3 test gaps)

---

## High Severity

### H1. `@dnd-kit/sortable` v10 incompatible with `@dnd-kit/core` v6

**Where:** `frontend/package.json:17-19`

```json
"@dnd-kit/core": "^6.3.1",
"@dnd-kit/sortable": "^10.0.0",
"@dnd-kit/utilities": "^3.2.2",
```

**Problem:** `@dnd-kit/sortable` v10 has a peer dependency on `@dnd-kit/core@^10.0.0`. Resolving `sortable@10` alongside `core@6` produces incompatible dependency versions. `npm install` will emit peer dep warnings, and at runtime `useSortable`, `SortableContext`, and `verticalListSortingStrategy` may fail because they expect internal types/hooks from core v10 that do not exist in v6. This likely breaks the entire drag-and-drop feature.

**Evidence:** The Playwright e2e test "moves a card between columns" (`frontend/tests/kanban.spec.ts:242`) exercises this path; it is mocked at the API layer but the DnD components are real. If H1 is real, this test would fail at runtime with JS errors from the mismatched DnD packages.

**Action:** Pin all three `@dnd-kit/*` packages to compatible major versions. Either:
- Downgrade `@dnd-kit/sortable` to `^6.x` (matching core v6), or
- Upgrade `@dnd-kit/core` and `@dnd-kit/utilities` to `^10.x` and verify API compatibility with existing usage.

---

## Medium Severity

### M1. Session cookie is a static, unsigned constant (carried forward from prior review)

**Where:** `backend/app/services.py:17`

```python
SESSION_COOKIE_VALUE = "authenticated"
```

**Problem:** Auth is literally "is the cookie value the string `authenticated`?" Anyone with browser devtools can set `document.cookie = "pm_session=authenticated; path=/"` and bypass login entirely. No server-side session store, no cryptographic signing, no per-user binding. The current user identity lookup (`require_authenticated_username` returns `MVP_USERNAME` regardless) is also hardcoded rather than derived from the session.

**Action:** Acceptable for the documented local MVP scope. Before any remote/shared deployment, replace with a signed/opaque session token (e.g., `itsdangerous`-signed or random token stored server-side) bound to the `users.id` row, and update `require_authenticated_username` to return the actual authenticated user. The `DATABASE.md` already notes that auth-to-DB-user alignment is pending.

### M2. AI board replacement is full-document overwrite — semantic safety still absent (PARTIALLY ADDRESSED from prior review)

**Where:** `backend/app/services.py:run_ai_chat`, `backend/app/ai.py:run_board_assistant`

**Problem:** The model returns a complete `updatedBoard` that wholesale replaces stored state. `BoardData` validates referential integrity (every `cardId` resolves, no orphans, no duplicates) but does **not** validate semantic safety — a confused/hallucinating model can silently drop columns, delete cards, rename everything, or reorder content, and it will validate and persist. The `response_format: {"type": "json_object"}` addition improved parsing reliability but did not address the semantic gap.

**Action:** At minimum, add identity-preservation validation: all pre-existing card and column IDs survive unless the user explicitly asked for deletion in their message. For stronger safety, implement a diff-preview step before applying AI updates. Document the tradeoff either way.

### M3. `BoardUpdateRequest.expectedVersion` is optional, bypassing optimistic concurrency

**Where:** `backend/app/models.py:65-66`

```python
class BoardUpdateRequest(BaseModel):
    board: BoardData
    expectedVersion: int | None = None
```

**Problem:** A `PUT /api/board` without `expectedVersion` skips the version check entirely (`repository.py:199`: `if expected_version is not None and expected_version != current_version`), allowing a blind overwrite without any conflict detection. The frontend always sends it, but the API contract does not enforce this, so any other client or a rogue script can silently clobber the board.

**Action:** Two options: (a) make `expectedVersion` required (breaking change, update frontend), or (b) reject updates missing `expectedVersion` at the service layer with a 400 error, keeping it optional in the model for future backward-compatible clients.

---

## Low Severity / Maintainability

### L1. Pydantic is an undocumented transitive dependency

**Where:** `backend/pyproject.toml:6-10`

```toml
dependencies = [
  "fastapi>=0.116.0",
  "httpx>=0.28.0",
  "uvicorn[standard]>=0.35.0",
]
```

**Problem:** `models.py` directly imports from `pydantic` (`BaseModel`, `Field`, `model_validator`), but pydantic is not listed in `pyproject.toml` — it arrives transitively via FastAPI. This works today but violates explicit-dependency conventions. A future FastAPI major version could change its pydantic dependency range, or uv's resolver could behave unexpectedly if pydantic is pinned indirectly.

**Action:** Add `pydantic>=2.0` explicitly to `[project.dependencies]`.

### L2. Duplicated default board data and stale frontend seed (carried forward from prior review)

**Where:** `backend/app/repository.py:DEFAULT_BOARD` and `frontend/src/lib/kanban.ts:initialData`

**Problem:** Two byte-for-byte identical copies of the same 8-card board JSON (3.1 KB each). The frontend now loads from the API on every render, so `initialData` is dead code at runtime — it is only referenced by tests. The two copies can independently drift over time, creating confusion about which is canonical.

**Action:** Either move `initialData` into the test fixture file, or add a `@deprecated` comment pointing to `DEFAULT_BOARD` in the backend as the canonical seed. Consider adding a CI check that compares them.

### L3. Container still runs as root (carried forward from prior review)

**Where:** `Dockerfile` — final stage has no `USER` directive.

**Action:** Add a non-root user for basic container hardening:

```dockerfile
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --ingroup app app
USER app
```

Low priority for local MVP but trivially fixable.

### L4. Session cookie missing `secure` flag

**Where:** `backend/app/services.py:46-53`

```python
response.set_cookie(
    key=SESSION_COOKIE_VALUE,
    httponly=True,
    samesite="lax",
    max_age=SESSION_MAX_AGE_SECONDS,
    path="/",
)
```

**Problem:** Cookie is not marked `secure=True`. Acceptable for local HTTP development, but if this app is ever accessed over a network without HTTPS (even a LAN demo), the session cookie is transmitted in plaintext.

**Action:** Add `secure=True`. Make it conditional on the request scheme for local dev compatibility: check `request.url.scheme` or use an env var.

### L5. ESLint config may be ESLint-version-sensitive

**Where:** `frontend/eslint.config.mjs:1-3`

```javascript
import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";
```

**Problem:** Two issues:
1. `globalIgnores` was added to the `eslint/config` module relatively recently (ESLint 9.20+). If the lockfile resolves an older ESLint, the import fails.
2. `eslint-config-next/core-web-vitals` and `eslint-config-next/typescript` are import paths from the legacy ESLint 8 flat-config adapter. In ESLint 9, the recommended import is `import nextConfig from "eslint-config-next"`.

**Action:** Update the ESLint config to use the flat-config-native approach: `import nextConfig from "eslint-config-next"` and use `ignores` in the config array instead of `globalIgnores`.

### L6. AI error message phrasing

**Where:** `frontend/src/components/AppShell.tsx:314`

```typescript
"I could not process that request right now. Please try again."
```

**Minor:** "could not" reads slightly stiffly for a transient error. Consider: "I couldn't process that request. Please try again."

---

## Tests

### T1. DnD incompatibility not detected in CI

If H1 is real, the Playwright e2e test `moves a card between columns` (`frontend/tests/kanban.spec.ts:242`) should fail with a JS runtime error from the mismatched `@dnd-kit` packages. This is the most actionable test gap — it would catch the dependency issue before deployment.

**Action:** Run `npx playwright test` after verifying the npm install completes without peer dep warnings to confirm whether DnD works end-to-end.

### T2. No test for `expectedVersion` bypass (M3)

No test asserts behavior of `PUT /api/board` when called without `expectedVersion`. The API silently accepts it.

**Action:** Add integration test in `test_routes.py`:
```python
def test_update_board_without_expected_version_still_succeeds(tmp_path):
    # This documents the current behavior; revisit if M3 is fixed.
```

### T3. Session cookie bypass not tested (M1)

No test verifies that manually setting `pm_session=authenticated` (without going through login) grants access to protected endpoints.

**Action:** Add integration test:
```python
def test_manual_session_cookie_bypasses_login(tmp_path):
    client = TestClient(create_app(db_path=tmp_path / "test.db"))
    client.cookies.set("pm_session", "authenticated")
    response = client.get("/api/board")
    assert response.status_code == 200  # documents the gap
```

---

## Prior Review Item Status Summary

| Item | Status in Current Codebase |
|------|---------------------------|
| H1 (local dev CORS) | FIXED — Next.js dev rewrites in `next.config.ts` |
| H2 (rename debounce) | FIXED — `{ debounce: true }` in `KanbanBoard.tsx:87` |
| M1 (version ref sync) | FIXED — ref updated synchronously in save callback `AppShell.tsx:213` |
| M2 (AI structured output) | PARTIALLY FIXED — `response_format: {"type": "json_object"}` added, no semantic safety |
| M3 (board validation) | FIXED — orphans, duplicates, column uniqueness enforced in `models.py:22-56` |
| M4 (session cookie) | **NOT FIXED** — still hardcoded `"authenticated"` |
| L1 (initialize_database) | FIXED — module-level `_initialized_paths` cache in `repository.py:132` |
| L2 (duplicated board) | **NOT FIXED** — `initialData` still in `frontend/src/lib/kanban.ts` |
| L3 (backend AGENTS.md) | FIXED — up to date with Part 10 scope |
| L4 (extra .env secrets) | FIXED per prior review |
| L5 (transient messages) | FIXED — `transient` flag on `ChatMessage` in `aiChat.ts` |
| L6 (json wrappers) | FIXED — direct `json.loads`/`json.dumps` calls |
| L7 (container root) | **NOT FIXED** — no `USER`, new `httpx.Client` per AI call |

---

## Suggested Order of Work

1. **H1** — Fix `@dnd-kit` version mismatch (showstopper if DnD is broken)
2. **T1** — Run Playwright e2e to confirm/deny H1, fix if failing
3. **M3** — Make `expectedVersion` required or rejected-when-missing
4. **M2** — Add identity-preservation validation for AI updates
5. **M1/M4** — Session hardening before any network exposure
6. **L-series** — Cleanups (pydantic dep, ESLint config, container user, etc.)
7. **T2/T3** — Coverage for known gaps
