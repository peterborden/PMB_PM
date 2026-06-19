import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ShareDialog } from "@/components/ShareDialog";
import type { BoardMember } from "@/lib/api";

const members: BoardMember[] = [
  { username: "alice", role: "owner" },
  { username: "bob", role: "editor" },
];

const setup = (overrides: Partial<Parameters<typeof ShareDialog>[0]> = {}) => {
  const props = {
    boardName: "Roadmap",
    members,
    isOwner: true,
    onAdd: vi.fn(),
    onRemove: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  };
  render(<ShareDialog {...props} />);
  return props;
};

describe("ShareDialog", () => {
  it("lists members with their roles", () => {
    setup();
    const list = screen.getByRole("list", { name: "Board members" });
    expect(within(list).getByText("alice")).toBeInTheDocument();
    expect(within(list).getByText("bob")).toBeInTheDocument();
    expect(within(list).getByText("owner")).toBeInTheDocument();
    expect(within(list).getByText("editor")).toBeInTheDocument();
  });

  it("adds a member by username", async () => {
    const props = setup();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username to add"), "carol");
    await user.click(screen.getByRole("button", { name: "Add" }));
    expect(props.onAdd).toHaveBeenCalledWith("carol");
  });

  it("removes a non-owner member", async () => {
    const props = setup();
    await userEvent.click(screen.getByRole("button", { name: "Remove bob" }));
    expect(props.onRemove).toHaveBeenCalledWith("bob");
  });

  it("does not offer to remove the owner", () => {
    setup();
    expect(
      screen.queryByRole("button", { name: "Remove alice" })
    ).not.toBeInTheDocument();
  });

  it("hides management controls for non-owners", () => {
    setup({ isOwner: false });
    expect(screen.queryByLabelText("Username to add")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Remove bob" })
    ).not.toBeInTheDocument();
  });

  it("shows an error message when provided", () => {
    setup({ error: "No user with that username." });
    expect(screen.getByText("No user with that username.")).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const props = setup();
    await userEvent.keyboard("{Escape}");
    expect(props.onClose).toHaveBeenCalled();
  });
});
