import { useQuery, useMutation, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  resolveDataset,
  fetchDatasetProfile,
  fetchSanitizeStatus,
  sanitizeProjectDataset,
} from "@/api/datasets";
import type {
  DatasetResolveRequest,
  SanitizeDatasetRequest,
  SanitizeStatus,
} from "@/types/dataset";

const PROFILE_KEY = (projectId: string) => ["projects", projectId, "dataset", "profile"] as const;

const SANITIZE_KEY = (projectId: string) => ["projects", projectId, "dataset", "sanitize"] as const;

const SANITIZE_STATUS_KEY = (projectId: string) =>
  ["projects", projectId, "dataset", "sanitize", "status"] as const;

export function useDatasetProfile({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: PROFILE_KEY(projectId),
    queryFn: () => fetchDatasetProfile({ projectId }),
    enabled: Boolean(projectId),
    retry: false,
  });
}

export function useResolveDataset({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: DatasetResolveRequest) => resolveDataset({ projectId, request }),
    onSuccess: (profile) => {
      queryClient.setQueryData(PROFILE_KEY(projectId), profile);
    },
  });
}

export function useSanitizeProjectDataset({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: SANITIZE_KEY(projectId),
    mutationFn: (request: SanitizeDatasetRequest) => sanitizeProjectDataset({ projectId, request }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: SANITIZE_STATUS_KEY(projectId) });
    },
  });
}

export function useSanitizeStatus({
  projectId,
}: {
  projectId: string;
}): UseQueryResult<SanitizeStatus, Error> {
  return useQuery({
    queryKey: SANITIZE_STATUS_KEY(projectId),
    queryFn: () => fetchSanitizeStatus({ projectId }),
    enabled: Boolean(projectId),
  });
}
