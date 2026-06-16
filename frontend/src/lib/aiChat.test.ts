import { appendMessage, trimChatHistory, type ChatMessage } from "@/lib/aiChat";

describe("aiChat helpers", () => {
  it("appends message entries in order", () => {
    const history: ChatMessage[] = [{ role: "user", content: "hello" }];
    const updated = appendMessage(history, "assistant", "hi");
    expect(updated).toEqual([
      { role: "user", content: "hello" },
      { role: "assistant", content: "hi" },
    ]);
  });

  it("trims history to the latest N messages", () => {
    const history: ChatMessage[] = Array.from({ length: 5 }).map((_, idx) => ({
      role: idx % 2 === 0 ? "user" : "assistant",
      content: `m${idx}`,
    }));
    expect(trimChatHistory(history, 3).map((entry) => entry.content)).toEqual([
      "m2",
      "m3",
      "m4",
    ]);
  });
});
