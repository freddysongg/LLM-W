import * as React from "react";
import { X } from "lucide-react";
import type { Project } from "@/types/project";
import type { ProjectStorageResponse } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ProjectDetailPanelProps {
  readonly project: Project | null;
  readonly storage: ProjectStorageResponse | null;
  readonly isLoadingStorage: boolean;
  readonly onClose: () => void;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"] as const;
  const index = Math.floor(Math.log(bytes) / Math.log(1024));
  const safeIndex = Math.min(index, units.length - 1);
  return `${(bytes / Math.pow(1024, safeIndex)).toFixed(1)} ${units[safeIndex]}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ProjectDetailPanel({
  project,
  storage,
  isLoadingStorage,
  onClose,
}: ProjectDetailPanelProps): React.JSX.Element | null {
  if (!project) return null;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <h2 className="font-semibold text-sm">{project.name}</h2>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
          <X className="h-4 w-4" />
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Metadata</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted-foreground">ID</span>
              <span className="font-mono text-xs truncate max-w-[180px]">{project.id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Description</span>
              <span className="text-right max-w-[180px]">{project.description || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Directory</span>
              <span className="font-mono text-xs truncate max-w-[180px]">
                {project.directoryPath}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Created</span>
              <span>{formatDate(project.createdAt)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted-foreground">Updated</span>
              <span>{formatDate(project.updatedAt)}</span>
            </div>
          </CardContent>
        </Card>

        {storage && !isLoadingStorage && (
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Storage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              <div className="flex justify-between font-medium">
                <span>Total</span>
                <span>{formatBytes(storage.totalBytes)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Checkpoints</span>
                <span>{formatBytes(storage.breakdown.checkpoints.bytes)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Logs</span>
                <span>{formatBytes(storage.breakdown.logs.bytes)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Activations</span>
                <span>{formatBytes(storage.breakdown.activations.bytes)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Exports</span>
                <span>{formatBytes(storage.breakdown.exports.bytes)}</span>
              </div>
              <div className="flex justify-between text-muted-foreground">
                <span>Reclaimable</span>
                <span className="text-amber-500">
                  {formatBytes(storage.retentionPolicy.reclaimableBytes)}
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoadingStorage && (
          <Card>
            <CardContent className="py-4 text-center text-sm text-muted-foreground">
              Loading storage info...
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
