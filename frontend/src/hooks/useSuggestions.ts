import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { GenerateSuggestionsRequest } from "@/types/suggestion";
import {
  fetchSuggestions,
  fetchSuggestion,
  generateSuggestions,
  acceptSuggestion,
  rejectSuggestion,
} from "@/api/suggestions";

const SUGGESTIONS_KEY = (projectId: string) => ["projects", projectId, "suggestions"] as const;

const SUGGESTION_KEY = (projectId: string, suggestionId: string) =>
  ["projects", projectId, "suggestions", suggestionId] as const;

export function useSuggestions({ projectId, status }: { projectId: string; status?: string }) {
  return useQuery({
    queryKey: [...SUGGESTIONS_KEY(projectId), status],
    queryFn: () => fetchSuggestions({ projectId, status }),
    enabled: Boolean(projectId),
  });
}

export function useSuggestion({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}) {
  return useQuery({
    queryKey: SUGGESTION_KEY(projectId, suggestionId),
    queryFn: () => fetchSuggestion({ projectId, suggestionId }),
    enabled: Boolean(projectId) && Boolean(suggestionId),
  });
}

export function useGenerateSuggestions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      projectId,
      request,
    }: {
      projectId: string;
      request: GenerateSuggestionsRequest;
    }) => generateSuggestions({ projectId, request }),
    onSuccess: (_data, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS_KEY(projectId) });
    },
  });
}

export function useAcceptSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, suggestionId }: { projectId: string; suggestionId: string }) =>
      acceptSuggestion({ projectId, suggestionId }),
    onSuccess: (_data, { projectId, suggestionId }) => {
      void queryClient.invalidateQueries({ queryKey: SUGGESTION_KEY(projectId, suggestionId) });
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS_KEY(projectId) });
    },
  });
}

export function useRejectSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, suggestionId }: { projectId: string; suggestionId: string }) =>
      rejectSuggestion({ projectId, suggestionId }),
    onSuccess: (_data, { projectId, suggestionId }) => {
      void queryClient.invalidateQueries({ queryKey: SUGGESTION_KEY(projectId, suggestionId) });
      void queryClient.invalidateQueries({ queryKey: SUGGESTIONS_KEY(projectId) });
    },
  });
}
