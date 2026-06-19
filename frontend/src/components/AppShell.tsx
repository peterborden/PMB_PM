"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { BoardSwitcher } from "@/components/BoardSwitcher";
import { ShareDialog } from "@/components/ShareDialog";
import { LogoutIcon, SendIcon, SparkleIcon, UsersIcon } from "@/components/icons";
import type { BoardData } from "@/lib/kanban";
import { appendMessage, trimChatHistory, type ChatMessage } from "@/lib/aiChat";
import {
  addBoardMember,
  ApiError,
  type BoardMember,
  type BoardMeta,
  createBoard,
  deleteBoard,
  getBoard,
  getSession,
  listBoardMembers,
  listBoards,
  login as apiLogin,
  logout as apiLogout,
  register as apiRegister,
  removeBoardMember,
  renameBoard,
  saveBoard,
  sendBoardChat,
} from "@/lib/api";

type AuthState = "loading" | "authenticated" | "unauthenticated";
type AuthMode = "login" | "register";

type CredentialsForm = {
  username: string;
  password: string;
};

const initialForm: CredentialsForm = {
  username: "",
  password: "",
};

const NEW_BOARD_NAME = "Untitled board";

// Text edits (column rename) persist on a trailing debounce so typing does not
// fire a board save per keystroke.
const SAVE_DEBOUNCE_MS = 500;

export const AppShell = () => {
  const [authState, setAuthState] = useState<AuthState>("loading");
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [form, setForm] = useState<CredentialsForm>(initialForm);
  const [username, setUsername] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [boards, setBoards] = useState<BoardMeta[]>([]);
  const [activeBoardId, setActiveBoardId] = useState<number | null>(null);
  const [board, setBoard] = useState<BoardData | null>(null);
  const [boardLoadError, setBoardLoadError] = useState<string | null>(null);
  const [isSavingBoard, setIsSavingBoard] = useState(false);
  const [isBoardBusy, setIsBoardBusy] = useState(false);
  const [boardSyncError, setBoardSyncError] = useState<string | null>(null);

  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isSendingChat, setIsSendingChat] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  const [isShareOpen, setIsShareOpen] = useState(false);
  const [members, setMembers] = useState<BoardMember[]>([]);
  const [membersBusy, setMembersBusy] = useState(false);
  const [membersError, setMembersError] = useState<string | null>(null);
  // Usernames assignable to cards on the active board (owner + members).
  const [assigneeOptions, setAssigneeOptions] = useState<string[]>([]);

  const saveQueueRef = useRef(Promise.resolve());
  // Synchronous source of truth for the active board and its version, used as
  // expectedVersion on saves. Kept in refs (not state) so chained saves never
  // read a stale value between renders.
  const activeBoardIdRef = useRef<number | null>(null);
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

  const activeBoard = boards.find((entry) => entry.id === activeBoardId) ?? null;
  const activeBoardName = activeBoard?.name ?? undefined;
  // role is absent on owned boards from older responses; treat absent as owner.
  const isActiveBoardOwner = activeBoard?.role !== "editor";

  const loadMembers = useCallback(async (boardId: number) => {
    setMembersBusy(true);
    setMembersError(null);
    try {
      const list = await listBoardMembers(boardId);
      setMembers(list);
      setAssigneeOptions(list.map((member) => member.username));
    } catch {
      setMembersError("Unable to load members.");
    } finally {
      setMembersBusy(false);
    }
  }, []);

  // Keep the card-assignee options in sync with the active board's members.
  useEffect(() => {
    if (authState !== "authenticated" || activeBoardId === null) {
      setAssigneeOptions([]);
      return;
    }
    let cancelled = false;
    listBoardMembers(activeBoardId)
      .then((list) => {
        if (!cancelled) {
          setAssigneeOptions(list.map((member) => member.username));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setAssigneeOptions([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [authState, activeBoardId]);

  const handleOpenShare = () => {
    const boardId = activeBoardIdRef.current;
    if (boardId === null) {
      return;
    }
    setMembers([]);
    setMembersError(null);
    setIsShareOpen(true);
    void loadMembers(boardId);
  };

  const handleAddMember = async (username: string) => {
    const boardId = activeBoardIdRef.current;
    if (boardId === null) {
      return;
    }
    setMembersBusy(true);
    setMembersError(null);
    try {
      await addBoardMember(boardId, username);
      const list = await listBoardMembers(boardId);
      setMembers(list);
      setAssigneeOptions(list.map((member) => member.username));
    } catch (error) {
      setMembersError(addMemberErrorMessage(error));
    } finally {
      setMembersBusy(false);
    }
  };

  const handleRemoveMember = async (username: string) => {
    const boardId = activeBoardIdRef.current;
    if (boardId === null) {
      return;
    }
    setMembersBusy(true);
    setMembersError(null);
    try {
      await removeBoardMember(boardId, username);
      const list = await listBoardMembers(boardId);
      setMembers(list);
      setAssigneeOptions(list.map((member) => member.username));
    } catch {
      setMembersError("Unable to remove member.");
    } finally {
      setMembersBusy(false);
    }
  };

  const loadBoardDetail = useCallback(async (boardId: number) => {
    setBoardLoadError(null);
    try {
      const detail = await getBoard(boardId);
      activeBoardIdRef.current = detail.id;
      boardVersionRef.current = detail.version;
      setActiveBoardId(detail.id);
      setBoard(detail.board);
      setBoardSyncError(null);
    } catch {
      setBoardLoadError("Unable to load board. Please try again.");
    }
  }, []);

  const refreshBoards = useCallback(
    async (preferredId?: number) => {
      const list = await listBoards();
      setBoards(list);
      if (list.length === 0) {
        return;
      }
      const target =
        list.find((entry) => entry.id === preferredId) ??
        list.find((entry) => entry.id === activeBoardIdRef.current) ??
        list[0];
      await loadBoardDetail(target.id);
    },
    [loadBoardDetail]
  );

  // Initial session check.
  useEffect(() => {
    let mounted = true;
    const loadSession = async () => {
      try {
        const session = await getSession();
        if (!mounted) {
          return;
        }
        if (session.authenticated) {
          setUsername(session.username);
          setAuthState("authenticated");
        } else {
          setAuthState("unauthenticated");
        }
      } catch {
        if (mounted) {
          setAuthState("unauthenticated");
        }
      }
    };

    void loadSession();
    return () => {
      mounted = false;
    };
  }, []);

  // Load boards once authenticated.
  useEffect(() => {
    if (authState !== "authenticated") {
      return;
    }
    void refreshBoards();
  }, [authState, refreshBoards]);

  const handleAuthSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorMessage(null);

    try {
      const session =
        authMode === "register"
          ? await apiRegister(form.username, form.password)
          : await apiLogin(form.username, form.password);
      setUsername(session.username);
      setForm(initialForm);
      setAuthState("authenticated");
    } catch (error) {
      setErrorMessage(authErrorMessage(error, authMode));
    } finally {
      setIsSubmitting(false);
    }
  };

  const resetBoardState = () => {
    if (renameDebounceRef.current) {
      clearTimeout(renameDebounceRef.current);
      renameDebounceRef.current = null;
    }
    pendingSaveRef.current = null;
    activeBoardIdRef.current = null;
    boardVersionRef.current = null;
    setBoards([]);
    setActiveBoardId(null);
    setBoard(null);
    setBoardLoadError(null);
    setBoardSyncError(null);
    setChatMessages([]);
    setChatInput("");
    setChatError(null);
  };

  const handleLogout = async () => {
    setErrorMessage(null);
    try {
      await apiLogout();
    } catch {
      // Logging out locally is safe even if the request fails.
    } finally {
      resetBoardState();
      setUsername(null);
      setAuthMode("login");
      setAuthState("unauthenticated");
    }
  };

  const enqueueSave = useCallback(
    (nextBoard: BoardData) => {
      saveQueueRef.current = saveQueueRef.current
        .then(async () => {
          const boardId = activeBoardIdRef.current;
          const expectedVersion = boardVersionRef.current;
          if (boardId === null || expectedVersion === null) {
            return;
          }

          setIsSavingBoard(true);
          try {
            const detail = await saveBoard(boardId, nextBoard, expectedVersion);
            // Only adopt the response if the user has not switched boards.
            if (activeBoardIdRef.current === boardId) {
              setBoard(detail.board);
              boardVersionRef.current = detail.version;
            }
          } catch (error) {
            if (error instanceof ApiError && error.status === 409) {
              setBoardSyncError("Board changed elsewhere. Reloaded latest state.");
              if (activeBoardIdRef.current === boardId) {
                await loadBoardDetail(boardId);
              }
              return;
            }
            setBoardSyncError("Unable to save board changes.");
          }
        })
        .finally(() => {
          setIsSavingBoard(false);
        });
    },
    [loadBoardDetail]
  );

  // Persist any debounced edit immediately (e.g. before sending an AI request or
  // switching boards so the latest edit is not lost).
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

  const handleSelectBoard = useCallback(
    async (boardId: number) => {
      if (boardId === activeBoardIdRef.current) {
        return;
      }
      setIsBoardBusy(true);
      try {
        flushPendingSave();
        await saveQueueRef.current;
        setChatMessages([]);
        setChatError(null);
        await loadBoardDetail(boardId);
      } finally {
        setIsBoardBusy(false);
      }
    },
    [flushPendingSave, loadBoardDetail]
  );

  const handleCreateBoard = useCallback(async () => {
    setIsBoardBusy(true);
    try {
      const created = await createBoard(NEW_BOARD_NAME);
      setChatMessages([]);
      setChatError(null);
      await refreshBoards(created.id);
    } catch {
      setBoardSyncError("Unable to create a new board.");
    } finally {
      setIsBoardBusy(false);
    }
  }, [refreshBoards]);

  const handleRenameBoard = useCallback(
    async (boardId: number, name: string) => {
      try {
        const meta = await renameBoard(boardId, name);
        setBoards((prev) =>
          prev.map((entry) => (entry.id === boardId ? { ...entry, name: meta.name } : entry))
        );
      } catch {
        setBoardSyncError("Unable to rename board.");
      }
    },
    []
  );

  const handleDeleteBoard = useCallback(
    async (boardId: number) => {
      setIsBoardBusy(true);
      try {
        await deleteBoard(boardId);
        if (boardId === activeBoardIdRef.current) {
          activeBoardIdRef.current = null;
          setChatMessages([]);
          setChatError(null);
        }
        await refreshBoards();
      } catch (error) {
        if (error instanceof ApiError && error.status === 409) {
          setBoardSyncError("You must keep at least one board.");
        } else {
          setBoardSyncError("Unable to delete board.");
        }
      } finally {
        setIsBoardBusy(false);
      }
    },
    [refreshBoards]
  );

  const handleSendChat = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const message = chatInput.trim();
    const boardId = activeBoardIdRef.current;
    if (!message || isSendingChat || boardId === null) {
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
      const result = await sendBoardChat(boardId, message, history);
      setChatMessages((prev) => appendMessage(prev, "assistant", result.reply));
      if (activeBoardIdRef.current === boardId) {
        setBoard(result.board);
        boardVersionRef.current = result.version;
        setBoardSyncError(null);
      }
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
    const isRegister = authMode === "register";
    return (
      <main className="flex min-h-screen items-center justify-center px-6 py-12">
        <section className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-8 shadow-[var(--shadow)]">
          <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
            Project Management
          </p>
          <h1 className="mt-4 font-display text-3xl font-semibold text-[var(--navy-dark)]">
            {isRegister ? "Create account" : "Sign in"}
          </h1>
          <p className="mt-2 text-sm text-[var(--gray-text)]">
            {isRegister
              ? "Create an account to start building boards."
              : "Sign in to access your boards."}
          </p>
          <form className="mt-6 space-y-4" onSubmit={handleAuthSubmit}>
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
                autoComplete={isRegister ? "new-password" : "current-password"}
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
              {isSubmitting
                ? isRegister
                  ? "Creating..."
                  : "Signing in..."
                : isRegister
                  ? "Create account"
                  : "Sign in"}
            </button>
          </form>
          <button
            type="button"
            onClick={() => {
              setAuthMode(isRegister ? "login" : "register");
              setErrorMessage(null);
            }}
            className="mt-5 text-sm font-semibold text-[var(--primary-blue)] transition hover:underline"
          >
            {isRegister
              ? "Have an account? Sign in"
              : "Need an account? Create one"}
          </button>
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
                void refreshBoards();
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

  const boardSwitcher = (
    <div className="flex flex-wrap items-center gap-2">
      <BoardSwitcher
        boards={boards}
        activeBoardId={activeBoardId}
        onSelect={(id) => void handleSelectBoard(id)}
        onCreate={() => void handleCreateBoard()}
        onRename={(id, name) => void handleRenameBoard(id, name)}
        onDelete={(id) => void handleDeleteBoard(id)}
        busy={isBoardBusy}
      />
      <button
        type="button"
        onClick={handleOpenShare}
        aria-label="Share board"
        title="Share board"
        className="flex items-center gap-1.5 rounded-full border border-[var(--stroke)] px-3 py-1.5 text-sm font-semibold text-[var(--navy-dark)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
      >
        <UsersIcon className="h-4 w-4" />
        Share
      </button>
    </div>
  );

  return (
    <div className="relative pr-[360px]">
      <KanbanBoard
        board={board}
        onBoardChange={persistBoardUpdate}
        isSaving={isSavingBoard || isSendingChat}
        syncError={boardSyncError}
        toolbar={boardSwitcher}
        boardName={activeBoardName}
        assigneeOptions={assigneeOptions}
      />
      <aside className="fixed inset-y-0 right-0 flex w-[360px] flex-col border-l border-[var(--stroke)] bg-white shadow-[-8px_0_18px_rgba(3,33,71,0.06)]">
        <div className="flex items-center justify-between gap-3 border-b border-[var(--stroke)] px-5 py-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--secondary-purple)]/10 text-[var(--secondary-purple)]">
              <SparkleIcon className="h-5 w-5" />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold leading-tight text-[var(--navy-dark)]">
                AI Assistant
              </h2>
              <p className="text-xs font-medium text-[var(--gray-text)]">
                {username ? `Signed in as ${username}` : "Reads and rewrites your board"}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Log out"
            title="Log out"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--stroke)] text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
          >
            <LogoutIcon className="h-4 w-4" />
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4">
          {chatMessages.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-[var(--stroke)] bg-[var(--surface)] p-4 text-sm leading-6 text-[var(--gray-text)]">
              Ask the assistant to review the board, suggest priorities, or update
              columns and cards.
            </div>
          ) : (
            chatMessages.map((entry, index) => (
              <article
                key={`${entry.role}-${index}`}
                className={
                  entry.role === "user"
                    ? "ml-8 rounded-2xl rounded-br-sm bg-[var(--secondary-purple)] px-3.5 py-2.5 text-sm leading-6 text-white"
                    : "mr-8 rounded-2xl rounded-bl-sm border border-[var(--stroke)] bg-[var(--surface)] px-3.5 py-2.5 text-sm leading-6 text-[var(--navy-dark)]"
                }
              >
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.18em] opacity-70">
                  {entry.role === "user" ? "You" : "Assistant"}
                </p>
                <p className="whitespace-pre-wrap">{entry.content}</p>
              </article>
            ))
          )}
          {isSendingChat ? (
            <p className="mr-8 flex items-center gap-1.5 px-1 text-xs font-medium text-[var(--gray-text)]">
              <SparkleIcon className="h-3.5 w-3.5 animate-pulse" />
              Assistant is thinking...
            </p>
          ) : null}
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
            rows={3}
            placeholder="Example: Move urgent cards into Review and summarize blockers."
            className="w-full resize-none rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm leading-6 outline-none transition focus:border-[var(--primary-blue)]"
          />
          {chatError ? (
            <p className="mt-2 text-sm font-medium text-red-600">{chatError}</p>
          ) : null}
          <button
            type="submit"
            disabled={isSendingChat || !chatInput.trim()}
            className="mt-3 flex w-full items-center justify-center gap-2 rounded-full bg-[var(--secondary-purple)] px-4 py-2.5 text-sm font-semibold text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-70"
          >
            <SendIcon className="h-4 w-4" />
            {isSendingChat ? "Sending..." : "Send"}
          </button>
        </form>
      </aside>

      {isShareOpen ? (
        <ShareDialog
          boardName={activeBoardName ?? "board"}
          members={members}
          isOwner={isActiveBoardOwner}
          busy={membersBusy}
          error={membersError}
          onAdd={(name) => void handleAddMember(name)}
          onRemove={(name) => void handleRemoveMember(name)}
          onClose={() => setIsShareOpen(false)}
        />
      ) : null}
    </div>
  );
};

function addMemberErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "No user with that username.";
    }
    if (error.status === 400) {
      return "You cannot share a board with its owner.";
    }
    if (error.status === 0) {
      return "Unable to reach server. Try again.";
    }
  }
  return "Unable to add member.";
}

function authErrorMessage(error: unknown, mode: AuthMode): string {
  if (error instanceof ApiError) {
    if (mode === "register") {
      if (error.status === 409) {
        return "That username is already taken.";
      }
      if (error.status === 422) {
        return "Username must be 3-32 characters and password at least 8.";
      }
    } else if (error.status === 401) {
      return "Invalid username or password.";
    }
    if (error.status === 0) {
      return "Unable to reach server. Try again.";
    }
  }
  return "Something went wrong. Please try again.";
}
