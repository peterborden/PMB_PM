# Project Management MVP Plan

This plan is execution-oriented and designed for incremental delivery with tests at each stage.

## Agreed Constraints

- Single Docker container for production-style local run
- Also provide local non-Docker developer helpers in `scripts/`
- Login can be simple for MVP (`user` / `password`)
- Testing standard across the project: unit + integration + e2e
- Structured output schema for AI workflow will be proposed in Part 9
- Key-gate check-ins only (not sign-off at every part)

## Key Gates

- Gate 1 (post Part 4): containerized app serves frontend and simple auth flow works end-to-end
- Gate 2 (post Part 7): persistent Kanban via backend + SQLite works end-to-end
- Gate 3 (post Part 10): AI sidebar chat with structured updates works end-to-end

## Part 1: Planning and Documentation

### Checklist

- [x] Expand `docs/PLAN.md` into an implementation checklist with tests and success criteria
- [x] Add `frontend/AGENTS.md` documenting current frontend code
- [x] Confirm part ordering and gate definitions still match priorities

### Tests

- [x] Documentation review for internal consistency and no contradictory requirements

### Success Criteria

- Plan is explicit enough to execute without ambiguous sequencing decisions
- Test expectations are clear for each implementation part

## Part 2: Scaffolding (Backend + Docker + Scripts)

### Checklist

- [x] Create `backend/` FastAPI scaffold with health and example API endpoint
- [x] Add backend dependency management with `uv` (project config + lock workflow)
- [x] Add Dockerfile for single-container FastAPI runtime scaffolding
- [x] Add container entrypoint wiring for serving API and static content
- [x] Add cross-platform scripts in `scripts/` for:
  - [x] Docker start/stop
  - [x] Local non-Docker start/stop for frontend and backend
- [x] Serve simple hello-world page and verify API response wiring

### Tests

- [x] Unit: backend health/example route tests
- [x] Integration: container boot test validates both static page and API route
- [x] E2E: script-driven smoke test hits `/` and `/api/hello`

### Success Criteria

- `scripts` can start/stop both Docker and local dev modes reliably
- Running container serves static page and API from one process boundary
- Base backend scaffolding is ready for real Kanban endpoints

## Part 3: Add Existing Frontend into Served App

### Checklist

- [x] Integrate current Next.js frontend build output into backend-serving flow
- [x] Ensure `/` renders the existing Kanban board in containerized mode
- [x] Preserve frontend styling and drag/drop behavior
- [x] Wire a simple fallback route strategy for static assets/pages

### Tests

- [x] Unit: frontend utility/component tests continue passing
- [x] Integration: static asset serving and route handling from backend
- [x] E2E: Kanban board renders with expected columns in Docker mode

### Success Criteria

- Existing Kanban UI is fully visible at `/` through FastAPI serving path
- No regressions in frontend core interactions

## Part 4: Simple Sign-In Experience

### Checklist

- [x] Add login UI gate before accessing board
- [x] Implement simple credential check (`user` / `password`)
- [x] Add basic logged-in session persistence for browser refresh
- [x] Add logout that clears session and returns user to login
- [x] Restrict board/API access when not authenticated

### Tests

- [x] Unit: auth helper validation and session helper behavior
- [x] Integration: protected route behavior and login/logout transitions
- [x] E2E: login success, login failure, logout, refresh retains session

### Success Criteria

- Unauthenticated users cannot access the Kanban board
- Auth flow is stable and minimal without unnecessary complexity

## Part 5: Database Modeling (Best-Practice MVP)

### Checklist

- [x] Propose schema in docs for users + one-board-per-user model
- [x] Define SQLite tables and JSON storage strategy for board state
- [x] Document migration/bootstrap strategy (auto-create DB if missing)
- [x] Document reasoning and tradeoffs

### Tests

- [ ] Unit: schema validation helpers
- [ ] Integration: DB initialization and read/write round-trip
- [ ] E2E: persistence survives app restart

### Success Criteria

- Schema supports current MVP and future multi-user extension
- JSON board storage approach is documented and implementable

## Part 6: Backend Kanban API

### Checklist

- [ ] Implement board read endpoint for current authenticated user
- [ ] Implement board update endpoint(s) for card/column state changes
- [ ] Add input validation and clear API error responses
- [ ] Ensure DB auto-creation and seed behavior on first run
- [ ] Add API-layer separation (routes, services, data access) with simple structure

### Tests

- [ ] Unit: service-layer board transformation and validation behavior
- [ ] Integration: API + DB end-to-end contract tests
- [ ] E2E: authenticated API usage from realistic client flow

### Success Criteria

- Backend can reliably persist and return per-user board state
- API contracts are stable for frontend integration

## Part 7: Frontend + Backend Integration

### Checklist

- [ ] Replace in-memory frontend board state initialization with backend fetch
- [ ] Persist all board edits through backend API
- [ ] Handle loading/error states with simple UX
- [ ] Keep drag/drop/add/delete/rename behavior consistent

### Tests

- [ ] Unit: data mapping and API client helpers
- [ ] Integration: component tests with mocked API success/failure
- [ ] E2E: real persistence through reload/restart scenarios

### Success Criteria

- Kanban operations are persistent across sessions and restarts
- Frontend behavior remains responsive and predictable

## Part 8: AI Connectivity (OpenRouter Baseline)

### Checklist

- [ ] Add backend AI client configured by `OPENROUTER_API_KEY`
- [ ] Use model `openai/gpt-oss-120b`
- [ ] Implement simple diagnostic route/task that asks AI `2+2`
- [ ] Add robust timeout and error reporting for AI calls

### Tests

- [ ] Unit: AI client request builder and response parser
- [ ] Integration: mocked OpenRouter interaction tests
- [ ] E2E: optional live connectivity smoke test (env-gated)

### Success Criteria

- Backend can successfully call OpenRouter with configured model
- AI failures are surfaced cleanly without crashing app flows

## Part 9: Structured AI Board Assistant Contract

### Checklist

- [ ] Propose structured output schema for:
  - [ ] Assistant reply text
  - [ ] Optional board update instruction payload
- [ ] Add conversation history handling in backend AI request flow
- [ ] Include full board JSON context in AI prompt input
- [ ] Validate structured output before applying board updates
- [ ] Document contract and examples in `docs/`

### Tests

- [ ] Unit: schema validation and update-application logic
- [ ] Integration: backend route with mocked structured AI responses
- [ ] E2E: chat prompt yielding no-op and update responses

### Success Criteria

- AI responses are deterministic to parse and safe to apply
- Optional board updates can be applied without UI hacks

## Part 10: UI AI Sidebar + Auto Refresh

### Checklist

- [ ] Build right-sidebar chat widget integrated with backend chat route
- [ ] Show conversation history in UI with clear loading states
- [ ] Apply AI-provided board updates automatically after successful responses
- [ ] Refresh UI state from canonical backend response after updates
- [ ] Keep layout polished and consistent with color/theme requirements

### Tests

- [ ] Unit: chat state reducer/helpers
- [ ] Integration: sidebar + board interaction tests
- [ ] E2E: user asks AI to modify board and UI updates automatically

### Success Criteria

- Sidebar supports full chat interaction with stable UX
- AI-triggered board updates appear immediately and correctly
- End-to-end product goal is met in local Docker workflow