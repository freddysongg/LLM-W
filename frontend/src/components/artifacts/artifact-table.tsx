import * as React from "react";
import type { Artifact } from "@/types/artifact";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
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
import { getArtifactDownloadUrl } from "@/api/artifacts";

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface ArtifactTableProps {
  readonly artifacts: ReadonlyArray<Artifact>;
  readonly projectId: string;
  readonly selectedArtifactId: string | null;
  readonly isDeleting: boolean;
  readonly onSelect: (artifactId: string) => void;
  readonly onDelete: (artifactId: string) => void;
}

export function ArtifactTable({
  artifacts,
  projectId,
  selectedArtifactId,
  isDeleting,
  onSelect,
  onDelete,
}: ArtifactTableProps): React.JSX.Element {
  if (artifacts.length === 0) {
    return (
      <div className="py-12 text-center text-sm text-muted-foreground">
        No artifacts found for the selected filters.
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Type</TableHead>
          <TableHead>Run</TableHead>
          <TableHead>File</TableHead>
          <TableHead>Size</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Retained</TableHead>
          <TableHead className="w-24" />
        </TableRow>
      </TableHeader>
      <TableBody>
        {artifacts.map((artifact) => (
          <TableRow
            key={artifact.id}
            className={`cursor-pointer ${selectedArtifactId === artifact.id ? "bg-muted/50" : ""}`}
            onClick={() => onSelect(artifact.id)}
          >
            <TableCell>
              <Badge variant="outline" className="text-xs font-mono">
                {artifact.artifactType.replace(/_/g, " ")}
              </Badge>
            </TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground">
              {artifact.runId.slice(0, 8)}
            </TableCell>
            <TableCell
              className="font-mono text-xs max-w-xs truncate text-muted-foreground"
              title={artifact.filePath}
            >
              {artifact.filePath.split("/").at(-1) ?? artifact.filePath}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatBytes(artifact.fileSizeBytes)}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatDate(artifact.createdAt)}
            </TableCell>
            <TableCell>
              {artifact.isRetained ? (
                <Badge variant="secondary" className="text-xs">
                  kept
                </Badge>
              ) : (
                <Badge variant="outline" className="text-xs text-muted-foreground">
                  purgeable
                </Badge>
              )}
            </TableCell>
            <TableCell onClick={(e) => e.stopPropagation()}>
              <div className="flex items-center gap-1">
                <Button variant="ghost" size="sm" asChild>
                  <a
                    href={getArtifactDownloadUrl({ projectId, artifactId: artifact.id })}
                    download
                    aria-label={`Download ${artifact.filePath}`}
                  >
                    ↓
                  </a>
                </Button>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-destructive hover:text-destructive"
                      disabled={isDeleting}
                      aria-label={`Delete artifact ${artifact.id}`}
                    >
                      ✕
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Delete artifact?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will permanently delete{" "}
                        <span className="font-mono text-sm">{artifact.filePath}</span>. This action
                        cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => onDelete(artifact.id)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        Delete
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
