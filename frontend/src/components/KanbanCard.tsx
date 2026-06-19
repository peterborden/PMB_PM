import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import clsx from "clsx";
import type { Card } from "@/lib/kanban";
import { CardMeta } from "@/components/CardMeta";
import { TrashIcon } from "@/components/icons";

type KanbanCardProps = {
  card: Card;
  onDelete: (cardId: string) => void;
};

export const KanbanCard = ({ card, onDelete }: KanbanCardProps) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <article
      ref={setNodeRef}
      style={style}
      className={clsx(
        "group relative rounded-2xl border border-[var(--stroke)] bg-white px-4 py-3 shadow-[0_8px_18px_rgba(3,33,71,0.06)]",
        "cursor-grab transition-all duration-150 hover:-translate-y-0.5 hover:border-[var(--primary-blue)]/40 hover:shadow-[0_14px_28px_rgba(3,33,71,0.12)] active:cursor-grabbing",
        isDragging && "opacity-60 shadow-[0_18px_32px_rgba(3,33,71,0.16)]"
      )}
      {...attributes}
      {...listeners}
      data-testid={`card-${card.id}`}
    >
      <div className="flex items-start justify-between gap-2">
        <h4 className="font-display text-sm font-semibold leading-5 text-[var(--navy-dark)]">
          {card.title}
        </h4>
        <button
          type="button"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => onDelete(card.id)}
          className="-mr-1 -mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-[var(--gray-text)] opacity-0 transition hover:bg-red-50 hover:text-red-600 focus-visible:opacity-100 group-hover:opacity-100"
          aria-label={`Delete ${card.title}`}
          title="Delete card"
        >
          <TrashIcon className="h-4 w-4" />
        </button>
      </div>
      <p className="mt-1.5 text-xs leading-5 text-[var(--gray-text)]">
        {card.details}
      </p>
      <CardMeta card={card} />
    </article>
  );
};
