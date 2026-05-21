import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from "@tanstack/react-query";

import { fetchAIRuleSettings, updateAIRuleSettings } from "@/api/ai-rule-settings";
import type { AIRuleSettings } from "@/types/ai-rule-settings";

const AI_RULE_SETTINGS_KEY = (projectId: string) =>
  ["projects", projectId, "ai-rule-settings"] as const;

export function useAIRuleSettings({
  projectId,
}: {
  projectId: string;
}): UseQueryResult<AIRuleSettings, Error> {
  return useQuery({
    queryKey: AI_RULE_SETTINGS_KEY(projectId),
    queryFn: () => fetchAIRuleSettings({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useUpdateAIRuleSettings({
  projectId,
}: {
  projectId: string;
}): UseMutationResult<AIRuleSettings, Error, AIRuleSettings> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: AIRuleSettings) => updateAIRuleSettings({ projectId, settings }),
    onSuccess: (next) => {
      queryClient.setQueryData(AI_RULE_SETTINGS_KEY(projectId), next);
    },
  });
}
