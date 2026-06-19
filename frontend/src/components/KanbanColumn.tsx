import clsx from "clsx";
import { useDroppable } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import type { Card, Column } from "@/lib/kanban";
import { KanbanCard } from "@/components/KanbanCard";
import { NewCardForm } from "@/components/NewCardForm";

type KanbanColumnProps = {
  column: Column;
  cards: Card[];
  onRename: (columnId: string, title: string) => void;
  onAddCard: (
    columnId: string,
    title: string,
    details: string,
    labels: string[],
    dueDate: string | null
  ) => void;
  onDeleteCard: (columnId: string, cardId: string) => void;
  onEditCard: (cardId: string) => void;
};

export const KanbanColumn = ({
  column,
  cards,
  onRename,
  onAddCard,
  onDeleteCard,
  onEditCard,
}: KanbanColumnProps) => {
  const { setNodeRef, isOver } = useDroppable({ id: column.id });

  return (
    <section
      ref={setNodeRef}
      className={clsx(
        "flex min-h-[520px] flex-col rounded-3xl border border-[var(--stroke)] bg-[var(--surface-strong)] p-3 shadow-[var(--shadow)] transition",
        isOver && "ring-2 ring-[var(--accent-yellow)]"
      )}
      data-testid={`column-${column.id}`}
    >
      <div className="flex items-center gap-2 px-1">
        <span className="h-5 w-1.5 shrink-0 rounded-full bg-[var(--accent-yellow)]" />
        <input
          value={column.title}
          onChange={(event) => onRename(column.id, event.target.value)}
          className="min-w-0 flex-1 bg-transparent font-display text-base font-semibold text-[var(--navy-dark)] outline-none focus:text-[var(--primary-blue)]"
          aria-label="Column title"
        />
        <span className="flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-[var(--surface)] px-2 text-xs font-semibold text-[var(--gray-text)]">
          {cards.length}
        </span>
      </div>
      <div className="mt-3 flex flex-1 flex-col gap-2.5">
        <SortableContext items={column.cardIds} strategy={verticalListSortingStrategy}>
          {cards.map((card) => (
            <KanbanCard
              key={card.id}
              card={card}
              onDelete={(cardId) => onDeleteCard(column.id, cardId)}
              onEdit={onEditCard}
            />
          ))}
        </SortableContext>
        {cards.length === 0 && (
          <div className="flex flex-1 items-center justify-center rounded-2xl border border-dashed border-[var(--stroke)] px-3 py-8 text-center text-xs font-medium text-[var(--gray-text)]">
            Drop a card here
          </div>
        )}
      </div>
      <NewCardForm
        onAdd={(title, details, labels, dueDate) =>
          onAddCard(column.id, title, details, labels, dueDate)
        }
      />
    </section>
  );
};
