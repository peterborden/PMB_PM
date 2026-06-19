"use client";

import { FormEvent, useEffect, useState } from "react";
import type { Card } from "@/lib/kanban";
import { TrashIcon } from "@/components/icons";

export type CardEdits = {
  title: string;
  details: string;
  labels: string[];
  dueDate: string | null;
  assignee: string | null;
};

type CardEditorProps = {
  card: Card;
  onSave: (edits: CardEdits) => void;
  onDelete: () => void;
  onClose: () => void;
  // Usernames that can be assigned (board owner + members).
  assigneeOptions?: string[];
};

const parseLabels = (raw: string): string[] => {
  const seen = new Set<string>();
  return raw
    .split(",")
    .map((label) => label.trim())
    .filter((label) => {
      if (!label || seen.has(label)) {
        return false;
      }
      seen.add(label);
      return true;
    });
};

export const CardEditor = ({
  card,
  onSave,
  onDelete,
  onClose,
  assigneeOptions = [],
}: CardEditorProps) => {
  const [title, setTitle] = useState(card.title);
  const [details, setDetails] = useState(card.details);
  const [labels, setLabels] = useState((card.labels ?? []).join(", "));
  const [dueDate, setDueDate] = useState(card.dueDate ?? "");
  const [assignee, setAssignee] = useState(card.assignee ?? "");

  // Always include the current assignee so an out-of-band value stays selectable.
  const options = Array.from(
    new Set([...assigneeOptions, ...(card.assignee ? [card.assignee] : [])])
  );

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
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      return;
    }
    onSave({
      title: trimmedTitle,
      details: details.trim(),
      labels: parseLabels(labels),
      dueDate: dueDate ? dueDate : null,
      assignee: assignee ? assignee : null,
    });
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--navy-dark)]/30 px-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Edit card"
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-md rounded-3xl border border-[var(--stroke)] bg-white p-6 shadow-[var(--shadow)]"
      >
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl font-semibold text-[var(--navy-dark)]">
            Edit card
          </h2>
          <button
            type="button"
            onClick={onDelete}
            aria-label="Delete card"
            title="Delete card"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-[var(--stroke)] text-[var(--gray-text)] transition hover:border-red-400 hover:text-red-500"
          >
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
        <form className="mt-4 space-y-3" onSubmit={handleSubmit}>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
              required
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Details
            <textarea
              value={details}
              onChange={(event) => setDetails(event.target.value)}
              rows={3}
              className="mt-1.5 w-full resize-none rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Labels
            <input
              value={labels}
              onChange={(event) => setLabels(event.target.value)}
              placeholder="Comma separated"
              className="mt-1.5 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Due date
            <input
              type="date"
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-[var(--stroke)] px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
            />
          </label>
          <label className="block text-sm font-semibold text-[var(--navy-dark)]">
            Assignee
            <select
              value={assignee}
              onChange={(event) => setAssignee(event.target.value)}
              className="mt-1.5 w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--primary-blue)]"
            >
              <option value="">Unassigned</option>
              {options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-center justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="rounded-full bg-[var(--secondary-purple)] px-5 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
