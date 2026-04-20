import * as React from "react";
import { useMemo, useState } from "react";
import { Grid3x3, List, Plus, Search } from "lucide-react";
import {
  useProjects,
  useCreateProject,
  useDeleteProject,
  useProjectStorage,
} from "@/hooks/useProjects";
import { useAppStore } from "@/stores/app-store";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { ProjectList } from "@/components/projects/project-list";
import { ProjectGrid } from "@/components/projects/project-grid";
import { CreateProjectDialog } from "@/components/projects/create-project-dialog";
import { DeleteProjectAction } from "@/components/projects/delete-project-action";
import { ProjectDetailPanel } from "@/components/projects/project-detail-panel";
import { ImportExportActions } from "@/components/projects/import-export-actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type { Project, CreateProjectRequest } from "@/types/project";

type ProjectsView = "grid" | "list";
type ProjectsSort = "updated" | "name";

export default function ProjectsPage(): React.JSX.Element {
  const { data: projects, isLoading, error } = useProjects();
  const createProject = useCreateProject();
  const deleteProject = useDeleteProject();
  const { setActiveProjectId } = useAppStore();

  const [isCreateOpen, setIsCreateOpen] = useState<boolean>(false);
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [view, setView] = useState<ProjectsView>("grid");
  const [sort, setSort] = useState<ProjectsSort>("updated");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const isAnimationLocked = useLockEntered();

  const pendingDeleteProject =
    projects?.find((candidate) => candidate.id === pendingDeleteId) ?? null;

  const { data: selectedStorage, isLoading: isLoadingStorage } = useProjectStorage({
    projectId: selectedProject?.id ?? "",
  });

  const filteredProjects = useMemo<ReadonlyArray<Project>>(() => {
    if (!projects) return [];
    const query = searchQuery.trim().toLowerCase();
    const matching = query
      ? projects.filter((candidate) => candidate.name.toLowerCase().includes(query))
      : projects;
    const sorted = [...matching];
    if (sort === "name") {
      sorted.sort((left, right) => left.name.localeCompare(right.name));
    } else {
      sorted.sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
    }
    return sorted;
  }, [projects, searchQuery, sort]);

  const handleCreate = (name: string, description: string): void => {
    createProject.mutate(
      { request: { name, description } },
      { onSuccess: () => setIsCreateOpen(false) },
    );
  };

  const handleSelect = (projectId: string): void => {
    const project = projects?.find((candidate) => candidate.id === projectId) ?? null;
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

  const enteredClass = isAnimationLocked ? "entered" : "";
  const runningCount = 0;

  return (
    <div className="flex h-full">
      <div className="flex min-w-0 flex-1 flex-col">
        <header
          className={cn(
            "flex items-start justify-between gap-4 px-6 pt-6 enter enter-1",
            enteredClass,
          )}
        >
          <div>
            <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
              Projects
            </h1>
            <p className="mt-1 font-mono text-[11px] text-ink-3">
              {projects?.length ?? 0} projects · {runningCount} running
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-[220px]">
              <Input
                placeholder="Search projects"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                icon={<Search className="h-3.5 w-3.5" aria-hidden="true" />}
                aria-label="Search projects"
              />
            </div>
            <Select value={sort} onValueChange={(value) => setSort(value as ProjectsSort)}>
              <SelectTrigger className="w-[150px]" aria-label="Sort projects">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="updated">Sort: updated</SelectItem>
                <SelectItem value="name">Sort: name</SelectItem>
              </SelectContent>
            </Select>
            <div
              className="inline-flex items-center gap-0.5 rounded-md border border-hairline bg-surface-2 p-0.5"
              role="radiogroup"
              aria-label="View mode"
            >
              <button
                type="button"
                role="radio"
                aria-checked={view === "grid"}
                aria-label="Grid view"
                onClick={() => setView("grid")}
                className={cn(
                  "inline-grid h-6 w-7 place-items-center rounded-[4px] transition-colors",
                  "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
                  view === "grid"
                    ? "bg-surface text-ink-1 shadow-token-xs"
                    : "text-ink-3 hover:text-ink-1",
                )}
              >
                <Grid3x3 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={view === "list"}
                aria-label="List view"
                onClick={() => setView("list")}
                className={cn(
                  "inline-grid h-6 w-7 place-items-center rounded-[4px] transition-colors",
                  "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
                  view === "list"
                    ? "bg-surface text-ink-1 shadow-token-xs"
                    : "text-ink-3 hover:text-ink-1",
                )}
              >
                <List className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
            <ImportExportActions
              selectedProject={selectedProject}
              onImport={(request: CreateProjectRequest) =>
                createProject.mutate({ request }, { onSuccess: () => {} })
              }
              isImporting={createProject.isPending}
            />
            <Button variant="primary" size="sm" onClick={() => setIsCreateOpen(true)}>
              <Plus aria-hidden="true" />
              New project
            </Button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {isLoading && (
            <div className="flex items-center justify-center py-16 font-mono text-[11px] text-ink-3">
              Loading projects…
            </div>
          )}
          {error && (
            <div className="flex items-center justify-center py-16 font-mono text-[11px] text-[color:var(--danger)]">
              Failed to load projects.
            </div>
          )}
          {projects && (
            <div className={cn("enter enter-2", enteredClass)}>
              {view === "grid" ? (
                <ProjectGrid projects={filteredProjects} onSelect={handleSelect} />
              ) : (
                <ProjectList
                  projects={filteredProjects}
                  selectedProjectId={selectedProject?.id ?? null}
                  onSelect={handleSelect}
                  onDelete={(projectId) => setPendingDeleteId(projectId)}
                />
              )}
            </div>
          )}
        </div>
      </div>

      {selectedProject && (
        <div className="flex w-80 shrink-0 flex-col border-l border-hairline bg-surface">
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
