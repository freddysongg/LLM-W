import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { wsClient } from "@/ws/client";
import { useRunStreamStore } from "@/stores/run-stream-store";
import { toast } from "@/hooks/use-toast";
import type {
  WebSocketEnvelope,
  MetricRecordedPayload,
  LogLinePayload,
  LogBatchPayload,
  ResourceUpdatePayload,
  CheckpointSavedPayload,
  ProgressUpdatePayload,
  RetentionAppliedPayload,
  FallbackProposedPayload,
  OomDetectedPayload,
  OomTrigger,
} from "@/types/websocket";
import type { MetricPoint, LogEntry, Checkpoint, ModalGpuType, DeviceType } from "@/types/run";
import type { ModalGpuOption } from "@/types/catalog";

interface RawFallbackCandidate {
  readonly gpu_type: string;
  readonly label: string;
  readonly vram_gb: number;
  readonly rate_usd_hr: number;
}

interface RawFallbackProposedPayload {
  readonly run_id: string;
  readonly attempt_index: number;
  readonly from_gpu: string;
  readonly candidates: ReadonlyArray<RawFallbackCandidate>;
  readonly detected_via: OomTrigger;
  readonly preserved_volume: boolean;
}

interface RawOomDetectedPayload {
  readonly run_id: string;
  readonly device: string;
  readonly exit_code: number;
  readonly detected_via: OomTrigger;
}

function normalizeFallbackCandidate(raw: RawFallbackCandidate): ModalGpuOption {
  return {
    gpuType: raw.gpu_type as ModalGpuType,
    label: raw.label,
    vramGb: raw.vram_gb,
    rateUsdHr: raw.rate_usd_hr,
  };
}

function normalizeFallbackProposed(raw: RawFallbackProposedPayload): FallbackProposedPayload {
  return {
    runId: raw.run_id,
    attemptIndex: raw.attempt_index,
    fromGpu: raw.from_gpu as ModalGpuType,
    candidates: raw.candidates.map(normalizeFallbackCandidate),
    detectedVia: raw.detected_via,
    preservedVolume: raw.preserved_volume,
  };
}

function normalizeOomDetected(raw: RawOomDetectedPayload): OomDetectedPayload {
  return {
    runId: raw.run_id,
    device: raw.device as DeviceType,
    exitCode: raw.exit_code,
    detectedVia: raw.detected_via,
  };
}

export interface RunStreamState {
  readonly isConnected: boolean;
  readonly liveLogs: ReadonlyArray<LogEntry>;
  readonly liveMetrics: ReadonlyArray<MetricPoint>;
  readonly systemResources: {
    readonly gpuMemoryUsedMb: number;
    readonly vramTotalMb: number | null;
    readonly cpuPct: number;
    readonly ramUsedMb: number;
    readonly ramTotalMb: number;
  } | null;
  readonly liveCheckpoints: ReadonlyArray<Checkpoint>;
  readonly progressPct: number | null;
  readonly currentStep: number | null;
  readonly totalSteps: number | null;
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

function buildMetricPoints(payload: MetricRecordedPayload): ReadonlyArray<MetricPoint> {
  return Object.entries(payload.metrics).map(([name, value]) => ({
    id: `${payload.runId}-${payload.step}-${name}`,
    runId: payload.runId,
    step: payload.step,
    epoch: payload.epoch,
    metricName: name as MetricPoint["metricName"],
    metricValue: value,
    stageName: null,
    recordedAt: new Date().toISOString(),
  }));
}

export function useRunStream({
  projectId,
  runId,
}: {
  projectId: string | null;
  runId: string | null;
}): RunStreamState {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = React.useState(wsClient.isConnected);

  const {
    appendLogs,
    appendMetricPoints,
    appendCheckpoint,
    setProgress,
    setSystemResources,
    setFallbackProposal,
    runData,
    systemResources,
  } = useRunStreamStore((state) => ({
    appendLogs: state.appendLogs,
    appendMetricPoints: state.appendMetricPoints,
    appendCheckpoint: state.appendCheckpoint,
    setProgress: state.setProgress,
    setSystemResources: state.setSystemResources,
    setFallbackProposal: state.setFallbackProposal,
    runData: runId ? (state.runData[runId] ?? null) : null,
    systemResources: state.systemResources,
  }));

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
        appendMetricPoints(runId, buildMetricPoints(payload));
      }

      if (envelope.channel === "logs") {
        if (envelope.event === "log_line") {
          const payload = envelope.payload as LogLinePayload;
          appendLogs(runId, [processLogLine(payload)]);
        } else if (envelope.event === "log_batch") {
          const payload = envelope.payload as LogBatchPayload;
          appendLogs(runId, payload.lines.map(processLogLine));
        }
      }

      if (envelope.channel === "system") {
        if (envelope.event === "resource_update") {
          const payload = envelope.payload as ResourceUpdatePayload;
          setSystemResources({
            gpuMemoryUsedMb: payload.gpuMemoryUsedMb,
            vramTotalMb: payload.vramTotalMb,
            cpuPct: payload.cpuPct,
            ramUsedMb: payload.ramUsedMb,
            ramTotalMb: payload.ramTotalMb,
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
            isRetained: true,
            isBest: payload.isBestEval,
            createdAt: new Date().toISOString(),
          };
          appendCheckpoint(runId, checkpoint);
        }
        if (envelope.event === "retention_applied") {
          const payload = envelope.payload as RetentionAppliedPayload;
          if (payload.pruned.length > 0) {
            const count = payload.pruned.length;
            toast({
              title: "Retention policy applied",
              description: `Pruned ${count} checkpoint${count === 1 ? "" : "s"} per retention policy`,
            });
          }
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId, "checkpoints"],
          });
        }
        if (envelope.event === "model_profile_ready") {
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId, "model-profile"],
          });
        }
        if (envelope.event === "weight_stats_recorded") {
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId, "weight-snapshots"],
          });
        }
        if (envelope.event === "oom_detected") {
          const payload = normalizeOomDetected(envelope.payload as RawOomDetectedPayload);
          toast({
            title: "Out-of-memory detected",
            description: `Device ${payload.device} ran out of memory (detected via ${payload.detectedVia}).`,
            variant: "destructive",
          });
        }
      }

      if (envelope.channel === "run_state") {
        if (envelope.event === "progress_update") {
          const payload = envelope.payload as ProgressUpdatePayload;
          setProgress(runId, payload.progressPct, payload.currentStep, payload.totalSteps);
        }
        if (envelope.event === "fallback_proposed") {
          const payload = normalizeFallbackProposed(envelope.payload as RawFallbackProposedPayload);
          setFallbackProposal(runId, payload);
          void queryClient.invalidateQueries({
            queryKey: ["projects", projectId, "runs", runId],
          });
        }

        const invalidatingEvents = new Set([
          "stage_entered",
          "stage_completed",
          "stage_failed",
          "run_completed",
          "run_failed",
          "run_cancelled",
          "run_paused",
          "progress_update",
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
      // Do not disconnect — the WS connection is shared and must survive navigation.
    };
  }, [
    projectId,
    runId,
    queryClient,
    appendLogs,
    appendMetricPoints,
    appendCheckpoint,
    setProgress,
    setSystemResources,
    setFallbackProposal,
  ]);

  return {
    isConnected,
    liveLogs: runData?.liveLogs ?? [],
    liveMetrics: runData?.liveMetrics ?? [],
    systemResources,
    liveCheckpoints: runData?.liveCheckpoints ?? [],
    progressPct: runData?.progressPct ?? null,
    currentStep: runData?.currentStep ?? null,
    totalSteps: runData?.totalSteps ?? null,
  };
}
