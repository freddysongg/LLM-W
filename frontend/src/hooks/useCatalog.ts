import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchLlmModels, fetchModalGpus } from "@/api/catalog";
import type { ModalGpuOption } from "@/types/catalog";
import type { LlmModelOption } from "@/types/llm-catalog";

export const MODAL_GPUS_KEY = ["catalog", "modal-gpus"] as const;
export const LLM_MODELS_KEY = ["catalog", "llm-models"] as const;
const CATALOG_STALE_TIME_MS: number = 5 * 60 * 1000;

export function useModalGpus(): UseQueryResult<ReadonlyArray<ModalGpuOption>, Error> {
  return useQuery({
    queryKey: MODAL_GPUS_KEY,
    queryFn: fetchModalGpus,
    staleTime: CATALOG_STALE_TIME_MS,
  });
}

export function useLlmModels(): UseQueryResult<ReadonlyArray<LlmModelOption>, Error> {
  return useQuery({
    queryKey: LLM_MODELS_KEY,
    queryFn: fetchLlmModels,
    staleTime: CATALOG_STALE_TIME_MS,
  });
}
