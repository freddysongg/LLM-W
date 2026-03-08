import type { ModelProfile, ModelResolveRequest, ModelArchitectureResponse } from "@/types/model";
import { fetchApi } from "./client";

export function resolveModel({
  projectId,
  request,
}: {
  projectId: string;
  request: ModelResolveRequest;
}): Promise<ModelProfile> {
  return fetchApi<ModelProfile>({
    path: `/projects/${projectId}/models/resolve`,
    method: "POST",
    body: request,
  });
}

export function fetchModelProfile({ projectId }: { projectId: string }): Promise<ModelProfile> {
  return fetchApi<ModelProfile>({ path: `/projects/${projectId}/models/profile` });
}

export function fetchModelArchitecture({
  projectId,
}: {
  projectId: string;
}): Promise<ModelArchitectureResponse> {
  return fetchApi<ModelArchitectureResponse>({
    path: `/projects/${projectId}/models/architecture`,
  });
}
