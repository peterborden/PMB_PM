import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { KanbanBoard } from "@/components/KanbanBoard";
import { initialData, type BoardData } from "@/lib/kanban";

const getFirstColumn = () => screen.getAllByTestId(/column-/i)[0];

const KanbanBoardHarness = () => {
  const [board, setBoard] = useState<BoardData>(initialData);
  return (
    <KanbanBoard
      board={board}
      onBoardChange={setBoard}
      assigneeOptions={["alice", "bob"]}
    />
  );
};

describe("KanbanBoard", () => {
  it("renders five columns", () => {
    render(<KanbanBoardHarness />);
    expect(screen.getAllByTestId(/column-/i)).toHaveLength(5);
  });

  it("renames a column", async () => {
    render(<KanbanBoardHarness />);
    const column = getFirstColumn();
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "New Name");
    expect(input).toHaveValue("New Name");
  });

  it("adds and removes a card", async () => {
    render(<KanbanBoardHarness />);
    const column = getFirstColumn();
    const addButton = within(column).getByRole("button", {
      name: /add a card/i,
    });
    await userEvent.click(addButton);

    const titleInput = within(column).getByPlaceholderText(/card title/i);
    await userEvent.type(titleInput, "New card");
    const detailsInput = within(column).getByPlaceholderText(/details/i);
    await userEvent.type(detailsInput, "Notes");

    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    expect(within(column).getByText("New card")).toBeInTheDocument();

    const deleteButton = within(column).getByRole("button", {
      name: /delete new card/i,
    });
    await userEvent.click(deleteButton);

    expect(within(column).queryByText("New card")).not.toBeInTheDocument();
  });

  it("adds a card with labels and a due date", async () => {
    render(<KanbanBoardHarness />);
    const column = getFirstColumn();
    await userEvent.click(
      within(column).getByRole("button", { name: /add a card/i })
    );

    await userEvent.type(
      within(column).getByPlaceholderText(/card title/i),
      "Tagged card"
    );
    await userEvent.type(within(column).getByLabelText("Labels"), "urgent, backend");
    fireEvent.change(within(column).getByLabelText("Due date"), {
      target: { value: "2026-07-01" },
    });
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    const card = within(column).getByText("Tagged card").closest("article")!;
    expect(within(card).getByText("urgent")).toBeInTheDocument();
    expect(within(card).getByText("backend")).toBeInTheDocument();
    expect(within(card).getByTestId("card-due-date")).toHaveTextContent("Jul 1");
  });

  it("edits an existing card through the editor", async () => {
    render(<KanbanBoardHarness />);
    await userEvent.click(
      screen.getByRole("button", { name: "Edit Align roadmap themes" })
    );

    const dialog = screen.getByRole("dialog");
    const titleInput = within(dialog).getByLabelText("Title");
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Updated roadmap");
    await userEvent.type(within(dialog).getByLabelText("Labels"), "urgent");
    fireEvent.change(within(dialog).getByLabelText("Due date"), {
      target: { value: "2026-07-01" },
    });
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    const card = screen.getByText("Updated roadmap").closest("article")!;
    expect(within(card).getByText("urgent")).toBeInTheDocument();
    expect(within(card).getByTestId("card-due-date")).toHaveTextContent("Jul 1");
  });

  it("assigns a card to a member via the editor", async () => {
    render(<KanbanBoardHarness />);
    await userEvent.click(
      screen.getByRole("button", { name: "Edit Align roadmap themes" })
    );

    const dialog = screen.getByRole("dialog");
    await userEvent.selectOptions(within(dialog).getByLabelText("Assignee"), "alice");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save" }));

    const card = screen.getByText("Align roadmap themes").closest("article")!;
    expect(within(card).getByTestId("card-assignee")).toHaveTextContent("alice");
  });

  it("deletes a card from the editor", async () => {
    render(<KanbanBoardHarness />);
    await userEvent.click(
      screen.getByRole("button", { name: "Edit Gather customer signals" })
    );
    const dialog = screen.getByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete card" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.queryByText("Gather customer signals")).not.toBeInTheDocument();
  });

  it("filters cards with the search box", async () => {
    render(<KanbanBoardHarness />);
    expect(screen.getByText("Align roadmap themes")).toBeInTheDocument();
    expect(screen.getByText("Gather customer signals")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Search cards"), "roadmap");

    expect(screen.getByText("Align roadmap themes")).toBeInTheDocument();
    expect(screen.queryByText("Gather customer signals")).not.toBeInTheDocument();
  });
});
