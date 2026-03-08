import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { CreateProjectRequest, UpdateProjectRequest } from "@/types/project";
import {
  fetchProjects,
  fetchProject,
  createProject,
  updateProject,
  deleteProject,
  fetchProjectStorage,
} from "@/api/projects";

const PROJECTS_QUERY_KEY = ["projects"] as const;

export function useProjects() {
  return useQuery({
    queryKey: PROJECTS_QUERY_KEY,
    queryFn: fetchProjects,
  });
}

export function useProject({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: [...PROJECTS_QUERY_KEY, projectId],
    queryFn: () => fetchProject({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useProjectStorage({ projectId }: { projectId: string }) {
  return useQuery({
    queryKey: [...PROJECTS_QUERY_KEY, projectId, "storage"],
    queryFn: () => fetchProjectStorage({ projectId }),
    enabled: Boolean(projectId),
  });
}

export function useCreateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ request }: { request: CreateProjectRequest }) => createProject({ request }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
    },
  });
}

export function useUpdateProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId, request }: { projectId: string; request: UpdateProjectRequest }) =>
      updateProject({ projectId, request }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
    },
  });
}

export function useDeleteProject() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ projectId }: { projectId: string }) => deleteProject({ projectId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: PROJECTS_QUERY_KEY });
    },
  });
}
