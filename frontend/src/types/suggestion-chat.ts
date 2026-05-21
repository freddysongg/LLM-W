export type SuggestionChatRole = "user" | "assistant";

export interface SuggestionChatMessage {
  readonly id: string;
  readonly suggestionId: string;
  readonly role: SuggestionChatRole;
  readonly content: string;
  readonly createdAt: string;
}
