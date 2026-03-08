import * as React from "react";
import { useProject } from "@/hooks/useProjects";
import { useProjectStorage } from "@/hooks/useStorage";
import { useRuns } from "@/hooks/useRuns";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import type { RunStatus } from "@/types/run";

interface ProjectDetailPanelProps {
  readonly projectId: string;
}

function formatBytes(bytes: number): string {
  if (bytes >= 1_073_741_824) return `${(bytes / 1_073_741_824).toFixed(1)} GB`;
  if (bytes >= 1_048_576) return `${(bytes / 1_048_576).toFixed(1)} MB`;
  if (bytes >= 1_024) return `${(bytes / 1_024).toFixed(1)} KB`;
  return `${bytes} B`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function runStatusVariant(status: RunStatus): "default" | "secondary" | "destructive" | "outline" {
  switch (status) {
    case "running":
      return "default";
    case "completed":
      return "secondary";
    case "failed":
      return "destructive";
    case "cancelled":
    case "paused":
    case "pending":
      return "outline";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

interface InfoRowProps {
  readonly label: string;
  readonly value: React.ReactNode;
}

function InfoRow({ label, value }: InfoRowProps): React.JSX.Element {
  return (
    <div className="py-1.5">
      <p className="text-xs text-muted-foreground mb-0.5">{label}</p>
      <p className="text-xs break-all">{value}</p>
    </div>
  );
}

interface SectionHeaderProps {
  readonly title: string;
}

function SectionHeader({ title }: SectionHeaderProps): React.JSX.Element {
  return (
    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
      {title}
    </p>
  );
}

export function ProjectDetailPanel({ projectId }: ProjectDetailPanelProps): React.JSX.Element {
  const { data: project, isLoading: isProjectLoading } = useProject({ projectId });
  const { data: storage } = useProjectStorage({ projectId });
  const { data: runs = [] } = useRuns({ projectId });

  if (isProjectLoading) {
    return <p className="text-sm text-muted-foreground">Loading…</p>;
  }

  if (!project) {
    return <p className="text-sm text-muted-foreground">Project not found.</p>;
  }

  const { name, description, directoryPath, createdAt, updatedAt } = project;

  const lastRun = [...runs].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime(),
  )[0];

  return (
    <div className="space-y-3">
      <div>
        <p className="text-sm font-medium">{name}</p>
        {description && (
          <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{description}</p>
        )}
      </div>

      <Separator />

      <div className="space-y-0.5">
        <InfoRow label="Directory" value={directoryPath} />
        <InfoRow label="Created" value={formatDate(createdAt)} />
        <InfoRow label="Updated" value={formatDate(updatedAt)} />
      </div>

      <Separator />

      <div>
        <SectionHeader title="Storage" />
        {storage ? (
          <div className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Total</span>
              <span className="font-mono">{formatBytes(storage.totalBytes)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Checkpoints</span>
              <span className="font-mono">{formatBytes(storage.breakdown.checkpoints.bytes)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Logs</span>
              <span className="font-mono">{formatBytes(storage.breakdown.logs.bytes)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Activations</span>
              <span className="font-mono">{formatBytes(storage.breakdown.activations.bytes)}</span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-muted-foreground">Exports</span>
              <span className="font-mono">{formatBytes(storage.breakdown.exports.bytes)}</span>
            </div>
            {storage.retentionPolicy.reclaimableBytes > 0 && (
              <div className="flex justify-between text-xs">
                <span className="text-muted-foreground">Reclaimable</span>
                <span className="font-mono text-amber-500">
                  {formatBytes(storage.retentionPolicy.reclaimableBytes)}
                </span>
              </div>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No storage data.</p>
        )}
      </div>

      <Separator />

      <div>
        <SectionHeader title="Run history" />
        <div className="flex justify-between text-xs mb-2">
          <span className="text-muted-foreground">Total runs</span>
          <span className="font-mono">{runs.length}</span>
        </div>
        {lastRun ? (
          <div className="flex items-center justify-between text-xs">
            <span className="text-muted-foreground">Last run</span>
            <Badge variant={runStatusVariant(lastRun.status)}>{lastRun.status}</Badge>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">No runs yet.</p>
        )}
      </div>
    </div>
  );
}
