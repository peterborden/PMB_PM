# Frontend Code Guide

## Purpose

This frontend is a Next.js Kanban UI with a simple sign-in gate, backend-backed persistence, and an AI sidebar chat. Auth, board state, and AI chat are managed through backend API endpoints.

## Stack

- Next.js App Router (`src/app`)
- React 19 + TypeScript
- Tailwind CSS v4
- `@dnd-kit` for drag-and-drop sorting
- Vitest + Testing Library for unit/integration tests
- Playwright for e2e tests

## Current App Structure

- `src/app/page.tsx`
  - Home route that renders `AppShell`
- `src/components/AppShell.tsx`
  - Auth gate for login/session/logout flows
  - Loads board data from `/api/board` after authentication
  - Persists board edits to `/api/board` with version-aware saves
  - Hosts right-side AI chat panel connected to `/api/ai/chat`
  - Applies AI-returned board updates and refreshes versioned state
  - Renders login form before board access
  - Renders logout action while authenticated
- `src/components/KanbanBoard.tsx`
  - Board interaction UI (controlled by parent state)
  - Handles drag start/end and card moves
  - Handles column rename, card add, and card delete
- `src/components/KanbanColumn.tsx`
  - Renders one column
  - Column title inline editing
  - Drop zone and sortable card list
  - New card form for the column
- `src/components/KanbanCard.tsx`
  - Sortable card with title/details and delete button
- `src/components/KanbanCardPreview.tsx`
  - Drag overlay preview card
- `src/components/NewCardForm.tsx`
  - Expandable form for adding cards
- `src/lib/kanban.ts`
  - Board/card/column types
  - Demo `initialData`
  - `moveCard` logic for within-column and cross-column moves
  - `createId` helper for client-side IDs
- `src/lib/aiChat.ts`
  - Chat helper functions for appending and trimming conversation history
- `src/app/globals.css`
  - Theme tokens matching root project color scheme

## Data Model in Frontend

- `BoardData` is:
  - `columns: Column[]` where each column owns ordered `cardIds`
  - `cards: Record<string, Card>` normalized card map
- Board state is loaded from backend API and persisted after edits.

## Behavior Implemented Today

- Login gate appears at `/` before board access
- Dummy sign-in accepted with `user` / `password`
- Session check runs on page load to preserve refresh state
- Logout returns the user to the login screen
- Kanban board renders only after authentication
- Board data loads from backend and persists edits via API
- Save and sync errors are surfaced in simple inline status messaging
- Sidebar chat supports conversational requests with loading/error handling
- AI replies appear in thread and AI-driven board updates apply automatically
- Five fixed initial columns are shown
- Column names can be edited inline
- Cards can be:
  - Reordered within a column
  - Moved across columns
  - Added from a per-column form
  - Removed from a column
- Drag overlay preview is shown during drag operations

## Tests Present

- Unit/integration:
  - `src/lib/aiChat.test.ts`: chat helper behavior
  - `src/lib/kanban.test.ts`: `moveCard` behavior
  - `src/components/KanbanBoard.test.tsx`: render, rename, add/remove card
  - `src/components/AppShell.test.tsx`: auth gate/session/login/logout and AI chat updates
- E2E:
  - `tests/kanban.spec.ts`: login success/failure, refresh persistence, logout, board interactions, AI update flow

## Current Limitations

- AI responses are text-only in sidebar (no markdown rendering/tool outputs yet)

## Notes for Next Phases

- Keep this file updated as frontend responsibilities shift from local state to backend-backed data.
- Preserve current user-facing interactions while migrating data flow to backend APIs.
