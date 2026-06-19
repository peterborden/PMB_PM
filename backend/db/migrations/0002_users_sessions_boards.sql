-- Real user management + multiple boards per user.
--
-- 1. Sessions: token-based auth replacing the static cookie value. Each login
--    mints a row here; the cookie carries the opaque token.
-- 2. Boards: drop the one-board-per-user UNIQUE(user_id) constraint and add a
--    human name + ordering position so a user can own many boards. SQLite cannot
--    drop a column constraint in place, so the table is rebuilt and copied.

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  expires_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at);

CREATE TABLE boards_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  name TEXT NOT NULL DEFAULT 'My Board',
  position INTEGER NOT NULL DEFAULT 0,
  board_json TEXT NOT NULL CHECK (json_valid(board_json)),
  version INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

INSERT INTO boards_new (id, user_id, name, position, board_json, version, created_at, updated_at)
  SELECT id, user_id, 'My Board', 0, board_json, version, created_at, updated_at FROM boards;

DROP TABLE boards;
ALTER TABLE boards_new RENAME TO boards;

CREATE INDEX IF NOT EXISTS idx_boards_user_id ON boards(user_id);
CREATE INDEX IF NOT EXISTS idx_boards_user_position ON boards(user_id, position);
