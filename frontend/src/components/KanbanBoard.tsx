"use client";

import { useMemo, useState } from "react";
import {
  type CollisionDetection,
  DndContext,
  DragOverlay,
  PointerSensor,
  pointerWithin,
  rectIntersection,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import clsx from "clsx";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { CheckIcon, SpinnerIcon } from "@/components/icons";
import { createId, moveCard, type BoardData } from "@/lib/kanban";

type KanbanBoardProps = {
  board: BoardData;
  onBoardChange: (
    nextBoard: BoardData,
    options?: { debounce?: boolean }
  ) => void;
  isSaving?: boolean;
  syncError?: string | null;
};

export const KanbanBoard = ({
  board,
  onBoardChange,
  isSaving = false,
  syncError = null,
}: KanbanBoardProps) => {
  const collisionDetection: CollisionDetection = (args) => {
    const pointerIntersections = pointerWithin(args);
    if (pointerIntersections.length > 0) {
      return pointerIntersections;
    }

    const rectIntersections = rectIntersection(args);
    if (rectIntersections.length > 0) {
      return rectIntersections;
    }

    return closestCorners(args);
  };

  const [activeCardId, setActiveCardId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 6 },
    })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);
  const totalCards = useMemo(() => Object.keys(board.cards).length, [board.cards]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);

    if (!over || active.id === over.id) {
      return;
    }

    onBoardChange({
      ...board,
      columns: moveCard(board.columns, active.id as string, over.id as string),
    });
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    onBoardChange(
      {
        ...board,
        columns: board.columns.map((column) =>
          column.id === columnId ? { ...column, title } : column
        ),
      },
      { debounce: true }
    );
  };

  const handleAddCard = (columnId: string, title: string, details: string) => {
    const id = createId("card");
    onBoardChange({
      ...board,
      cards: {
        ...board.cards,
        [id]: { id, title, details: details || "No details yet." },
      },
      columns: board.columns.map((column) =>
        column.id === columnId
          ? { ...column, cardIds: [...column.cardIds, id] }
          : column
      ),
    });
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    onBoardChange({
      ...board,
      cards: Object.fromEntries(
        Object.entries(board.cards).filter(([id]) => id !== cardId)
      ),
      columns: board.columns.map((column) => {
        if (column.id !== columnId) {
          return column;
        }
        return {
          ...column,
          cardIds: column.cardIds.filter((id) => id !== cardId),
        };
      }),
    });
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen w-full max-w-[1700px] flex-col gap-6 px-6 pb-12 pt-8">
        <header className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--stroke)] bg-white/80 px-6 py-4 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex items-center gap-4">
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[var(--navy-dark)] font-display text-lg font-semibold text-white">
              K
            </span>
            <div>
              <h1 className="font-display text-2xl font-semibold leading-tight text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="text-xs font-medium text-[var(--gray-text)]">
                {totalCards} cards across {board.columns.length} columns
              </p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {syncError ? (
              <p className="text-sm font-medium text-red-600">{syncError}</p>
            ) : null}
            <span
              className={clsx(
                "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold",
                isSaving
                  ? "bg-[var(--accent-yellow)]/15 text-[var(--accent-yellow)]"
                  : "bg-emerald-50 text-emerald-600"
              )}
            >
              {isSaving ? (
                <SpinnerIcon className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <CheckIcon className="h-3.5 w-3.5" />
              )}
              {isSaving ? "Saving" : "All changes saved"}
            </span>
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={collisionDetection}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="grid flex-1 grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds.map((cardId) => board.cards[cardId])}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onDeleteCard={handleDeleteCard}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
};
