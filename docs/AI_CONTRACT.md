# AI Chat Contract (Part 9)

## Purpose

Define the backend contract for AI chat so responses are structured, validated, and safe to apply to board state.

## Backend Route

- `POST /api/boards/{board_id}/ai/chat` (authenticated) — operates on the given board
- `POST /api/ai/chat` (authenticated) — legacy alias that targets the user's default board

The backend always includes:

- current board JSON
- current user message
- prior conversation history (`user`/`assistant` turns)

## Request Schema

```json
{
  "message": "string",
  "history": [
    { "role": "user", "content": "string" },
    { "role": "assistant", "content": "string" }
  ]
}
```

Notes:

- `history` is optional and defaults to `[]`
- allowed roles are `user` and `assistant`

## Structured AI Output Schema

The model is instructed to return JSON with this shape:

```json
{
  "reply": "string",
  "updatedBoard": {
    "columns": [
      { "id": "string", "title": "string", "cardIds": ["string"] }
    ],
    "cards": {
      "card-id": {
        "id": "string",
        "title": "string",
        "details": "string",
        "labels": ["string"],
        "dueDate": "YYYY-MM-DD or null",
        "assignee": "username or null"
      }
    }
  }
}
```

`updatedBoard` can also be `null` when no board change is needed.

Backend validation:

- parse JSON from model output
- validate against Pydantic schema
- validate internal board consistency (`cardIds` reference existing cards)

## API Response Schema

```json
{
  "reply": "string",
  "boardUpdated": true,
  "board": {
    "columns": [],
    "cards": {}
  },
  "version": 2
}
```

Behavior:

- if `updatedBoard` is `null`, backend returns current board/version with `boardUpdated: false`
- if `updatedBoard` is present and valid, backend persists it and returns incremented version with `boardUpdated: true`

## Error Handling

- `401`: not authenticated
- `502`: upstream AI request/response error
- `503`: `OPENROUTER_API_KEY` not configured
- `409`: optimistic concurrency conflict during board write

## Example (No Board Update)

Request:

```json
{
  "message": "What should I focus on first?",
  "history": []
}
```

Response:

```json
{
  "reply": "Start with the highest-risk in-progress card.",
  "boardUpdated": false,
  "board": { "columns": [], "cards": {} },
  "version": 4
}
```

## Example (Board Update)

Request:

```json
{
  "message": "Move card card-4 to Review",
  "history": [
    { "role": "user", "content": "Can you help reorganize my board?" },
    { "role": "assistant", "content": "Yes, tell me what to change." }
  ]
}
```

Response:

```json
{
  "reply": "Moved card-4 to Review.",
  "boardUpdated": true,
  "board": { "columns": [], "cards": {} },
  "version": 5
}
```
