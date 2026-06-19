"use client";

import { FormEvent, useEffect, useState } from "react";
import type { BoardMember } from "@/lib/api";
import { TrashIcon } from "@/components/icons";

type ShareDialogProps = {
  boardName: string;
  members: BoardMember[];
  isOwner: boolean;
  busy?: boolean;
  error?: string | null;
  onAdd: (username: string) => void;
  onRemove: (username: string) => void;
  onClose: () => void;
};

export const ShareDialog = ({
  boardName,
  members,
  isOwner,
  busy = false,
  error = null,
  onAdd,
  onRemove,
  onClose,
}: ShareDialogProps) => {
  const [username, setUsername] = useState("");

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = username.trim();
    if (!trimmed) {
      return;
    }
    onAdd(trimmed);
    setUsername("");
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--navy-dark)]/30 px-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Share board"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]"
      >
        <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">
          Share &ldquo;{boardName}&rdquo;
        </h2>
        <p className="mt-1 text-sm text-[var(--gray-text)]">
          {isOwner
            ? "Invite other users by username. Members can view and edit this board."
            : "You have access to this board. Only the owner can manage members."}
        </p>

        {isOwner ? (
          <form className="mt-4 flex gap-2" onSubmit={handleSubmit}>
            <input
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Username"
              aria-label="Username to add"
              className="flex-1 rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
            />
            <button
              type="submit"
              disabled={busy || !username.trim()}
              className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Add
            </button>
          </form>
        ) : null}

        {error ? (
          <p className="mt-3 text-sm font-medium text-red-600">{error}</p>
        ) : null}

        <ul className="mt-4 space-y-2" aria-label="Board members">
          {members.map((member) => (
            <li
              key={member.username}
              className="flex items-center justify-between rounded-xl border border-[var(--stroke)] px-3 py-2"
            >
              <span className="text-sm font-medium text-[var(--navy-dark)]">
                {member.username}
              </span>
              <span className="flex items-center gap-2">
                <span className="rounded-full bg-[var(--surface)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--gray-text)]">
                  {member.role}
                </span>
                {isOwner && member.role !== "owner" ? (
                  <button
                    type="button"
                    onClick={() => onRemove(member.username)}
                    aria-label={`Remove ${member.username}`}
                    title="Remove member"
                    disabled={busy}
                    className="flex h-7 w-7 items-center justify-center rounded-lg text-[var(--gray-text)] transition hover:bg-red-50 hover:text-red-600 disabled:opacity-50"
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                ) : null}
              </span>
            </li>
          ))}
        </ul>

        <div className="mt-6 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-full border border-[var(--stroke)] px-5 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
