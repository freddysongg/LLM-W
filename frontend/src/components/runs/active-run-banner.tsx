import * as React from "react";
import type { Run } from "@/types/run";
import type { ActiveRunStatus } from "@/components/shared/active-run-banner";
import { ActiveRunBanner as SharedActiveRunBanner } from "@/components/shared/active-run-banner";

interface ActiveRunBannerProps {
  readonly run: Run;
  readonly currentStep: number | null;
  readonly totalSteps: number | null;
  readonly progressPct: number | null;
  readonly isConnected: boolean;
  readonly configLabel?: string;
  readonly lastLoss?: number | null;
  readonly learningRate?: number | null;
  readonly onPause?: () => void;
  readonly onResume?: () => void;
  readonly onStop?: () => void;
}

const DEFAULT_LOSS_FALLBACK = 0;
const DEFAULT_LR_FALLBACK = 0;

function resolveStatus(status: Run["status"]): ActiveRunStatus {
  if (status === "paused") return "paused";
  return "running";
}

function environmentLabel(run: Run): string {
  if (!run.environment || run.environment === "local") return "local";
  return run.modalGpuType ? `modal · ${run.modalGpuType}` : "modal";
}

function computeEtaSeconds({
  startedAt,
  percent,
}: {
  readonly startedAt: string | null;
  readonly percent: number;
}): number {
  if (!startedAt || percent <= 0) return 0;
  const elapsedMs = Date.now() - new Date(startedAt).getTime();
  if (elapsedMs <= 0) return 0;
  const projectedTotalMs = elapsedMs / (percent / 100);
  return Math.max(0, Math.round((projectedTotalMs - elapsedMs) / 1000));
}

export function ActiveRunBanner({
  run,
  currentStep,
  totalSteps,
  progressPct,
  isConnected,
  configLabel = "streaming",
  lastLoss,
  learningRate,
  onPause,
  onResume,
  onStop,
}: ActiveRunBannerProps): React.JSX.Element {
  const status = resolveStatus(run.status);
  const displayPct = progressPct ?? run.progressPct;
  const step = currentStep ?? run.currentStep;
  const total = totalSteps ?? run.totalSteps ?? Math.max(step, 1);
  const etaSeconds = computeEtaSeconds({ startedAt: run.startedAt, percent: displayPct });
  const connectionSuffix = isConnected ? "ws connected" : "ws reconnecting";
  const runName = `run ${run.id.slice(0, 6)}`;

  return (
    <SharedActiveRunBanner
      runName={runName}
      configLabel={`${configLabel} · ${connectionSuffix}`}
      runId={run.id}
      env={environmentLabel(run)}
      status={status}
      step={step}
      stepTotal={total}
      loss={lastLoss ?? DEFAULT_LOSS_FALLBACK}
      lr={learningRate ?? DEFAULT_LR_FALLBACK}
      etaSeconds={etaSeconds}
      onPause={onPause}
      onResume={onResume}
      onStop={onStop}
    />
  );
}
