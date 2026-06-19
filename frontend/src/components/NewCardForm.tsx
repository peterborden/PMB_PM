import { useState, type FormEvent } from "react";
import { PlusIcon } from "@/components/icons";

const initialFormState = { title: "", details: "", labels: "", dueDate: "" };

type NewCardFormProps = {
  onAdd: (
    title: string,
    details: string,
    labels: string[],
    dueDate: string | null
  ) => void;
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

export const NewCardForm = ({ onAdd }: NewCardFormProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [formState, setFormState] = useState(initialFormState);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.title.trim()) {
      return;
    }
    onAdd(
      formState.title.trim(),
      formState.details.trim(),
      parseLabels(formState.labels),
      formState.dueDate ? formState.dueDate : null
    );
    setFormState(initialFormState);
    setIsOpen(false);
  };

  return (
    <div className="mt-2.5">
      {isOpen ? (
        <form onSubmit={handleSubmit} className="space-y-2.5">
          <input
            value={formState.title}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, title: event.target.value }))
            }
            placeholder="Card title"
            className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm font-medium text-[var(--navy-dark)] outline-none transition focus:border-[var(--primary-blue)]"
            required
          />
          <textarea
            value={formState.details}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, details: event.target.value }))
            }
            placeholder="Details"
            rows={3}
            className="w-full resize-none rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
          />
          <input
            value={formState.labels}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, labels: event.target.value }))
            }
            placeholder="Labels (comma separated)"
            aria-label="Labels"
            className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
          />
          <input
            type="date"
            value={formState.dueDate}
            onChange={(event) =>
              setFormState((prev) => ({ ...prev, dueDate: event.target.value }))
            }
            aria-label="Due date"
            className="w-full rounded-xl border border-[var(--stroke)] bg-white px-3 py-2 text-sm text-[var(--gray-text)] outline-none transition focus:border-[var(--primary-blue)]"
          />
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="rounded-full bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white transition hover:brightness-110"
            >
              Add card
            </button>
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                setFormState(initialFormState);
              }}
              className="rounded-full border border-[var(--stroke)] px-3 py-2 text-xs font-semibold uppercase tracking-wide text-[var(--gray-text)] transition hover:text-[var(--navy-dark)]"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-dashed border-[var(--stroke)] px-3 py-2 text-xs font-semibold text-[var(--gray-text)] transition hover:border-[var(--primary-blue)] hover:text-[var(--primary-blue)]"
        >
          <PlusIcon className="h-4 w-4" />
          Add a card
        </button>
      )}
    </div>
  );
};
