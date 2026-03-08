import * as React from "react";
import { useProjectStorage, useCleanupStorage } from "@/hooks/useStorage";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

interface StoragePanelProps {
  readonly projectId: string;
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
          <CardTitle className="text-sm">Storage</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Loading…</CardContent>
      </Card>
    );
  }

  if (!storage) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Storage</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">Unavailable.</CardContent>
      </Card>
    );
  }

  const { totalBytes, breakdown, retentionPolicy } = storage;
  const categories = Object.entries(breakdown);
  const maxBytes = Math.max(...categories.map(([, d]) => d.bytes), 1);

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm">Storage</CardTitle>
          <span className="text-sm font-medium">{formatBytes(totalBytes)}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {categories.map(([category, detail]) => (
          <div key={category} className="space-y-1">
            <div className="flex justify-between text-xs">
              <span className="capitalize text-muted-foreground">{category}</span>
              <span className="font-medium">{formatBytes(detail.bytes)}</span>
            </div>
            <Progress value={Math.round((detail.bytes / maxBytes) * 100)} />
          </div>
        ))}

        {retentionPolicy.reclaimableBytes > 0 && (
          <div className="flex items-center justify-between pt-1 border-t">
            <span className="text-xs text-muted-foreground">
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
        )}
      </CardContent>
    </Card>
  );
}
