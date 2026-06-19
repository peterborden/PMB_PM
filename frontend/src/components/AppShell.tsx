"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import type { BoardData } from "@/lib/kanban";
import { appendMessage, trimChatHistory, type ChatMessage } from "@/lib/aiChat";

type AuthState = "loading" | "authenticated" | "unauthenticated";

type LoginForm = {
  username: string;
  password: string;
};

const initialForm: LoginForm = {
  username: "",
  password: "",
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
const withApiBase = (path: string) => `${API_BASE_URL}${path}`;

// Text edits (column rename) persist on a trailing debounce so typing does not
// fire a board save per keystroke.
const SAVE_DEBOUNCE_MS = 500;

type BoardApiPayload = {
  board: BoardData;
  version: number;
};

type AIChatPayload = {
  reply: string;
  boardUpdated: boolean;
  board: BoardData;
  version: number;
};

export const AppShell = () => {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [form, setForm] = useState<LoginForm>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [boardLoadError, setBoardLoadError] = useState<string | null>(null);
  const [isSavingBoard, setIsSavingBoard] = useState(false);
  const [boardSyncError, setBoardSyncError] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const saveQueueRef = useRef(Promise.resolve());
  // Synchronous source of truth for the board version used as expectedVersion on
  // saves. Kept in a ref (not state) so chained saves never read a stale value.
  const boardVersionRef = useRef<number | null>(null);
  const renameDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingSaveRef = useRef<BoardData | null>(null);

  useEffect(() => {
    return () => {
      if (renameDebounceRef.current) {
        clearTimeout(renameDebounceRef.current);
      }
    };
  }, []);

  const loadBoard = useCallback(async () => {
    setBoardLoadError(null);
    try {
      const response = await fetch(withApiBase("/api/board"), {
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error("Board load failed.");
      }
      const payload = (await response.json()) as BoardApiPayload;
      setBoard(payload.board);
      boardVersionRef.current = payload.version;
      setBoardSyncError(null);
    } catch {
      setBoardLoadError("Unable to load board. Please try again.");
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const loadSession = async () => {
      try {
        const response = await fetch(withApiBase("/api/auth/session"), {
          credentials: "same-origin",
        });
        if (!response.ok) {
          throw new Error("Session check failed.");
        }
        const payload = (await response.json()) as { authenticated: boolean };
        if (!mounted) {
          return;
        }
        setAuthState(payload.authenticated ? "authenticated" : "unauthenticated");
      } catch {
        if (!mounted) {
          return;
        }
        setAuthState("unauthenticated");
      }
    };

    void loadSession();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (authState !== "authenticated") {
      return;
    }
    void loadBoard();
  }, [authState, loadBoard]);

  const handleLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const response = await fetch(withApiBase("/api/auth/login"), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: form.username,
          password: form.password,
        }),
      });

      if (!response.ok) {
        setErrorMessage("Invalid username or password.");
        return;
      }

      setAuthState("authenticated");
      setForm(initialForm);
    } catch {
      setErrorMessage("Unable to reach server. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = async () => {
    setErrorMessage(null);
    try {
      await fetch(withApiBase("/api/auth/logout"), {
        method: "POST",
        credentials: "same-origin",
      });
    } finally {
      if (renameDebounceRef.current) {
        clearTimeout(renameDebounceRef.current);
        renameDebounceRef.current = null;
      }
      pendingSaveRef.current = null;
      setBoard(null);
      boardVersionRef.current = null;
      setBoardLoadError(null);
      setBoardSyncError(null);
      setChatMessages([]);
      setChatInput("");
      setChatError(null);
      setAuthState("unauthenticated");
    }
  };

  const enqueueSave = useCallback(
    (nextBoard: BoardData) => {
      saveQueueRef.current = saveQueueRef.current
        .then(async () => {
          const expectedVersion = boardVersionRef.current;
          if (expectedVersion === null) {
            return;
          }

          setIsSavingBoard(true);
          const response = await fetch(withApiBase("/api/board"), {
            method: "PUT",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              board: nextBoard,
              expectedVersion,
            }),
          });

          if (response.status === 409) {
            setBoardSyncError("Board changed elsewhere. Reloaded latest state.");
            await loadBoard();
            return;
          }

          if (!response.ok) {
            throw new Error("Save failed");
          }

          const payload = (await response.json()) as BoardApiPayload;
          setBoard(payload.board);
          // Update the version ref synchronously so the next queued save sends a
          // current expectedVersion instead of waiting for a re-render.
          boardVersionRef.current = payload.version;
        })
        .catch(() => {
          setBoardSyncError("Unable to save board changes.");
        })
        .finally(() => {
          setIsSavingBoard(false);
        });
    },
    [loadBoard]
  );

  // Persist any debounced edit immediately (e.g. before sending an AI request so
  // the assistant sees the latest board).
  const flushPendingSave = useCallback(() => {
    if (renameDebounceRef.current) {
      clearTimeout(renameDebounceRef.current);
      renameDebounceRef.current = null;
    }
    const pending = pendingSaveRef.current;
    pendingSaveRef.current = null;
    if (pending) {
      enqueueSave(pending);
    }
  }, [enqueueSave]);

  const persistBoardUpdate = useCallback(
    (nextBoard: BoardData, options?: { debounce?: boolean }) => {
      setBoard(nextBoard);
      setBoardSyncError(null);

      if (renameDebounceRef.current) {
        clearTimeout(renameDebounceRef.current);
        renameDebounceRef.current = null;
      }

      if (options?.debounce) {
        pendingSaveRef.current = nextBoard;
        renameDebounceRef.current = setTimeout(() => {
          renameDebounceRef.current = null;
          const pending = pendingSaveRef.current;
          pendingSaveRef.current = null;
          if (pending) {
            enqueueSave(pending);
          }
        }, SAVE_DEBOUNCE_MS);
        return;
      }

      pendingSaveRef.current = null;
      enqueueSave(nextBoard);
    },
    [enqueueSave]
  );

  const handleSendChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || isSendingChat) {
      return;
    }

    setChatInput("");
    setChatError(null);
    setChatMessages((prev) => appendMessage(prev, "user", message));
    setIsSendingChat(true);

    try {
      // Keep board write ordering stable: flush any debounced edit, then wait for
      // queued saves before asking AI so it operates on the latest board.
      flushPendingSave();
      await saveQueueRef.current;

      const history = trimChatHistory(chatMessages);
      const response = await fetch(withApiBase("/api/ai/chat"), {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message,
          history,
        }),
      });

      if (!response.ok) {
        throw new Error("chat failed");
      }

      const payload = (await response.json()) as AIChatPayload;
      setChatMessages((prev) => appendMessage(prev, "assistant", payload.reply));
      setBoard(payload.board);
      boardVersionRef.current = payload.version;
      setBoardSyncError(null);
    } catch {
      setChatError("Unable to complete AI chat request.");
      setChatMessages((prev) =>
        appendMessage(
          prev,
          "assistant",
          "I could not process that request right now. Please try again.",
          true
        )
      );
    } finally {
      setIsSendingChat(false);
    }
  };

  if (authState === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <div className="rounded-2xl border border-[var(--stroke)] bg-white px-8 py-6 text-sm font-semibold text-[var(--gray-text)] shadow-[var(--shadow)]">
          Checking session...
        </div>
      </main>
    );
  }

  if (authState === "unauthenticated") {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <section className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            Project Management MVP
          </p>
          <h1 className="mt-4 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            Sign in
          </h1>
          <p className="mt-2 text-sm text-[var(--gray-text)]">
            Sign in to access your board.
          </p>
          <form className="mt-6 space-y-4" onSubmit={handleLogin}>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Username
              <input
                name="username"
                value={form.username}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, username: event.target.value }))
                }
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 outline-none focus:border-[var(--primary-blue)]"
                autoComplete="username"
                required
              />
            </label>
            <label className="block text-sm font-semibold text-[var(--navy-dark)]">
              Password
              <input
                name="password"
                type="password"
                value={form.password}
                onChange={(event) =>
                  setForm((prev) => ({ ...prev, password: event.target.value }))
                }
                className="mt-2 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 outline-none focus:border-[var(--primary-blue)]"
                autoComplete="current-password"
                required
              />
            </label>
            {errorMessage ? (
              <p className="text-sm font-medium text-red-600">{errorMessage}</p>
            ) : null}
            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
            >
              {isSubmitting ? "Signing in..." : "Sign in"}
            </button>
          </form>
        </section>
      </main>
    );
  }

  if (boardLoadError) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <section className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
          <h1 className="font-display text-2xl font-semibold text-[var(--navy-dark)]">
            Unable to load board
          </h1>
          <p className="mt-3 text-sm text-[var(--gray-text)]">{boardLoadError}</p>
          <div className="mt-6 flex gap-3">
            <button
              type="button"
              onClick={() => {
                void loadBoard();
              }}
              className="rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110"
            >
              Retry
            </button>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
            >
              Log out
            </button>
          </div>
        </section>
      </main>
    );
  }

  if (!board) {
    return (
      <main className="flex min-h-screen items-center justify-center px-6">
        <div className="rounded-2xl border border-[var(--stroke)] bg-white px-8 py-6 text-sm font-semibold text-[var(--gray-text)] shadow-[var(--shadow)]">
          Loading board...
        </div>
      </main>
    );
  }

  return (
    <div className="relative pr-[360px]">
      <KanbanBoard
        board={board}
        onBoardChange={persistBoardUpdate}
        isSaving={isSavingBoard || isSendingChat}
        syncError={boardSyncError}
      />
      <aside className="fixed inset-y-0 right-0 flex w-[360px] flex-col border-l border-[var(--stroke)] bg-white shadow-[-8px_0_18px_rgba(3,33,71,0.06)]">
        <div className="border-b border-[var(--stroke)] p-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                AI Assistant
              </p>
              <h2 className="mt-2 font-display text-xl font-semibold text-[var(--navy-dark)]">
                Kanban Chat
              </h2>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-full border border-[var(--stroke)] px-3 py-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
            >
              Log out
            </button>
          </div>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {chatMessages.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--stroke)] bg-[var(--surface)] p-4 text-sm text-[var(--gray-text)]">
              Ask AI to review the board, suggest priorities, or update columns and cards.
            </div>
          ) : (
            chatMessages.map((entry, index) => (
              <article
                key={`${entry.role}-${index}`}
                className={
                  entry.role === "user"
                    ? "ml-6 rounded-2xl bg-[var(--secondary-purple)] p-3 text-sm text-white"
                    : "mr-6 rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] p-3 text-sm text-[var(--navy-dark)]"
                }
              >
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] opacity-80">
                  {entry.role === "user" ? "You" : "Assistant"}
                </p>
                <p className="whitespace-pre-wrap">{entry.content}</p>
              </article>
            ))
          )}
        </div>
        <form
          onSubmit={handleSendChat}
          className="border-t border-[var(--stroke)] p-4"
        >
          <label
            htmlFor="ai-chat-input"
            className="mb-2 block text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)]"
          >
            Ask AI
          </label>
          <textarea
            id="ai-chat-input"
            value={chatInput}
            onChange={(event) => setChatInput(event.target.value)}
            rows={4}
            placeholder="Example: Move urgent cards into Review and summarize blockers."
            className="w-full resize-none rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
          />
          {chatError ? (
            <p className="mt-2 text-sm font-medium text-red-600">{chatError}</p>
          ) : null}
          <button
            type="submit"
            disabled={isSendingChat || !chatInput.trim()}
            className="mt-3 w-full rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
          >
            {isSendingChat ? "Sending..." : "Send"}
          </button>
        </form>
      </aside>
    </div>
  );
};
