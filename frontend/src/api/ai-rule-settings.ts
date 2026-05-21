import type { AIRuleName, AIRuleSettings } from "@/types/ai-rule-settings";
import { fetchApi } from "./client";

type RawAIRuleSettings = Record<AIRuleName, { readonly enabled: boolean }>;

function normalize(raw: RawAIRuleSettings): AIRuleSettings {
  return raw as AIRuleSettings;
}

export async function fetchAIRuleSettings({
  projectId,
}: {
  projectId: string;
}): Promise<AIRuleSettings> {
  const raw = await fetchApi<RawAIRuleSettings>({
    path: `/projects/${projectId}/ai-rule-settings`,
  });
  return normalize(raw);
}

export async function updateAIRuleSettings({
  projectId,
  settings,
}: {
  projectId: string;
  settings: AIRuleSettings;
}): Promise<AIRuleSettings> {
  const raw = await fetchApi<RawAIRuleSettings>({
    path: `/projects/${projectId}/ai-rule-settings`,
    method: "PUT",
    body: settings,
  });
  return normalize(raw);
}
