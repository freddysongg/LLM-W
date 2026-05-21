import * as React from "react";
import { useProjectStorage, useCleanupStorage } from "@/hooks/useStorage";
import type { StorageCategoryDetail } from "@/types/project";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

interface StoragePanelProps {
  readonly projectId: string;
}

const DISPLAY_CATEGORIES: ReadonlyArray<{
  readonly key: "checkpoints" | "logs" | "exports";
  readonly label: string;
}> = [
  { key: "checkpoints", label: "Checkpoints" },
  { key: "logs", label: "Logs" },
  { key: "exports", label: "Exports" },
];

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

interface BreakdownRowProps {
  readonly label: string;
  readonly detail: StorageCategoryDetail;
}

function BreakdownRow({ label, detail }: BreakdownRowProps): React.JSX.Element {
  const { bytes, fileCount } = detail;
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">{label}</span>
      <span className="font-mono text-[14px] text-ink-1">{formatBytes(bytes)}</span>
      <span className="font-mono text-[10px] text-ink-4">
        {fileCount} file{fileCount === 1 ? "" : "s"}
      </span>
    </div>
  );
}

export function StoragePanel({ projectId }: StoragePanelProps): React.JSX.Element {
  const { data: storage, isLoading } = useProjectStorage({ projectId });
  const cleanupMutation = useCleanupStorage();

  const handleCleanup = (): void => {
    cleanupMutation.mutate({ projectId });
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Storage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-[11px] text-ink-3">Loading…</div>
        </CardContent>
      </Card>
    );
  }

  if (!storage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Storage</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="font-mono text-[11px] text-ink-3">Unavailable.</div>
        </CardContent>
      </Card>
    );
  }

  const { totalBytes, quotaBytes, breakdown, retentionPolicy } = storage;
  const usagePct = Math.min(100, (totalBytes / quotaBytes) * 100);
  const canCleanup = retentionPolicy.reclaimableBytes > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Storage</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
          {formatBytes(totalBytes)} / {formatBytes(quotaBytes)}
        </span>
      </CardHeader>
      <CardContent className="space-y-4">
        <Progress value={usagePct} />
        <div className="grid grid-cols-3 gap-3">
          {DISPLAY_CATEGORIES.map(({ key, label }) => (
            <BreakdownRow key={key} label={label} detail={breakdown[key]} />
          ))}
        </div>
        {canCleanup ? (
          <div className="flex items-center justify-between border-t border-hairline pt-3">
            <span className="font-mono text-[11px] text-ink-3">
              {formatBytes(retentionPolicy.reclaimableBytes)} reclaimable
            </span>
            <Button
              size="sm"
              variant="outline"
              onClick={handleCleanup}
              disabled={cleanupMutation.isPending}
            >
              {cleanupMutation.isPending ? "Cleaning…" : "Clean up"}
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
