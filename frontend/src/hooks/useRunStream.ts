import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { wsClient } from "@/ws/client";
import type {
  WebSocketEnvelope,
  MetricRecordedPayload,
  LogLinePayload,
  LogBatchPayload,
  ResourceUpdatePayload,
  CheckpointSavedPayload,
  ProgressUpdatePayload,
} from "@/types/websocket";
import type { MetricPoint } from "@/types/run";
import type { LogEntry, Checkpoint } from "@/types/run";

interface LiveMetrics {
  readonly byStep: ReadonlyArray<MetricPoint>;
}

interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly gpuUtilizationPct: number;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
}

interface RunStreamState {
  readonly isConnected: boolean;
  readonly liveLogs: ReadonlyArray<LogEntry>;
  readonly liveMetrics: LiveMetrics;
  readonly systemResources: SystemResources | null;
  readonly liveCheckpoints: ReadonlyArray<Checkpoint>;
  readonly progressPct: number | null;
  readonly currentStep: number | null;
  readonly totalSteps: number | null;
}

const MAX_LIVE_LOGS = 2000;

function processMetricPayload(
  prev: ReadonlyArray<MetricPoint>,
  payload: MetricRecordedPayload,
): ReadonlyArray<MetricPoint> {
  const newPoints: MetricPoint[] = Object.entries(payload.metrics).map(([name, value]) => ({
    id: `${payload.runId}-${payload.step}-${name}`,
    runId: payload.runId,
    step: payload.step,
    epoch: payload.epoch,
    metricName: name as MetricPoint["metricName"],
    metricValue: value,
    stageName: null,
    recordedAt: new Date().toISOString(),
  }));
  return [...prev, ...newPoints];
}

function processLogLine(entry: Omit<LogLinePayload, "runId">): LogEntry {
  return {
    severity: entry.severity,
    stage: entry.stage,
    message: entry.message,
    source: entry.source,
    timestamp: new Date().toISOString(),
  };
}

export function useRunStream({
  projectId,
  runId,
}: {
  projectId: string | null;
  runId: string | null;
}): RunStreamState {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = React.useState(false);
  const [liveLogs, setLiveLogs] = React.useState<ReadonlyArray<LogEntry>>([]);
  const [liveMetrics, setLiveMetrics] = React.useState<LiveMetrics>({ byStep: [] });
  const [systemResources, setSystemResources] = React.useState<SystemResources | null>(null);
  const [liveCheckpoints, setLiveCheckpoints] = React.useState<ReadonlyArray<Checkpoint>>([]);
  const [progressPct, setProgressPct] = React.useState<number | null>(null);
  const [currentStep, setCurrentStep] = React.useState<number | null>(null);
  const [totalSteps, setTotalSteps] = React.useState<number | null>(null);

  React.useEffect(() => {
    if (!projectId || !runId) return;

    wsClient.connect({
      projectId,
      channels: ["run_state", "metrics", "logs", "system"],
    });

    const removeConnectionListener = wsClient.onConnectionChange(({ isConnected: connected }) => {
      setIsConnected(connected);
    });

    const removeMessageListener = wsClient.onMessage((envelope: WebSocketEnvelope) => {
      if (envelope.runId && envelope.runId !== runId) return;

      if (envelope.channel === "metrics" && envelope.event === "metric_recorded") {
        const payload = envelope.payload as MetricRecordedPayload;
        setLiveMetrics((prev) => ({
          byStep: processMetricPayload(prev.byStep, payload),
        }));
      }

      if (envelope.channel === "logs") {
        if (envelope.event === "log_line") {
          const payload = envelope.payload as LogLinePayload;
          const entry = processLogLine(payload);
          setLiveLogs((prev) => {
            const next = [...prev, entry];
            return next.length > MAX_LIVE_LOGS ? next.slice(-MAX_LIVE_LOGS) : next;
          });
        } else if (envelope.event === "log_batch") {
          const payload = envelope.payload as LogBatchPayload;
          const entries = payload.lines.map(processLogLine);
          setLiveLogs((prev) => {
            const next = [...prev, ...entries];
            return next.length > MAX_LIVE_LOGS ? next.slice(-MAX_LIVE_LOGS) : next;
          });
        }
      }

      if (envelope.channel === "system") {
        if (envelope.event === "resource_update") {
          const payload = envelope.payload as ResourceUpdatePayload;
          setSystemResources({
            gpuMemoryUsedMb: payload.gpuMemoryUsedMb,
            gpuUtilizationPct: payload.gpuUtilizationPct,
            cpuPct: payload.cpuPct,
            ramUsedMb: payload.ramUsedMb,
          });
        }
        if (envelope.event === "checkpoint_saved") {
          const payload = envelope.payload as CheckpointSavedPayload;
          const checkpoint: Checkpoint = {
            id: `${payload.step}-${payload.path}`,
            runId: payload.runId,
            step: payload.step,
            path: payload.path,
            sizeBytes: payload.sizeBytes,
            isRetained: false,
            createdAt: new Date().toISOString(),
          };
          setLiveCheckpoints((prev) => [...prev, checkpoint]);
        }
      }

      if (envelope.channel === "run_state") {
        if (envelope.event === "progress_update") {
          const payload = envelope.payload as ProgressUpdatePayload;
          setProgressPct(payload.progressPct);
          setCurrentStep(payload.currentStep);
          setTotalSteps(payload.totalSteps);
        }

        const invalidatingEvents = new Set([
          "stage_entered",
          "stage_completed",
          "stage_failed",
          "run_completed",
          "run_failed",
          "run_cancelled",
          "run_paused",
        ]);

        if (invalidatingEvents.has(envelope.event)) {
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId],
          });
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId, "stages"],
          });
        }

        if (
          envelope.event === "run_completed" ||
          envelope.event === "run_failed" ||
          envelope.event === "run_cancelled"
        ) {
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs"],
          });
        }
      }
    });

    return () => {
      removeConnectionListener();
      removeMessageListener();
      wsClient.disconnect();
    };
  }, [projectId, runId, queryClient]);

  return {
    isConnected,
    liveLogs,
    liveMetrics,
    systemResources,
    liveCheckpoints,
    progressPct,
    currentStep,
    totalSteps,
  };
}
