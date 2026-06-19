# Database Design

## Goals

- Support real user accounts (register/login) with many Kanban boards per user
- Keep storage simple and reliable using SQLite
- Store board state as JSON for fast implementation and flexible schema evolution

## Current SQLite Schema

Migration `0001_init.sql` created `users` + a one-board-per-user `boards` table.
Migration `0002_users_sessions_boards.sql` added token-based `sessions` and
rebuilt `boards` to allow many boards per user (added `name` + `position`,
dropped the `UNIQUE(user_id)` constraint).

```sql
CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,   -- PBKDF2-HMAC-SHA256, see backend/app/auth.py
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE sessions (
  token TEXT PRIMARY KEY,         -- opaque token carried in the pm_session cookie
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  expires_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE boards (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,       -- no longer UNIQUE: many boards per user
  name TEXT NOT NULL DEFAULT 'My Board',
  position INTEGER NOT NULL DEFAULT 0,
  board_json TEXT NOT NULL CHECK (json_valid(board_json)),
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_boards_user_id ON boards(user_id);
CREATE INDEX idx_boards_user_position ON boards(user_id, position);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
```

## Authentication

- Passwords are hashed with PBKDF2-HMAC-SHA256 (200k iterations, per-user salt)
  and stored as a self-describing `algo$iterations$salt$hash` string.
- Login/register insert a `sessions` row and set its `token` as the `pm_session`
  cookie. Session lookup checks `expires_at`; logout deletes the row.
- All board access is scoped by `user_id`, so users cannot read or mutate each
  other's boards.

## JSON Board Payload Shape

The `boards.board_json` column stores one JSON document with the same shape used by frontend board state:

```json
{
  "columns": [
    { "id": "col-backlog", "title": "Backlog", "cardIds": ["card-1"] }
  ],
  "cards": {
    "card-1": {
      "id": "card-1",
      "title": "Example card",
      "details": "Example details"
    }
  }
}
```

## Why JSON Blob Storage Here

- Simple CRUD path for MVP: read whole board, update whole board
- Matches frontend data shape directly
- Supports flexible card/column evolution without frequent SQL schema changes
- Easy to validate with Pydantic before write

Tradeoff:
- Not efficient for SQL queries over individual cards (acceptable for MVP scale)
- Writes update the whole document, so optimistic locking is recommended

## Concurrency and Integrity

- Use `boards.version` for optimistic concurrency control:
  - client reads board with version
  - update requires expected version
  - successful update increments version
- Keep `CHECK (json_valid(board_json))` for DB-level guardrail
- Perform app-level schema validation of the parsed board JSON before persisting

## Migration Strategy

Use versioned SQL migrations in `backend/db/migrations/`:

- `0001_init.sql` creates `users` and `boards`
- Track migration state with `PRAGMA user_version`
- On startup:
  1. open/create SQLite DB file
  2. read current `user_version`
  3. apply pending migration files in order
  4. update `user_version`

This keeps migration logic deterministic and simple for local MVP use.

## Bootstrap Strategy (DB Auto-create)

On backend startup:

1. Ensure DB directory exists
2. Open SQLite connection (creates file if missing)
3. Run migrations
4. Ensure MVP user record exists (`username = "user"`)
5. Ensure one board exists for that user; if missing, seed with default board JSON

Notes:
- Stage 4 auth is currently hardcoded. In Stage 6, auth and DB user records should be aligned so the same user identity is used for board lookup.

## Test Plan for Implementation Stages

These tests are implemented in Stage 6 when DB code is added:

- Unit:
  - board JSON schema validation
  - optimistic version increment helper behavior
- Integration:
  - DB auto-create on empty path
  - migration execution and `user_version` updates
  - create/read/update board round-trip by user
- E2E:
  - modify board, restart app, verify persisted board state remains

## Alternatives Considered

- Fully normalized card/column tables now:
  - better queryability, but significantly higher implementation complexity for MVP
- Single `boards` table without `users`:
  - simpler now, but blocks clean multi-user transition

Chosen approach balances MVP speed with future-proofing.
