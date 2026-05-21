import * as React from "react";
import { Copy, Play, Square } from "lucide-react";
import { useServingStatus, useStartServing, useStopServing } from "@/hooks/useServing";
import { useToast } from "@/hooks/use-toast";
import { Button } from "@/components/ui/button";
import { StatusDot, type RunStatus } from "@/components/shared/status-dot";
import { describeApiError } from "@/lib/api-error";
import type { ServingState, ServingStatus } from "@/types/serving";

interface ServingPanelProps {
  readonly projectId: string;
}

interface StateDisplay {
  readonly dot: RunStatus;
  readonly label: string;
}

const STATE_DISPLAY: Record<ServingState, StateDisplay> = {
  stopped: { dot: "pending", label: "Not serving" },
  starting: { dot: "paused", label: "Starting model load…" },
  running: { dot: "running", label: "Running" },
  failed: { dot: "failed", label: "Failed" },
  stopping: { dot: "paused", label: "Stopping…" },
};

function buildPortLabel(status: ServingStatus): string {
  if (!status.base_url) {
    return STATE_DISPLAY[status.state].label;
  }
  return `${STATE_DISPLAY[status.state].label} · ${status.base_url}`;
}

export function ServingStatusRow({ projectId }: ServingPanelProps): React.JSX.Element {
  const { data: status, isLoading } = useServingStatus({ projectId });

  if (isLoading || !status) {
    return (
      <span className="inline-flex items-center gap-2 text-ink-3">
        <StatusDot status="pending" />
        <span>—</span>
      </span>
    );
  }

  const { dot } = STATE_DISPLAY[status.state];
  return (
    <span className="inline-flex items-center gap-2">
      <StatusDot status={dot} />
      <span>{buildPortLabel(status)}</span>
      {status.last_error && status.state === "failed" && (
        <span
          className="ml-2 max-w-[280px] truncate font-mono text-[10px] text-danger"
          title={status.last_error}
        >
          {status.last_error}
        </span>
      )}
    </span>
  );
}

export function ServingActions({ projectId }: ServingPanelProps): React.JSX.Element {
  const { data: status } = useServingStatus({ projectId });
  const startMutation = useStartServing();
  const stopMutation = useStopServing();
  const { toast } = useToast();

  const state: ServingState = status?.state ?? "stopped";
  const isBusy = startMutation.isPending || stopMutation.isPending;

  const handleStart = (): void => {
    startMutation.mutate(
      { projectId, request: {} },
      {
        onError: (error) => {
          toast({
            title: "Could not start serving",
            description: describeApiError({ cause: error, fallback: "Serving startup failed." }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleStop = (): void => {
    stopMutation.mutate(
      { projectId },
      {
        onError: (error) => {
          toast({
            title: "Could not stop serving",
            description: describeApiError({ cause: error, fallback: "Stop request failed." }),
            variant: "destructive",
          });
        },
      },
    );
  };

  const handleCopyUrl = async (): Promise<void> => {
    if (!status?.base_url) return;
    try {
      await navigator.clipboard.writeText(status.base_url);
      toast({ title: "URL copied", description: status.base_url });
    } catch {
      toast({
        title: "Copy failed",
        description: "Clipboard access denied.",
        variant: "destructive",
      });
    }
  };

  if (state === "running") {
    return (
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={handleStop} disabled={isBusy}>
          <Square className="size-3" aria-hidden="true" />
          Stop
        </Button>
        <Button variant="outline" size="sm" onClick={handleCopyUrl} disabled={!status?.base_url}>
          <Copy className="size-3" aria-hidden="true" />
          Copy URL
        </Button>
      </div>
    );
  }

  if (state === "starting" || state === "stopping") {
    return (
      <Button variant="outline" size="sm" disabled>
        <Play className="size-3" aria-hidden="true" />
        {state === "starting" ? "Starting…" : "Stopping…"}
      </Button>
    );
  }

  const startLabel = state === "failed" ? "Restart" : "Start serving";
  return (
    <Button variant="outline" size="sm" onClick={handleStart} disabled={isBusy}>
      <Play className="size-3" aria-hidden="true" />
      {startLabel}
    </Button>
  );
}
