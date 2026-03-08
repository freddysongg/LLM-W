import type { ConfigVersion, SaveConfigRequest } from "@/types/config";
import { fetchApi } from "./client";

export async function fetchActiveConfig({
  projectId,
}: {
  projectId: string;
}): Promise<ConfigVersion> {
  return fetchApi<ConfigVersion>({ path: `/projects/${projectId}/configs/active` });
}

export async function saveConfig({
  projectId,
  request,
}: {
  projectId: string;
  request: SaveConfigRequest;
}): Promise<ConfigVersion> {
  return fetchApi<ConfigVersion>({
    path: `/projects/${projectId}/configs`,
    method: "PUT",
    body: {
      yaml_content: request.yamlContent,
      source_tag: request.sourceTag,
      source_detail: request.sourceDetail ?? null,
    },
  });
}
