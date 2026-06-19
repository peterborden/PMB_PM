import { expect, test, type Page } from "@playwright/test";

const installAuthMock = async (page: Page) => {
  let authenticated = false;
  let boardVersion = 1;
  const sharedMembers: string[] = [];
  let board = {
    columns: [
      { id: "col-backlog", title: "Backlog", cardIds: ["card-1", "card-2"] },
      { id: "col-discovery", title: "Discovery", cardIds: ["card-3"] },
      {
        id: "col-progress",
        title: "In Progress",
        cardIds: ["card-4", "card-5"],
      },
      { id: "col-review", title: "Review", cardIds: ["card-6"] },
      { id: "col-done", title: "Done", cardIds: ["card-7", "card-8"] },
    ],
    cards: {
      "card-1": {
        id: "card-1",
        title: "Align roadmap themes",
        details: "Draft quarterly themes with impact statements and metrics.",
      },
      "card-2": {
        id: "card-2",
        title: "Gather customer signals",
        details: "Review support tags, sales notes, and churn feedback.",
      },
      "card-3": {
        id: "card-3",
        title: "Prototype analytics view",
        details: "Sketch initial dashboard layout and key drill-downs.",
      },
      "card-4": {
        id: "card-4",
        title: "Refine status language",
        details: "Standardize column labels and tone across the board.",
      },
      "card-5": {
        id: "card-5",
        title: "Design card layout",
        details: "Add hierarchy and spacing for scanning dense lists.",
      },
      "card-6": {
        id: "card-6",
        title: "QA micro-interactions",
        details: "Verify hover, focus, and loading states.",
      },
      "card-7": {
        id: "card-7",
        title: "Ship marketing page",
        details: "Final copy approved and asset pack delivered.",
      },
      "card-8": {
        id: "card-8",
        title: "Close onboarding sprint",
        details: "Document release notes and share internally.",
      },
    },
  };

  const BOARD_ID = 1;
  const boardMeta = () => ({
    id: BOARD_ID,
    name: "My Board",
    version: boardVersion,
    createdAt: "2026-06-19T00:00:00.000Z",
    updatedAt: "2026-06-19T00:00:00.000Z",
  });
  const boardDetail = () => ({
    id: BOARD_ID,
    name: "My Board",
    version: boardVersion,
    board,
  });
  const unauthorized = (route: Parameters<Parameters<Page["route"]>[1]>[0]) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Authentication required" }),
    });

  // Catch-all for the boards API: list, single-board detail, and per-board AI
  // chat. `**/api/boards**` matches /api/boards, /api/boards/1, and
  // /api/boards/1/ai/chat; routing branches on path + method.
  await page.route("**/api/boards**", async (route) => {
    if (!authenticated) {
      await unauthorized(route);
      return;
    }

    const request = route.request();
    const method = request.method();
    const path = new URL(request.url()).pathname;

    if (path === "/api/boards" && method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ boards: [boardMeta()] }),
      });
      return;
    }

    if (path.includes("/members")) {
      if (method === "GET") {
        const members = [
          { username: "user", role: "owner" },
          ...sharedMembers.map((username) => ({ username, role: "editor" })),
        ];
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ members }),
        });
        return;
      }
      if (method === "POST") {
        const payload = request.postDataJSON() as { username: string };
        sharedMembers.push(payload.username);
        await route.fulfill({
          status: 201,
          contentType: "application/json",
          body: JSON.stringify({ username: payload.username, role: "editor" }),
        });
        return;
      }
      if (method === "DELETE") {
        await route.fulfill({ status: 204, body: "" });
        return;
      }
    }

    if (path.endsWith("/ai/chat") && method === "POST") {
      const payload = request.postDataJSON() as { message?: string };
      const nextBoard = structuredClone(board);
      nextBoard.columns[0].title = "AI Backlog";
      board = nextBoard;
      boardVersion += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          reply: `Handled: ${payload.message ?? ""}`,
          boardUpdated: true,
          board,
          version: boardVersion,
        }),
      });
      return;
    }

    if (method === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(boardDetail()),
      });
      return;
    }

    if (method === "PUT") {
      const payload = request.postDataJSON() as {
        board: typeof board;
        expectedVersion?: number;
      };
      if (
        payload.expectedVersion !== undefined &&
        payload.expectedVersion !== boardVersion
      ) {
        await route.fulfill({
          status: 409,
          contentType: "application/json",
          body: JSON.stringify({
            detail: `Version conflict. Current version is ${boardVersion}.`,
          }),
        });
        return;
      }
      board = payload.board;
      boardVersion += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(boardDetail()),
      });
      return;
    }

    await route.fulfill({
      status: 405,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Method not allowed" }),
    });
  });

  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        authenticated,
        username: authenticated ? "user" : null,
      }),
    });
  });

  await page.route("**/api/auth/login", async (route) => {
    const payload = route.request().postDataJSON() as {
      username?: string;
      password?: string;
    };
    if (payload.username === "user" && payload.password === "password") {
      authenticated = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ authenticated: true, username: "user" }),
      });
      return;
    }

    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Invalid credentials" }),
    });
  });

  await page.route("**/api/auth/logout", async (route) => {
    authenticated = false;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ authenticated: false, username: null }),
    });
  });
};

const loginViaUi = async (page: Page) => {
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
};

const dragCardToTarget = async (page: Page, cardId: string, targetTestId: string) => {
  const card = page.getByTestId(`card-${cardId}`);
  const target = page.getByTestId(targetTestId);
  await card.scrollIntoViewIfNeeded();
  await target.scrollIntoViewIfNeeded();

  const cardBox = await card.boundingBox();
  const targetBox = await target.boundingBox();
  if (!cardBox || !targetBox) {
    throw new Error("Unable to resolve drag coordinates.");
  }

  await page.mouse.move(
    cardBox.x + cardBox.width / 2,
    cardBox.y + cardBox.height / 2
  );
  await page.mouse.down();
  await page.mouse.move(
    targetBox.x + targetBox.width / 2,
    targetBox.y + targetBox.height / 2,
    { steps: 18 }
  );
  await page.mouse.up();
};

test("loads the kanban board", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  await expect(page.locator('[data-testid^="column-"]')).toHaveCount(5);
});

test("adds a card to a column", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  const firstColumn = page.locator('[data-testid^="column-"]').first();
  await firstColumn.getByRole("button", { name: /add a card/i }).click();
  await firstColumn.getByPlaceholder("Card title").fill("Playwright card");
  await firstColumn.getByPlaceholder("Details").fill("Added via e2e.");
  await firstColumn.getByRole("button", { name: /add card/i }).click();
  await expect(firstColumn.getByText("Playwright card")).toBeVisible();
});

test("edits a card via the editor", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);

  await page
    .locator('button[aria-label="Edit Align roadmap themes"]')
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Title").fill("Edited via e2e");
  await dialog.getByLabel("Labels").fill("urgent");
  await dialog.getByRole("button", { name: "Save" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByText("Edited via e2e")).toBeVisible();
  await expect(page.getByText("urgent")).toBeVisible();
});

test("shares a board with another user", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);

  await page.getByRole("button", { name: "Share board" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText("user", { exact: true })).toBeVisible();

  await dialog.getByLabel("Username to add").fill("bob");
  await dialog.getByRole("button", { name: "Add" }).click();

  await expect(dialog.getByText("bob", { exact: true })).toBeVisible();
});

test("assigns a card to a member", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);

  await page
    .locator('button[aria-label="Edit Align roadmap themes"]')
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await dialog.getByLabel("Assignee").selectOption("user");
  await dialog.getByRole("button", { name: "Save" }).click();

  await expect(dialog).toBeHidden();
  await expect(page.getByTestId("card-assignee").first()).toContainText("user");
});

test("moves a card between columns", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  const targetColumn = page.getByTestId("column-col-review");
  await dragCardToTarget(page, "card-1", "card-card-6");
  await expect(targetColumn.getByTestId("card-card-1")).toBeVisible();
});

test("can move cards back into an emptied column", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);

  const discoveryColumn = page.getByTestId("column-col-discovery");
  await expect(discoveryColumn.getByTestId("card-card-3")).toBeVisible();

  // Empty the Discovery column (it starts with one card).
  await dragCardToTarget(page, "card-3", "card-card-6");
  await expect(discoveryColumn.getByTestId("card-card-3")).toHaveCount(0);
  await expect(discoveryColumn.getByText("Drop a card here")).toBeVisible();

  // Move another card back into the now-empty Discovery column.
  await dragCardToTarget(page, "card-1", "column-col-discovery");
  await expect(discoveryColumn.getByTestId("card-card-1")).toBeVisible();
});

test("logs out to login screen", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
});

test("shows an error for invalid login", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await page.getByLabel("Username").fill("user");
  await page.getByLabel("Password").fill("wrong");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Invalid username or password.")).toBeVisible();
});

test("keeps session after refresh", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Kanban Studio" })).toBeVisible();
});

test("ai chat updates board automatically", async ({ page }) => {
  await installAuthMock(page);
  await page.goto("/");
  await loginViaUi(page);
  await page.getByLabel("Ask AI").fill("Rename backlog");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Handled: Rename backlog")).toBeVisible();
  await expect(page.getByLabel("Column title").first()).toHaveValue("AI Backlog");
});
