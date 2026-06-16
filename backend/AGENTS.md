## Backend Overview

The backend is a FastAPI service used as the server foundation for the Project Management MVP.

### Current Scope (Part 6)

- Serves the exported frontend static build at `/`
- Exposes JSON API endpoints:
  - `/api/health` for service health
  - `/api/auth/session` for login state checks
  - `/api/auth/login` for credential sign-in
  - `/api/auth/logout` for session clear
  - `/api/hello` protected hello-world payload
  - `/api/board` (GET/PUT) for authenticated board read/update
- Uses `uv` project management via `backend/pyproject.toml`
- Includes unit, integration, and e2e test suites under `backend/tests`
- Uses fallback frontend route handling for non-API paths
- Uses cookie-based MVP auth (`user` / `password`)
- Uses SQLite persistence with migration/bootstrap flow
- Separates models, services, and data access in `backend/app/`

### Planned Evolution

- Add AI routes using OpenRouter