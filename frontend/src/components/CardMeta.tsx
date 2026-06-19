import clsx from "clsx";
import type { Card } from "@/lib/kanban";
import { formatDueDate, isOverdue } from "@/lib/kanban";

type CardMetaProps = {
  card: Card;
};

// Renders a card's labels and due date. Returns null when the card has neither,
// so plain cards keep their original compact look.
export const CardMeta = ({ card }: CardMetaProps) => {
  const labels = card.labels ?? [];
  const hasDueDate = Boolean(card.dueDate);

  if (labels.length === 0 && !hasDueDate) {
    return null;
  }

  const overdue = isOverdue(card.dueDate);

  return (
    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
      {labels.map((label) => (
        <span
          key={label}
          className="rounded-full bg-[var(--primary-blue)]/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-[var(--primary-blue)]"
        >
          {label}
        </span>
      ))}
      {card.dueDate ? (
        <span
          data-testid="card-due-date"
          className={clsx(
            "rounded-full px-2 py-0.5 text-[10px] font-semibold",
            overdue
              ? "bg-red-50 text-red-600"
              : "bg-[var(--accent-yellow)]/15 text-[var(--accent-yellow)]"
          )}
          title={overdue ? "Overdue" : "Due date"}
        >
          {overdue ? "Overdue " : "Due "}
          {formatDueDate(card.dueDate)}
        </span>
      ) : null}
    </div>
  );
};
