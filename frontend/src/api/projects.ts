import type { Project, CreateProjectRequest, UpdateProjectRequest } from "@/types/project";
import { fetchApi } from "./client";

interface RawProject {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly directory_path: string;
  readonly active_config_version_id: string | null;
  readonly created_at: string;
  readonly updated_at: string;
}

function normalizeProject(raw: RawProject): Project {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    directoryPath: raw.directory_path,
    activeConfigVersionId: raw.active_config_version_id,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  };
}

export async function fetchProjects(): Promise<ReadonlyArray<Project>> {
  const raw = await fetchApi<ReadonlyArray<RawProject>>({ path: "/projects" });
  return raw.map(normalizeProject);
}

export async function fetchProject({ projectId }: { projectId: string }): Promise<Project> {
  const raw = await fetchApi<RawProject>({ path: `/projects/${projectId}` });
  return normalizeProject(raw);
}

export async function createProject({
  request,
}: {
  request: CreateProjectRequest;
}): Promise<Project> {
  const raw = await fetchApi<RawProject>({ path: "/projects", method: "POST", body: request });
  return normalizeProject(raw);
}

export async function updateProject({
  projectId,
  request,
}: {
  projectId: string;
  request: UpdateProjectRequest;
}): Promise<Project> {
  const raw = await fetchApi<RawProject>({
    path: `/projects/${projectId}`,
    method: "PATCH",
    body: request,
  });
  return normalizeProject(raw);
}

export async function deleteProject({ projectId }: { projectId: string }): Promise<void> {
  return fetchApi<void>({ path: `/projects/${projectId}?confirm=true`, method: "DELETE" });
}
