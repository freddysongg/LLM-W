import * as React from "react";
import type { Run } from "@/types/run";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";

interface ActiveRunBannerProps {
  readonly run: Run;
  readonly currentStep: number | null;
  readonly totalSteps: number | null;
  readonly progressPct: number | null;
  readonly isConnected: boolean;
}

export function ActiveRunBanner({
  run,
  currentStep,
  totalSteps,
  progressPct,
  isConnected,
}: ActiveRunBannerProps): React.JSX.Element {
  const displayPct = progressPct ?? run.progressPct;
  const displayStep = currentStep ?? run.currentStep;
  const displayTotal = totalSteps ?? run.totalSteps;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-sm font-medium">Active Run</span>
          <span className="font-mono text-xs text-muted-foreground">{run.id.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          {!isConnected && (
            <Badge variant="outline" className="text-xs text-yellow-600 border-yellow-400">
              Reconnecting…
            </Badge>
          )}
          {run.currentStage && (
            <Badge variant="secondary" className="text-xs">
              {run.currentStage.replace(/_/g, " ")}
            </Badge>
          )}
        </div>
      </div>

      <div className="space-y-1">
        <Progress value={displayPct} className="h-2" />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>{Math.round(displayPct)}%</span>
          {displayTotal !== null && (
            <span>
              step {displayStep} / {displayTotal}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
