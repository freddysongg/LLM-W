import type { SuggestionChatMessage, SuggestionChatRole } from "@/types/suggestion-chat";
import { fetchApi } from "./client";

interface RawSuggestionChatMessage {
  readonly id: string;
  readonly suggestion_id: string;
  readonly role: SuggestionChatRole;
  readonly content: string;
  readonly created_at: string;
}

interface RawSuggestionChatListResponse {
  readonly messages: ReadonlyArray<RawSuggestionChatMessage>;
}

function normalize(raw: RawSuggestionChatMessage): SuggestionChatMessage {
  return {
    id: raw.id,
    suggestionId: raw.suggestion_id,
    role: raw.role,
    content: raw.content,
    createdAt: raw.created_at,
  };
}

export async function fetchSuggestionChat({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}): Promise<ReadonlyArray<SuggestionChatMessage>> {
  const raw = await fetchApi<RawSuggestionChatListResponse>({
    path: `/projects/${projectId}/suggestions/${suggestionId}/chat`,
  });
  return raw.messages.map(normalize);
}

export async function sendSuggestionChatMessage({
  projectId,
  suggestionId,
  message,
}: {
  projectId: string;
  suggestionId: string;
  message: string;
}): Promise<SuggestionChatMessage> {
  const raw = await fetchApi<RawSuggestionChatMessage>({
    path: `/projects/${projectId}/suggestions/${suggestionId}/chat`,
    method: "POST",
    body: { message },
  });
  return normalize(raw);
}
