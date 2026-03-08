import * as React from "react";
import { useState } from "react";
import { Plus } from "lucide-react";
import {
  useProjects,
  useCreateProject,
  useDeleteProject,
  useProjectStorage,
} from "@/hooks/useProjects";
import { useAppStore } from "@/stores/app-store";
import { ProjectList } from "@/components/projects/project-list";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { DeleteProjectAction } from "@/components/projects/delete-project-action";
import { ProjectDetailPanel } from "@/components/projects/project-detail-panel";
import { ImportExportActions } from "@/components/projects/import-export-actions";
import { Button } from "@/components/ui/button";
import type { Project, CreateProjectRequest } from "@/types/project";

export default function ProjectsPage(): React.JSX.Element {
  const { data: projects, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const { setActiveProjectId } = useAppStore();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const pendingDeleteProject = projects?.find((p) => p.id === pendingDeleteId) ?? null;

  const { data: selectedStorage, isLoading: isLoadingStorage } = useProjectStorage({
    projectId: selectedProject?.id ?? "",
  });

  const handleCreate = (name: string, description: string): void => {
    createProject.mutate(
      { request: { name, description } },
      { onSuccess: () => setIsCreateOpen(false) },
    );
  };

  const handleSelect = (projectId: string): void => {
    const project = projects?.find((p) => p.id === projectId) ?? null;
    setSelectedProject(project);
    setActiveProjectId(projectId);
  };

  const handleDeleteConfirm = (): void => {
    if (!pendingDeleteId) return;
    deleteProject.mutate(
      { projectId: pendingDeleteId },
      {
        onSuccess: () => {
          if (selectedProject?.id === pendingDeleteId) {
            setSelectedProject(null);
            setActiveProjectId(null);
          }
          setPendingDeleteId(null);
        },
      },
    );
  };

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col min-w-0">
        <div className="flex items-center justify-between h-14 px-6 border-b">
          <h1 className="text-xl font-semibold">Projects</h1>
          <div className="flex items-center gap-2">
            <ImportExportActions
              selectedProject={selectedProject}
              onImport={(request: CreateProjectRequest) =>
                createProject.mutate({ request }, { onSuccess: () => {} })
              }
              isImporting={createProject.isPending}
            />
            <Button onClick={() => setIsCreateOpen(true)} size="sm">
              <Plus className="h-4 w-4 mr-1" />
              New Project
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {isLoading && (
            <div className="flex items-center justify-center py-16 text-muted-foreground text-sm">
              Loading projects...
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center py-16 text-destructive text-sm">
              Failed to load projects.
            </div>
          )}
          {projects && (
            <ProjectList
              projects={projects}
              onSelect={handleSelect}
              onDelete={(id) => setPendingDeleteId(id)}
            />
          )}
        </div>
      </div>

      {selectedProject && (
        <div className="w-80 border-l shrink-0 flex flex-col">
          <ProjectDetailPanel
            project={selectedProject}
            storage={selectedStorage ?? null}
            isLoadingStorage={isLoadingStorage}
            onClose={() => setSelectedProject(null)}
          />
        </div>
      )}

      <CreateProjectDialog
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onCreate={handleCreate}
        isCreating={createProject.isPending}
      />

      {pendingDeleteProject && (
        <DeleteProjectAction
          projectName={pendingDeleteProject.name}
          isOpen={Boolean(pendingDeleteId)}
          onConfirm={handleDeleteConfirm}
          onCancel={() => setPendingDeleteId(null)}
          isDeleting={deleteProject.isPending}
        />
      )}
    </div>
  );
}
