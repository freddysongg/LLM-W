import type {
  Project,
  CreateProjectRequest,
  UpdateProjectRequest,
  ProjectStorageResponse,
} from "@/types/project";
import { fetchApi } from "./client";

export async function fetchProjects(): Promise<ReadonlyArray<Project>> {
  return fetchApi<ReadonlyArray<Project>>({ path: "/projects" });
}

export async function fetchProject({ projectId }: { projectId: string }): Promise<Project> {
  return fetchApi<Project>({ path: `/projects/${projectId}` });
}

export async function createProject({
  request,
}: {
  request: CreateProjectRequest;
}): Promise<Project> {
  return fetchApi<Project>({ path: "/projects", method: "POST", body: request });
}

export async function updateProject({
  projectId,
  request,
}: {
  projectId: string;
  request: UpdateProjectRequest;
}): Promise<Project> {
  return fetchApi<Project>({ path: `/projects/${projectId}`, method: "PATCH", body: request });
}

export async function deleteProject({ projectId }: { projectId: string }): Promise<void> {
  return fetchApi<void>({ path: `/projects/${projectId}?confirm=true`, method: "DELETE" });
}

export async function fetchProjectStorage({
  projectId,
}: {
  projectId: string;
}): Promise<ProjectStorageResponse> {
  return fetchApi<ProjectStorageResponse>({ path: `/projects/${projectId}/storage` });
}
