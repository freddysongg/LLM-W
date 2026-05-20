import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { fetchModalGpus } from "@/api/catalog";
import type { ModalGpuOption } from "@/types/catalog";

export const MODAL_GPUS_KEY = ["catalog", "modal-gpus"] as const;
const MODAL_GPUS_STALE_TIME_MS: number = 5 * 60 * 1000;

export function useModalGpus(): UseQueryResult<ReadonlyArray<ModalGpuOption>, Error> {
  return useQuery({
    queryKey: MODAL_GPUS_KEY,
    queryFn: fetchModalGpus,
    staleTime: MODAL_GPUS_STALE_TIME_MS,
  });
}
