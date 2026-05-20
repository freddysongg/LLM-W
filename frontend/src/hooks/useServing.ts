import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchServingStatus, startServing, stopServing } from "@/api/serving";
import type { ServeRequest, ServingStatus } from "@/types/serving";

const STARTING_POLL_MS = 3_000;
const RUNNING_POLL_MS = 15_000;

const servingQueryKey = (projectId: string) => ["projects", projectId, "serving"] as const;

function selectPollInterval(status: ServingStatus | undefined): number | false {
  if (status === undefined) {
    return false;
  }
  if (status.state === "starting" || status.state === "stopping") {
    return STARTING_POLL_MS;
  }
  if (status.state === "running") {
    return RUNNING_POLL_MS;
  }
  return false;
}

export function useServingStatus({
  projectId,
  enabled = true,
}: {
  projectId: string;
  enabled?: boolean;
}) {
  return useQuery({
    queryKey: servingQueryKey(projectId),
    queryFn: () => fetchServingStatus({ projectId }),
    enabled: enabled && Boolean(projectId),
    refetchInterval: (query) => selectPollInterval(query.state.data),
    refetchIntervalInBackground: false,
  });
}

export function useStartServing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, request }: { projectId: string; request: ServeRequest }) =>
      startServing({ projectId, request }),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: servingQueryKey(projectId) });
    },
  });
}

export function useStopServing() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId }: { projectId: string }) => stopServing({ projectId }),
    onSuccess: (_, { projectId }) => {
      void queryClient.invalidateQueries({ queryKey: servingQueryKey(projectId) });
    },
  });
}
