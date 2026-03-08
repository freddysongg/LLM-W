import * as React from "react";
import type { Artifact } from "@/types/artifact";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { getArtifactDownloadUrl } from "@/api/artifacts";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

interface MetaRowProps {
  readonly label: string;
  readonly value: React.ReactNode;
}

function MetaRow({ label, value }: MetaRowProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-sm font-medium break-all">{value}</span>
    </div>
  );
}

interface ArtifactDetailDrawerProps {
  readonly artifact: Artifact | null;
  readonly projectId: string;
  readonly onClose: () => void;
}

export function ArtifactDetailDrawer({
  artifact,
  projectId,
  onClose,
}: ArtifactDetailDrawerProps): React.JSX.Element {
  return (
    <Dialog open={artifact !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-lg">
        {artifact && (
          <>
            <DialogHeader>
              <DialogTitle className="text-base">Artifact Detail</DialogTitle>
            </DialogHeader>

            <div className="space-y-3 mt-2">
              <MetaRow
                label="ID"
                value={<span className="font-mono text-xs">{artifact.id}</span>}
              />
              <MetaRow
                label="Type"
                value={
                  <Badge variant="outline" className="text-xs font-mono">
                    {artifact.artifactType.replace(/_/g, " ")}
                  </Badge>
                }
              />
              <MetaRow
                label="Run"
                value={<span className="font-mono text-xs">{artifact.runId}</span>}
              />
              <MetaRow label="File path" value={artifact.filePath} />
              <MetaRow label="Size" value={formatBytes(artifact.fileSizeBytes)} />
              <MetaRow label="Created" value={new Date(artifact.createdAt).toLocaleString()} />
              <MetaRow
                label="Retention"
                value={
                  artifact.isRetained ? (
                    <Badge variant="secondary" className="text-xs">
                      retained
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-xs text-muted-foreground">
                      purgeable
                    </Badge>
                  )
                }
              />

              {artifact.metadata && (
                <>
                  <Separator />
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-muted-foreground">Metadata</span>
                    <pre className="text-xs bg-muted rounded p-2 overflow-auto max-h-40">
                      {JSON.stringify(artifact.metadata, null, 2)}
                    </pre>
                  </div>
                </>
              )}

              <Separator />

              <Button asChild className="w-full">
                <a href={getArtifactDownloadUrl({ projectId, artifactId: artifact.id })} download>
                  Download
                </a>
              </Button>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
