import * as React from "react";
import { useNavigate } from "react-router-dom";
import type { Run } from "@/types/run";
import type { ActiveRunStatus } from "@/components/shared/active-run-banner";
import { ActiveRunBanner } from "@/components/shared/active-run-banner";

interface LatestRunStatusCardProps {
  readonly run: Run | null;
  readonly configLabel?: string;
  readonly currentStep?: number | null;
  readonly totalSteps?: number | null;
  readonly progressPct?: number | null;
  readonly loss?: number | null;
  readonly learningRate?: number | null;
  readonly etaSeconds?: number | null;
  readonly onPause?: () => void;
  readonly onResume?: () => void;
  readonly onStop?: () => void;
}

const DEFAULT_LOSS_FALLBACK = 0;
const DEFAULT_LR_FALLBACK = 0;
const DEFAULT_ETA_FALLBACK = 0;

function resolveStatus(status: Run["status"]): ActiveRunStatus | null {
  if (status === "running" || status === "pending") return "running";
  if (status === "paused") return "paused";
  return null;
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
  const remainingMs = Math.max(0, projectedTotalMs - elapsedMs);
  return Math.round(remainingMs / 1000);
}

export function LatestRunStatusCard({
  run,
  configLabel = "active config",
  currentStep,
  totalSteps,
  progressPct,
  loss,
  learningRate,
  etaSeconds,
  onPause,
  onResume,
  onStop,
}: LatestRunStatusCardProps): React.JSX.Element | null {
  const navigate = useNavigate();

  if (!run) return null;
  const status = resolveStatus(run.status);
  if (!status) return null;

  const runName = `run ${run.id.slice(0, 6)}`;
  const step = currentStep ?? run.currentStep;
  const total = totalSteps ?? run.totalSteps ?? Math.max(step, 1);
  const percent = progressPct ?? run.progressPct;
  const resolvedEta = etaSeconds ?? computeEtaSeconds({ startedAt: run.startedAt, percent });

  const handleMore = (): void => {
    void navigate(`/runs`);
  };

  return (
    <ActiveRunBanner
      runName={runName}
      configLabel={configLabel}
      runId={run.id}
      env={environmentLabel(run)}
      status={status}
      step={step}
      stepTotal={total}
      loss={loss ?? DEFAULT_LOSS_FALLBACK}
      lr={learningRate ?? DEFAULT_LR_FALLBACK}
      etaSeconds={resolvedEta ?? DEFAULT_ETA_FALLBACK}
      onPause={onPause}
      onResume={onResume}
      onStop={onStop}
      onMore={handleMore}
    />
  );
}
