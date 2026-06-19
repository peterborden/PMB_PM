import type { BoardData } from "@/lib/kanban";
import type { ChatMessage } from "@/lib/aiChat";

// Single source of truth for talking to the backend. Fetches stay relative
// (NEXT_PUBLIC_API_BASE_URL is empty in dev/prod) so the pm_session cookie flows
// same-origin; see CLAUDE.md "Don'ts".
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const withApiBase = (path: string) => `${API_BASE_URL}${path}`;

export type SessionInfo = {
  authenticated: boolean;
  username: string | null;
};

export type BoardMeta = {
  id: number;
  name: string;
  version: number;
  createdAt: string;
  updatedAt: string;
};

export type BoardDetail = {
  id: number;
  name: string;
  board: BoardData;
  version: number;
};

export type AIChatResult = {
  reply: string;
  boardUpdated: boolean;
  board: BoardData;
  version: number;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  // Treat a 204 (or otherwise empty) response as success without parsing JSON.
  expectNoContent?: boolean;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, expectNoContent = false } = options;

  let response: Response;
  try {
    response = await fetch(withApiBase(path), {
      method,
      credentials: "same-origin",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Unable to reach the server.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorDetail(response));
  }

  if (expectNoContent || response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // fall through to a generic message
  }
  return `Request failed (${response.status}).`;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export const getSession = () => request<SessionInfo>("/api/auth/session");

export const login = (username: string, password: string) =>
  request<SessionInfo>("/api/auth/login", {
    method: "POST",
    body: { username, password },
  });

export const register = (username: string, password: string) =>
  request<SessionInfo>("/api/auth/register", {
    method: "POST",
    body: { username, password },
  });

export const logout = () =>
  request<SessionInfo>("/api/auth/logout", { method: "POST" });

// ---------------------------------------------------------------------------
// Boards
// ---------------------------------------------------------------------------

export const listBoards = async (): Promise<BoardMeta[]> => {
  const payload = await request<{ boards: BoardMeta[] }>("/api/boards");
  return payload.boards;
};

export const createBoard = (name: string) =>
  request<BoardMeta>("/api/boards", { method: "POST", body: { name } });

export const getBoard = (boardId: number) =>
  request<BoardDetail>(`/api/boards/${boardId}`);

export const saveBoard = (
  boardId: number,
  board: BoardData,
  expectedVersion: number
) =>
  request<BoardDetail>(`/api/boards/${boardId}`, {
    method: "PUT",
    body: { board, expectedVersion },
  });

export const renameBoard = (boardId: number, name: string) =>
  request<BoardMeta>(`/api/boards/${boardId}`, {
    method: "PATCH",
    body: { name },
  });

export const deleteBoard = (boardId: number) =>
  request<void>(`/api/boards/${boardId}`, {
    method: "DELETE",
    expectNoContent: true,
  });

export const sendBoardChat = (
  boardId: number,
  message: string,
  history: ChatMessage[]
) =>
  request<AIChatResult>(`/api/boards/${boardId}/ai/chat`, {
    method: "POST",
    body: { message, history },
  });
