import * as React from "react";
import type { Checkpoint } from "@/types/run";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";

interface CheckpointListProps {
  readonly checkpoints: ReadonlyArray<Checkpoint>;
  readonly onSelectCheckpoint: (checkpoint: Checkpoint) => void;
  readonly selectedCheckpointPath: string | null;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

export function CheckpointList({
  checkpoints,
  onSelectCheckpoint,
  selectedCheckpointPath,
}: CheckpointListProps): React.JSX.Element {
  if (checkpoints.length === 0) {
    return (
      <div className="py-6 text-center text-sm text-muted-foreground">No checkpoints yet.</div>
    );
  }

  const sorted = [...checkpoints].sort((a, b) => b.step - a.step);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Step</TableHead>
          <TableHead>Path</TableHead>
          <TableHead>Size</TableHead>
          <TableHead>Retained</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {sorted.map((checkpoint) => (
          <TableRow
            key={checkpoint.id}
            onClick={() => onSelectCheckpoint(checkpoint)}
            className={`cursor-pointer ${
              selectedCheckpointPath === checkpoint.path ? "bg-accent" : "hover:bg-muted/50"
            }`}
          >
            <TableCell className="font-mono text-xs">{checkpoint.step}</TableCell>
            <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-xs">
              {checkpoint.path}
            </TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {formatBytes(checkpoint.sizeBytes)}
            </TableCell>
            <TableCell>
              {checkpoint.isRetained ? (
                <Badge variant="secondary" className="text-xs">
                  Kept
                </Badge>
              ) : (
                <span className="text-xs text-muted-foreground">—</span>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
