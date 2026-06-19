"use client";

import { FormEvent, useState } from "react";
import clsx from "clsx";
import { EditIcon, PlusIcon, TrashIcon } from "@/components/icons";
import type { BoardMeta } from "@/lib/api";

type BoardSwitcherProps = {
  boards: BoardMeta[];
  activeBoardId: number | null;
  onSelect: (boardId: number) => void;
  onCreate: () => void;
  onRename: (boardId: number, name: string) => void;
  onDelete: (boardId: number) => void;
  busy?: boolean;
};

export const BoardSwitcher = ({
  boards,
  activeBoardId,
  onSelect,
  onCreate,
  onRename,
  onDelete,
  busy = false,
}: BoardSwitcherProps) => {
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");

  const activeBoard = boards.find((board) => board.id === activeBoardId) ?? null;
  const canDelete = boards.length > 1;

  const startEditing = () => {
    if (!activeBoard) {
      return;
    }
    setDraftName(activeBoard.name);
    setEditingId(activeBoard.id);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setDraftName("");
  };

  const submitRename = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (editingId === null) {
      return;
    }
    const trimmed = draftName.trim();
    const current = boards.find((board) => board.id === editingId);
    if (trimmed && current && trimmed !== current.name) {
      onRename(editingId, trimmed);
    }
    cancelEditing();
  };

  return (
    <nav
      aria-label="Boards"
      className="flex flex-wrap items-center gap-2"
    >
      {boards.map((board) => {
        const isActive = board.id === activeBoardId;
        if (isActive && editingId === board.id) {
          return (
            <form key={board.id} onSubmit={submitRename} className="flex items-center gap-1">
              <input
                aria-label="Board name"
                autoFocus
                value={draftName}
                onChange={(event) => setDraftName(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Escape") {
                    cancelEditing();
                  }
                }}
                onBlur={cancelEditing}
                className="w-40 rounded-lg border border-[var(--primary-blue)] px-2.5 py-1.5 text-sm outline-none"
              />
            </form>
          );
        }

        return (
          <button
            key={board.id}
            type="button"
            onClick={() => onSelect(board.id)}
            aria-current={isActive ? "true" : undefined}
            disabled={busy}
            className={clsx(
              "rounded-full px-3.5 py-1.5 text-sm font-semibold transition disabled:opacity-60",
              isActive
                ? "bg-[var(--navy-dark)] text-white"
                : "border border-[var(--stroke)] text-[var(--navy-dark)] hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
            )}
          >
            {board.name}
          </button>
        );
      })}

      {activeBoard && editingId === null ? (
        <button
          type="button"
          onClick={startEditing}
          aria-label="Rename board"
          title="Rename board"
          disabled={busy}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--stroke)] text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)] disabled:opacity-60"
        >
          <EditIcon className="h-4 w-4" />
        </button>
      ) : null}

      {activeBoard ? (
        <button
          type="button"
          onClick={() => onDelete(activeBoard.id)}
          aria-label="Delete board"
          title={canDelete ? "Delete board" : "A user must keep at least one board"}
          disabled={busy || !canDelete}
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-[var(--stroke)] text-[var(--gray-text)] transition hover:border-red-400 hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      ) : null}

      <button
        type="button"
        onClick={onCreate}
        aria-label="New board"
        disabled={busy}
        className="flex items-center gap-1.5 rounded-full border border-dashed border-[var(--stroke)] px-3 py-1.5 text-sm font-semibold text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)] disabled:opacity-60"
      >
        <PlusIcon className="h-4 w-4" />
        New board
      </button>
    </nav>
  );
};
