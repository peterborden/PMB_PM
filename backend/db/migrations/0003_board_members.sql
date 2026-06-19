-- Board sharing / collaboration.
--
-- A board is owned by exactly one user (boards.user_id). board_members lists
-- additional users who can read and edit that board. The owner is NOT stored
-- here; ownership stays on boards.user_id. Management of members (add/remove),
-- renaming, and deletion remain owner-only; members may edit board content.

CREATE TABLE IF NOT EXISTS board_members (
  board_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL DEFAULT 'editor',
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  PRIMARY KEY (board_id, user_id),
  FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_board_members_user_id ON board_members(user_id);
