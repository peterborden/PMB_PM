import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CardEditor } from "@/components/CardEditor";
import type { Card } from "@/lib/kanban";

const card: Card = {
  id: "card-1",
  title: "Ship release",
  details: "Publish the build",
  labels: ["urgent"],
  dueDate: "2026-07-01",
};

const setup = (overrides: Partial<Parameters<typeof CardEditor>[0]> = {}) => {
  const props = {
    card,
    onSave: vi.fn(),
    onDelete: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  };
  render(<CardEditor {...props} />);
  return props;
};

describe("CardEditor", () => {
  it("prefills fields from the card", () => {
    setup();
    expect(screen.getByLabelText("Title")).toHaveValue("Ship release");
    expect(screen.getByLabelText("Details")).toHaveValue("Publish the build");
    expect(screen.getByLabelText("Labels")).toHaveValue("urgent");
    expect(screen.getByLabelText("Due date")).toHaveValue("2026-07-01");
  });

  it("saves edited values with parsed labels", async () => {
    const props = setup();
    const user = userEvent.setup();
    const labels = screen.getByLabelText("Labels");
    await user.clear(labels);
    await user.type(labels, "urgent, backend, urgent");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(props.onSave).toHaveBeenCalledWith({
      title: "Ship release",
      details: "Publish the build",
      labels: ["urgent", "backend"],
      dueDate: "2026-07-01",
      assignee: null,
    });
  });

  it("assigns the card to a board member", async () => {
    const props = setup({ assigneeOptions: ["alice", "bob"] });
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Assignee"), "bob");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ assignee: "bob" })
    );
  });

  it("does not save with an empty title", async () => {
    const props = setup();
    const user = userEvent.setup();
    await user.clear(screen.getByLabelText("Title"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).not.toHaveBeenCalled();
  });

  it("closes on Escape and via Cancel", async () => {
    const props = setup();
    const user = userEvent.setup();
    await user.keyboard("{Escape}");
    expect(props.onClose).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(props.onClose).toHaveBeenCalledTimes(2);
  });

  it("clears the due date when emptied", async () => {
    const props = setup();
    const user = userEvent.setup();
    await user.clear(screen.getByLabelText("Due date"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(props.onSave).toHaveBeenCalledWith(
      expect.objectContaining({ dueDate: null })
    );
  });
});
