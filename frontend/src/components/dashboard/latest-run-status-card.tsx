import * as React from "react";
import type { Run } from "@/types/run";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

interface LatestRunStatusCardProps {
  readonly run: Run | null;
}

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function runStatusVariant(status: Run["status"]): BadgeVariant {
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

function formatElapsed(startedAt: string): string {
  const elapsed = Date.now() - new Date(startedAt).getTime();
  const seconds = Math.floor(elapsed / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  if (hours > 0) return `${hours}h ${minutes % 60}m`;
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
  return `${seconds}s`;
}

export function LatestRunStatusCard({ run }: LatestRunStatusCardProps): React.JSX.Element {
  if (!run) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Latest Run</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">No runs yet.</CardContent>
      </Card>
    );
  }

  const { id, status, currentStage, progressPct, startedAt } = run;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Latest Run</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground truncate">{id}</span>
          <Badge variant={runStatusVariant(status)}>{status}</Badge>
        </div>
        {currentStage && (
          <div className="text-xs text-muted-foreground">
            Stage: {currentStage.replace(/_/g, " ")}
          </div>
        )}
        <Progress value={progressPct} />
        {startedAt && (
          <div className="text-xs text-muted-foreground">Elapsed: {formatElapsed(startedAt)}</div>
        )}
      </CardContent>
    </Card>
  );
}
