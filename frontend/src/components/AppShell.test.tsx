import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/components/AppShell";
import { initialData } from "@/lib/kanban";

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

const boardPayload = () => ({ board: initialData, version: 1 });

describe("AppShell", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("shows login screen when no session exists", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AppShell />);

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  it("authenticates and shows the board", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }))
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse(boardPayload()));
    vi.stubGlobal("fetch", fetchMock);

    render(<AppShell />);

    await screen.findByRole("heading", { name: "Sign in" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "user");
    await user.type(screen.getByLabelText("Password"), "password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("shows an error on invalid credentials", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }))
      .mockResolvedValueOnce(jsonResponse({ detail: "Invalid credentials" }, 401));
    vi.stubGlobal("fetch", fetchMock);

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
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ authenticated: true }))
      .mockResolvedValueOnce(jsonResponse(boardPayload()))
      .mockResolvedValueOnce(jsonResponse({ authenticated: false }));
    vi.stubGlobal("fetch", fetchMock);

    render(<AppShell />);

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Log out" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  it("sends chat and applies AI board update", async () => {
    const updatedBoard = {
      ...initialData,
      columns: initialData.columns.map((column) =>
        column.id === "col-backlog" ? { ...column, title: "AI Backlog" } : column
      ),
    };

    const fetchMock = vi.fn(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/api/auth/session")) {
          return jsonResponse({ authenticated: true });
        }
        if (url.endsWith("/api/board")) {
          return jsonResponse(boardPayload());
        }
        if (url.endsWith("/api/ai/chat")) {
          expect(init?.method).toBe("POST");
          return jsonResponse({
            reply: "Renamed backlog column.",
            boardUpdated: true,
            board: updatedBoard,
            version: 2,
          });
        }
        if (url.endsWith("/api/auth/logout")) {
          return jsonResponse({ authenticated: false });
        }
        return jsonResponse({}, 404);
      }
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<AppShell />);
    expect(await screen.findByRole("heading", { name: "Kanban Studio" })).toBeVisible();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Ask AI"), "Rename backlog");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Renamed backlog column.")).toBeVisible();
    const columnInputs = await screen.findAllByLabelText("Column title");
    expect(columnInputs[0]).toHaveValue("AI Backlog");
  });
});
