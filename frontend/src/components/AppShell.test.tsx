import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { initialData, type BoardData } from "@/lib/kanban";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const emptyBoard: BoardData = {
  columns: [{ id: "col-todo", title: "To Do", cardIds: [] }],
  cards: {},
};

type BoardRecord = {
  id: number;
  name: string;
  version: number;
  board: BoardData;
};

type AIResponder = (
  boardId: number,
  message: string
) => { reply: string; boardUpdated: boolean; board: BoardData; version: number };

type ServerOptions = {
  authenticated?: boolean;
  username?: string | null;
  boards?: BoardRecord[];
  ai?: AIResponder;
};

const meta = (record: BoardRecord) => ({
  id: record.id,
  name: record.name,
  version: record.version,
  createdAt: "2026-06-19T00:00:00.000Z",
  updatedAt: "2026-06-19T00:00:00.000Z",
});

const detail = (record: BoardRecord) => ({
  id: record.id,
  name: record.name,
  version: record.version,
  board: record.board,
});

// A small in-memory backend so AppShell exercises the real API client and
// multi-board flows (create/switch/rename/delete) end to end.
const createServer = (options: ServerOptions = {}) => {
  const state = {
    authenticated: options.authenticated ?? false,
    username: options.username ?? (options.authenticated ? "user" : null),
    boards:
      options.boards ??
      [{ id: 1, name: "My Board", version: 1, board: initialData }],
    nextId: 100,
  };

  const find = (id: number) => state.boards.find((b) => b.id === id);

  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    const method = init?.method ?? "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;

    if (path.endsWith("/api/auth/session")) {
      return jsonResponse({
        authenticated: state.authenticated,
        username: state.authenticated ? state.username : null,
      });
    }
    if (path.endsWith("/api/auth/login") || path.endsWith("/api/auth/register")) {
      state.authenticated = true;
      state.username = body?.username ?? "user";
      return jsonResponse({ authenticated: true, username: state.username });
    }
    if (path.endsWith("/api/auth/logout")) {
      state.authenticated = false;
      return jsonResponse({ authenticated: false, username: null });
    }

    if (path.endsWith("/api/boards") && method === "GET") {
      return jsonResponse({ boards: state.boards.map(meta) });
    }
    if (path.endsWith("/api/boards") && method === "POST") {
      const record = {
        id: state.nextId++,
        name: body.name,
        version: 1,
        board: emptyBoard,
      };
      state.boards.push(record);
      return jsonResponse(meta(record), 201);
    }

    const aiMatch = path.match(/\/api\/boards\/(\d+)\/ai\/chat$/);
    if (aiMatch) {
      const id = Number(aiMatch[1]);
      const responder =
        options.ai ??
        ((boardId, message) => ({
          reply: `Echo: ${message}`,
          boardUpdated: false,
          board: find(boardId)!.board,
          version: find(boardId)!.version,
        }));
      const result = responder(id, body.message);
      const record = find(id)!;
      record.board = result.board;
      record.version = result.version;
      return jsonResponse(result);
    }

    const boardMatch = path.match(/\/api\/boards\/(\d+)$/);
    if (boardMatch) {
      const id = Number(boardMatch[1]);
      const record = find(id);
      if (!record) {
        return jsonResponse({ detail: "Board not found" }, 404);
      }
      if (method === "GET") {
        return jsonResponse(detail(record));
      }
      if (method === "PUT") {
        record.board = body.board;
        record.version += 1;
        return jsonResponse(detail(record));
      }
      if (method === "PATCH") {
        record.name = body.name;
        return jsonResponse(meta(record));
      }
      if (method === "DELETE") {
        if (state.boards.length <= 1) {
          return jsonResponse({ detail: "Cannot delete the only remaining board" }, 409);
        }
        state.boards = state.boards.filter((b) => b.id !== id);
        return new Response(null, { status: 204 });
      }
    }

    return jsonResponse({ detail: "Not found" }, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
  return { state, fetchMock };
};

describe("AppShell", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows login screen when no session exists", async () => {
    createServer({ authenticated: false });
    render(<AppShell />);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  it("authenticates and shows the board", async () => {
    createServer({ authenticated: false });
    render(<AppShell />);
    await screen.findByRole("heading", { name: "Sign in" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("registers a new account", async () => {
    createServer({ authenticated: false });
    render(<AppShell />);
    await screen.findByRole("heading", { name: "Sign in" });

    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Need an account? Create one" }));
    expect(await screen.findByRole("heading", { name: "Create account" })).toBeVisible();

    await user.type(screen.getByLabelText("Username"), "newbie");
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();
    expect(screen.getByText("Signed in as newbie")).toBeVisible();
  });

  it("shows an error on invalid credentials", async () => {
    const { fetchMock } = createServer({ authenticated: false });
    fetchMock.mockImplementationOnce(async () =>
      jsonResponse({ authenticated: false, username: null })
    );
    // Make the login attempt fail with 401.
    fetchMock.mockImplementationOnce(async (input: RequestInfo | URL) => {
      if (String(input).endsWith("/api/auth/login")) {
        return jsonResponse({ detail: "Invalid credentials" }, 401);
      }
      return jsonResponse({}, 404);
    });

    render(<AppShell />);
    await screen.findByRole("heading", { name: "Sign in" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByText("Invalid username or password.")
    ).toBeInTheDocument();
  });

  it("logs out and returns to login screen", async () => {
    createServer({ authenticated: true });
    render(<AppShell />);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  it("sends chat and applies AI board update", async () => {
    createServer({
      authenticated: true,
      ai: (boardId, message) => ({
        reply: "Renamed backlog column.",
        boardUpdated: true,
        version: 2,
        board: {
          ...initialData,
          columns: initialData.columns.map((column) =>
            column.id === "col-backlog"
              ? { ...column, title: `AI:${message}` }
              : column
          ),
        },
      }),
    });

    render(<AppShell />);
    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Ask AI"), "Rename backlog");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Renamed backlog column.")).toBeVisible();
    const columnInputs = await screen.findAllByLabelText("Column title");
    expect(columnInputs[0]).toHaveValue("AI:Rename backlog");
  });

  it("creates a new board and switches to it", async () => {
    createServer({ authenticated: true });
    render(<AppShell />);
    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();

    const switcher = screen.getByRole("navigation", { name: "Boards" });
    expect(within(switcher).getByRole("button", { name: "My Board" })).toBeVisible();

    const user = userEvent.setup();
    await user.click(within(switcher).getByRole("button", { name: "New board" }));

    // The newly created board appears and becomes active (empty board => no cards).
    expect(
      await within(switcher).findByRole("button", { name: "Untitled board" })
    ).toBeVisible();
    expect(screen.queryByText("Align roadmap themes")).not.toBeInTheDocument();
  });

  it("switches back to an existing board", async () => {
    createServer({
      authenticated: true,
      boards: [
        { id: 1, name: "My Board", version: 1, board: initialData },
        { id: 2, name: "Roadmap", version: 1, board: emptyBoard },
      ],
    });
    render(<AppShell />);
    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();

    const switcher = screen.getByRole("navigation", { name: "Boards" });
    const user = userEvent.setup();
    await user.click(within(switcher).getByRole("button", { name: "Roadmap" }));

    // Roadmap is the empty board (single "To Do" column), so its column appears
    // and the seeded "My Board" card disappears.
    expect(await screen.findByDisplayValue("To Do")).toBeVisible();
    expect(screen.queryByText("Align roadmap themes")).not.toBeInTheDocument();
  });
});
