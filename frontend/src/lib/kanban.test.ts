import {
  cardMatchesQuery,
  formatDueDate,
  isOverdue,
  moveCard,
  type Card,
  type Column,
} from "@/lib/kanban";

const card = (overrides: Partial<Card> = {}): Card => ({
  id: "card-1",
  title: "Ship release",
  details: "Cut the build and publish",
  ...overrides,
});

describe("cardMatchesQuery", () => {
  it("matches everything for an empty query", () => {
    expect(cardMatchesQuery(card(), "")).toBe(true);
    expect(cardMatchesQuery(card(), "   ")).toBe(true);
  });

  it("matches against title, details, labels, and assignee (case-insensitive)", () => {
    expect(cardMatchesQuery(card(), "SHIP")).toBe(true);
    expect(cardMatchesQuery(card(), "publish")).toBe(true);
    expect(cardMatchesQuery(card({ labels: ["urgent"] }), "urgent")).toBe(true);
    expect(cardMatchesQuery(card({ assignee: "alice" }), "alice")).toBe(true);
  });

  it("returns false when nothing matches", () => {
    expect(cardMatchesQuery(card(), "database")).toBe(false);
  });
});

describe("formatDueDate", () => {
  it("formats an ISO date as a short label without timezone drift", () => {
    expect(formatDueDate("2026-07-01")).toBe("Jul 1");
    expect(formatDueDate("2026-12-25")).toBe("Dec 25");
  });

  it("returns the raw value when it is not a valid ISO date", () => {
    expect(formatDueDate("nonsense")).toBe("nonsense");
  });
});

describe("isOverdue", () => {
  const today = new Date(2026, 5, 19); // 2026-06-19 (local)

  it("is true for dates before today", () => {
    expect(isOverdue("2026-06-18", today)).toBe(true);
  });

  it("is false for today or future dates", () => {
    expect(isOverdue("2026-06-19", today)).toBe(false);
    expect(isOverdue("2026-06-20", today)).toBe(false);
  });

  it("is false when there is no due date", () => {
    expect(isOverdue(null, today)).toBe(false);
    expect(isOverdue(undefined, today)).toBe(false);
  });
});

describe("moveCard", () => {
  const baseColumns: Column[] = [
    { id: "col-a", title: "A", cardIds: ["card-1", "card-2"] },
    { id: "col-b", title: "B", cardIds: ["card-3"] },
  ];

  it("reorders cards in the same column", () => {
    const result = moveCard(baseColumns, "card-2", "card-1");
    expect(result[0].cardIds).toEqual(["card-2", "card-1"]);
  });

  it("moves cards to another column", () => {
    const result = moveCard(baseColumns, "card-2", "card-3");
    expect(result[0].cardIds).toEqual(["card-1"]);
    expect(result[1].cardIds).toEqual(["card-2", "card-3"]);
  });

  it("drops cards to the end of a column", () => {
    const result = moveCard(baseColumns, "card-1", "col-b");
    expect(result[0].cardIds).toEqual(["card-2"]);
    expect(result[1].cardIds).toEqual(["card-3", "card-1"]);
  });
});
