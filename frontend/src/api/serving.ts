import type { ServeRequest, ServingStartResponse, ServingStatus } from "@/types/serving";
import { fetchApi } from "./client";

export function startServing({
  projectId,
  request,
}: {
  projectId: string;
  request: ServeRequest;
}): Promise<ServingStartResponse> {
  return fetchApi<ServingStartResponse>({
    path: `/projects/${projectId}/serve`,
    method: "POST",
    body: request,
  });
}

export function fetchServingStatus({ projectId }: { projectId: string }): Promise<ServingStatus> {
  return fetchApi<ServingStatus>({ path: `/projects/${projectId}/serve` });
}

export function stopServing({ projectId }: { projectId: string }): Promise<void> {
  return fetchApi<void>({
    path: `/projects/${projectId}/serve`,
    method: "DELETE",
  });
}
