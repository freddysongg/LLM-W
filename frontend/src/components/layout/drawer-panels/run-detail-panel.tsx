import * as React from "react";
import { useRun, useRunStages, useRunMetrics } from "@/hooks/useRuns";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { RunTimeline } from "@/components/runs/run-timeline";
import type { RunStatus } from "@/types/run";

interface RunDetailPanelProps {
  readonly projectId: string;
  readonly runId: string;
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

function elapsedLabel(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt) return "—";
  const start = new Date(startedAt).getTime();
  const end = completedAt ? new Date(completedAt).getTime() : Date.now();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function MetricRow({
  label,
  value,
}: {
  readonly label: string;
  readonly value: string;
}): React.JSX.Element {
  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="text-xs font-mono">{value}</span>
    </div>
  );
}

export function RunDetailPanel({ projectId, runId }: RunDetailPanelProps): React.JSX.Element {
  const { data: run, isLoading: isRunLoading } = useRun({ projectId, runId });
  const { data: stages = [] } = useRunStages({ projectId, runId });
  const { data: metrics = [] } = useRunMetrics({ projectId, runId });
  const [selectedStageId, setSelectedStageId] = React.useState<string | null>(null);

  if (isRunLoading) {
    return <p className="text-sm text-muted-foreground p-4">Loading…</p>;
  }

  if (!run) {
    return <p className="text-sm text-muted-foreground p-4">Run not found.</p>;
  }

  const {
    status,
    currentStage,
    currentStep,
    totalSteps,
    progressPct,
    startedAt,
    completedAt,
    failureReason,
    failureStage,
    configVersionId,
  } = run;

  const lastTrainLoss = metrics
    .filter((m) => m.metricName === "train_loss")
    .sort((a, b) => b.step - a.step)[0];

  const lastEvalLoss = metrics
    .filter((m) => m.metricName === "eval_loss")
    .sort((a, b) => b.step - a.step)[0];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant={runStatusVariant(status)}>{status}</Badge>
        {currentStage && (
          <span className="text-xs text-muted-foreground">{currentStage.replace(/_/g, " ")}</span>
        )}
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Progress</span>
          <span>{totalSteps ? `${currentStep} / ${totalSteps}` : `step ${currentStep}`}</span>
        </div>
        <Progress value={progressPct} className="h-1.5" />
      </div>

      <MetricRow label="Elapsed" value={elapsedLabel(startedAt, completedAt)} />
      <MetricRow label="Config version" value={configVersionId.slice(0, 8)} />

      {lastTrainLoss && (
        <MetricRow label="Train loss" value={lastTrainLoss.metricValue.toFixed(4)} />
      )}
      {lastEvalLoss && <MetricRow label="Eval loss" value={lastEvalLoss.metricValue.toFixed(4)} />}

      {status === "failed" && failureReason && (
        <>
          <Separator />
          <div className="space-y-1">
            <p className="text-xs font-semibold text-destructive uppercase tracking-wider">
              Failure
            </p>
            {failureStage && (
              <p className="text-xs text-muted-foreground">
                Stage: {failureStage.replace(/_/g, " ")}
              </p>
            )}
            <p className="text-xs text-destructive/90 break-words">{failureReason}</p>
          </div>
        </>
      )}

      <Separator />

      <div>
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
          Stages
        </p>
        <RunTimeline
          stages={stages}
          selectedStageId={selectedStageId}
          onSelectStage={setSelectedStageId}
        />
      </div>
    </div>
  );
}
