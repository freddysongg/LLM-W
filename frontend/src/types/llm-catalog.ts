import type { AIProvider } from "@/types/config";

export type LlmCatalogProvider = Exclude<AIProvider, "openai_compatible">;

export interface LlmModelOption {
  readonly provider: LlmCatalogProvider;
  readonly modelId: string;
  readonly label: string;
}
