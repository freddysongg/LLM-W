import type { Artifact, ArtifactType } from "@/types/artifact";
import { fetchApi } from "./client";

interface RawArtifact {
  readonly id: string;
  readonly run_id: string;
  readonly project_id: string;
  readonly artifact_type: string;
  readonly file_path: string;
  readonly file_size_bytes: number | null;
  readonly metadata_json: string | null;
  readonly is_retained: number;
  readonly created_at: string;
}

interface FetchArtifactsParams {
  readonly projectId: string;
  readonly runId?: string;
  readonly artifactType?: ArtifactType;
}

function normalizeArtifact(raw: RawArtifact): Artifact {
  let metadata: Record<string, unknown> | null = null;
  if (raw.metadata_json) {
    try {
      metadata = JSON.parse(raw.metadata_json) as Record<string, unknown>;
    } catch {
      // malformed metadata_json — treat as absent
    }
  }
  return {
    id: raw.id,
    runId: raw.run_id,
    projectId: raw.project_id,
    artifactType: raw.artifact_type as ArtifactType,
    filePath: raw.file_path,
    fileSizeBytes: raw.file_size_bytes,
    metadata,
    isRetained: raw.is_retained !== 0,
    createdAt: raw.created_at,
  };
}

export async function fetchArtifacts({
  projectId,
  runId,
  artifactType,
}: FetchArtifactsParams): Promise<ReadonlyArray<Artifact>> {
  const searchParams = new URLSearchParams();
  if (runId) searchParams.set("run_id", runId);
  if (artifactType) searchParams.set("artifact_type", artifactType);
  const query = searchParams.toString();
  const raw = await fetchApi<ReadonlyArray<RawArtifact>>({
    path: `/projects/${projectId}/artifacts${query ? `?${query}` : ""}`,
  });
  return raw.map(normalizeArtifact);
}

export async function deleteArtifact({
  projectId,
  artifactId,
}: {
  projectId: string;
  artifactId: string;
}): Promise<void> {
  return fetchApi<void>({
    path: `/projects/${projectId}/artifacts/${artifactId}`,
    method: "DELETE",
  });
}

export async function cleanupArtifacts({ projectId }: { projectId: string }): Promise<void> {
  return fetchApi<void>({
    path: `/projects/${projectId}/artifacts/cleanup`,
    method: "POST",
  });
}

export function getArtifactDownloadUrl({
  projectId,
  artifactId,
}: {
  projectId: string;
  artifactId: string;
}): string {
  return `/api/v1/projects/${projectId}/artifacts/${artifactId}/download`;
}
