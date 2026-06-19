import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { BoardSwitcher } from "@/components/BoardSwitcher";
import type { BoardMeta } from "@/lib/api";

const board = (id: number, name: string): BoardMeta => ({
  id,
  name,
  version: 1,
  createdAt: "t",
  updatedAt: "t",
});

const renderSwitcher = (overrides: Partial<Parameters<typeof BoardSwitcher>[0]> = {}) => {
  const props = {
    boards: [board(1, "My Board"), board(2, "Roadmap")],
    activeBoardId: 1,
    onSelect: vi.fn(),
    onCreate: vi.fn(),
    onRename: vi.fn(),
    onDelete: vi.fn(),
    ...overrides,
  };
  render(<BoardSwitcher {...props} />);
  return props;
};

describe("BoardSwitcher", () => {
  it("selects a board when its tab is clicked", async () => {
    const props = renderSwitcher();
    await userEvent.click(screen.getByRole("button", { name: "Roadmap" }));
    expect(props.onSelect).toHaveBeenCalledWith(2);
  });

  it("creates a board", async () => {
    const props = renderSwitcher();
    await userEvent.click(screen.getByRole("button", { name: "New board" }));
    expect(props.onCreate).toHaveBeenCalledTimes(1);
  });

  it("renames the active board through the inline editor", async () => {
    const props = renderSwitcher();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Rename board" }));

    const input = screen.getByLabelText("Board name");
    await user.clear(input);
    await user.type(input, "Q3 Plan{Enter}");

    expect(props.onRename).toHaveBeenCalledWith(1, "Q3 Plan");
  });

  it("deletes the active board", async () => {
    const props = renderSwitcher();
    await userEvent.click(screen.getByRole("button", { name: "Delete board" }));
    expect(props.onDelete).toHaveBeenCalledWith(1);
  });

  it("disables delete when only one board remains", () => {
    renderSwitcher({ boards: [board(1, "My Board")] });
    expect(screen.getByRole("button", { name: "Delete board" })).toBeDisabled();
  });
});
