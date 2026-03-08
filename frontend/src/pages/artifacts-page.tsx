import * as React from "react";
import type { ArtifactType } from "@/types/artifact";
import type { Artifact } from "@/types/artifact";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import { useArtifacts, useDeleteArtifact, useCleanupArtifacts } from "@/hooks/useArtifacts";
import { useProjectStorage, useCleanupStorage } from "@/hooks/useStorage";
import { ArtifactTable } from "@/components/artifacts/artifact-table";
import { ArtifactDetailDrawer } from "@/components/artifacts/artifact-detail-drawer";
import { TypeFilter } from "@/components/artifacts/type-filter";
import { RunFilter } from "@/components/artifacts/run-filter";
import { StorageSummary } from "@/components/artifacts/storage-summary";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

export default function ArtifactsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedArtifactId, setSelectedArtifactId] = React.useState<string | null>(null);
  const [typeFilter, setTypeFilter] = React.useState<ArtifactType | undefined>(undefined);
  const [runFilter, setRunFilter] = React.useState<string | undefined>(undefined);

  const projectId = activeProjectId ?? "";

  const { data: runs = [] } = useRuns({ projectId });
  const { data: artifacts = [], isLoading } = useArtifacts({
    projectId,
    runId: runFilter,
    artifactType: typeFilter,
  });
  const { data: storage } = useProjectStorage({ projectId });

  const deleteMutation = useDeleteArtifact();
  const cleanupArtifactsMutation = useCleanupArtifacts();
  const cleanupStorageMutation = useCleanupStorage();

  const selectedArtifact: Artifact | null =
    artifacts.find((a) => a.id === selectedArtifactId) ?? null;

  const handleDelete = (artifactId: string): void => {
    if (!projectId) return;
    deleteMutation.mutate(
      { projectId, artifactId },
      {
        onSuccess: () => {
          if (selectedArtifactId === artifactId) {
            setSelectedArtifactId(null);
          }
        },
      },
    );
  };

  const handleBulkCleanup = (): void => {
    if (!projectId) return;
    cleanupArtifactsMutation.mutate({ projectId });
  };

  const handleStorageCleanup = (): void => {
    if (!projectId) return;
    cleanupStorageMutation.mutate({ projectId });
  };

  if (!activeProjectId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Select a project to view artifacts.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between h-14 px-6 border-b">
        <h1 className="text-xl font-semibold">Artifacts</h1>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" disabled={cleanupArtifactsMutation.isPending}>
              {cleanupArtifactsMutation.isPending ? "Running cleanup…" : "Bulk cleanup"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Run retention policy cleanup?</AlertDialogTitle>
              <AlertDialogDescription>
                This will delete non-retained artifacts according to the project retention policy.
                Retained artifacts will not be affected.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleBulkCleanup}>Run cleanup</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-3 border-b">
            <TypeFilter value={typeFilter} onChange={setTypeFilter} />
            <RunFilter runs={runs} value={runFilter} onChange={setRunFilter} />
          </div>

          <div className="flex-1 overflow-y-auto px-6">
            {isLoading ? (
              <div className="py-8 text-sm text-muted-foreground">Loading artifacts…</div>
            ) : (
              <ArtifactTable
                artifacts={artifacts}
                projectId={projectId}
                selectedArtifactId={selectedArtifactId}
                isDeleting={deleteMutation.isPending}
                onSelect={setSelectedArtifactId}
                onDelete={handleDelete}
              />
            )}
          </div>
        </div>

        {storage && (
          <div className="w-64 shrink-0 border-l p-4 overflow-y-auto">
            <StorageSummary
              storage={storage}
              isCleaningUp={cleanupStorageMutation.isPending}
              onCleanup={handleStorageCleanup}
            />
          </div>
        )}
      </div>

      <ArtifactDetailDrawer
        artifact={selectedArtifact}
        projectId={projectId}
        onClose={() => setSelectedArtifactId(null)}
      />
    </div>
  );
}
