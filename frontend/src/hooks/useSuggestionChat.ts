import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { fetchSuggestionChat, sendSuggestionChatMessage } from "@/api/suggestion-chat";
import type { SuggestionChatMessage } from "@/types/suggestion-chat";

const SUGGESTION_CHAT_KEY = (projectId: string, suggestionId: string) =>
  ["projects", projectId, "suggestions", suggestionId, "chat"] as const;

export function useSuggestionChat({
  projectId,
  suggestionId,
  enabled,
}: {
  projectId: string;
  suggestionId: string;
  enabled: boolean;
}): UseQueryResult<ReadonlyArray<SuggestionChatMessage>, Error> {
  return useQuery({
    queryKey: SUGGESTION_CHAT_KEY(projectId, suggestionId),
    queryFn: () => fetchSuggestionChat({ projectId, suggestionId }),
    enabled: Boolean(projectId) && Boolean(suggestionId) && enabled,
  });
}

export function useSendSuggestionChatMessage({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}): UseMutationResult<SuggestionChatMessage, Error, string> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) =>
      sendSuggestionChatMessage({ projectId, suggestionId, message }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: SUGGESTION_CHAT_KEY(projectId, suggestionId),
      });
    },
  });
}
