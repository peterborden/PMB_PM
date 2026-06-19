export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  // Local-only message (e.g. an error notice) that is shown in the thread but
  // not sent back to the AI as conversation context.
  transient?: boolean;
};

export const trimChatHistory = (history: ChatMessage[], limit = 12): ChatMessage[] => {
  if (limit <= 0) {
    return [];
  }
  const durable = history.filter((message) => !message.transient);
  if (durable.length <= limit) {
    return durable;
  }
  return durable.slice(durable.length - limit);
};

export const appendMessage = (
  history: ChatMessage[],
  role: ChatMessage["role"],
  content: string,
  transient = false
): ChatMessage[] => [
  ...history,
  transient ? { role, content, transient: true } : { role, content },
];
