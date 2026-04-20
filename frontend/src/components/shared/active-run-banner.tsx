import * as React from "react";
import { MoreHorizontal, Pause, Play, Square, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export type ActiveRunStatus = "running" | "paused";

export interface ActiveRunBannerProps {
  readonly runName: string;
  readonly configLabel: string;
  readonly runId: string;
  readonly env: string;
  readonly status: ActiveRunStatus;
  readonly step: number;
  readonly stepTotal: number;
  readonly loss: number;
  readonly lr: number;
  readonly etaSeconds: number;
  readonly onPause?: () => void;
  readonly onResume?: () => void;
  readonly onStop?: () => void;
  readonly onMore?: () => void;
  readonly className?: string;
}

function formatInteger(value: number): string {
  return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatLoss(value: number): string {
  return value.toFixed(4);
}

function formatLearningRate(value: number): string {
  return value.toExponential(2);
}

function formatEta({
  seconds,
  status,
}: {
  readonly seconds: number;
  readonly status: ActiveRunStatus;
}): string {
  if (status === "paused") return "paused";
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const remainder = totalSeconds % 60;
  if (hours > 0) return `${hours}h ${minutes.toString().padStart(2, "0")}m`;
  if (minutes > 0) return `${minutes}m ${remainder.toString().padStart(2, "0")}s`;
  return `${remainder}s`;
}

interface MetricBlockProps {
  readonly label: string;
  readonly value: React.ReactNode;
}

function MetricBlock({ label, value }: MetricBlockProps): React.JSX.Element {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">{label}</span>
      <span className="font-mono text-[13px] font-semibold text-ink-1">{value}</span>
    </div>
  );
}

export function ActiveRunBanner({
  runName,
  configLabel,
  runId,
  env,
  status,
  step,
  stepTotal,
  loss,
  lr,
  etaSeconds,
  onPause,
  onResume,
  onStop,
  onMore,
  className,
}: ActiveRunBannerProps): React.JSX.Element {
  const isPaused = status === "paused";
  const progressPercent = stepTotal > 0 ? Math.min(100, Math.max(0, (step / stepTotal) * 100)) : 0;

  const handlePrimary = (): void => {
    if (isPaused) {
      onResume?.();
    } else {
      onPause?.();
    }
  };

  return (
    <div
      role="region"
      aria-label={`Active run ${runName}`}
      className={cn(
        "iris-glow relative grid grid-cols-[auto_1fr_auto] items-center gap-5 rounded-lg border border-hairline bg-surface p-5",
        "overflow-hidden",
        className,
      )}
    >
      <div
        aria-hidden="true"
        className="grid size-11 place-items-center rounded-md bg-ink-1 text-[color:var(--canvas)]"
      >
        <Zap className="size-[18px]" aria-hidden="true" />
      </div>

      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="truncate text-[14px] font-semibold leading-none text-ink-1">
            {runName}
          </span>
          <span className="font-mono text-[11px] text-ink-3">· {configLabel}</span>
          <Badge variant={isPaused ? "warn" : "running"}>{isPaused ? "paused" : "streaming"}</Badge>
        </div>
        <div className="font-mono text-[11px] text-ink-3">
          {runId} · {env} · eta {formatEta({ seconds: etaSeconds, status })}
        </div>
        <div className="mt-1 grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
          <MetricBlock
            label="step"
            value={
              <>
                {formatInteger(step)}
                <span className="text-ink-3">/{formatInteger(stepTotal)}</span>
              </>
            }
          />
          <MetricBlock label="loss" value={formatLoss(loss)} />
          <MetricBlock label="lr" value={formatLearningRate(lr)} />
          <MetricBlock label="eta" value={formatEta({ seconds: etaSeconds, status })} />
        </div>
        <Progress value={progressPercent} striped={!isPaused} paused={isPaused} className="mt-1" />
      </div>

      <div className="flex items-center gap-1.5">
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={handlePrimary}
          disabled={isPaused ? onResume === undefined : onPause === undefined}
        >
          {isPaused ? (
            <>
              <Play className="size-3" aria-hidden="true" />
              Resume
            </>
          ) : (
            <>
              <Pause className="size-3" aria-hidden="true" />
              Pause
            </>
          )}
        </Button>
        <Button
          type="button"
          size="sm"
          variant="ghost"
          onClick={onStop}
          disabled={onStop === undefined}
          className="text-[color:var(--danger)] hover:text-[color:var(--danger)]"
        >
          <Square className="size-3" aria-hidden="true" />
          Stop
        </Button>
        <Button
          type="button"
          size="icon"
          variant="ghost"
          onClick={onMore}
          disabled={onMore === undefined}
          aria-label="More actions"
        >
          <MoreHorizontal className="size-4" aria-hidden="true" />
        </Button>
      </div>
    </div>
  );
}
