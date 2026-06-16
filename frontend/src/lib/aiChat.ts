export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export const trimChatHistory = (history: ChatMessage[], limit = 12): ChatMessage[] => {
  if (limit <= 0) {
    return [];
  }
  if (history.length <= limit) {
    return history;
  }
  return history.slice(history.length - limit);
};

export const appendMessage = (
  history: ChatMessage[],
  role: ChatMessage["role"],
  content: string
): ChatMessage[] => [...history, { role, content }];
