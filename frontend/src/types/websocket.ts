import type { MetricName, RunStatus, StageName } from "./run";
import type { ArtifactType } from "./artifact";

export type WebSocketChannel = "run_state" | "metrics" | "logs" | "system";
export type LogSeverity = "debug" | "info" | "warning" | "error" | "critical";

export interface WebSocketEnvelope<T = unknown> {
  readonly channel: WebSocketChannel;
  readonly event: string;
  readonly runId: string;
  readonly timestamp: string;
  readonly payload: T;
}

export interface RunCreatedPayload {
  readonly runId: string;
  readonly configVersionId: string;
  readonly status: RunStatus;
}

export interface StageEnteredPayload {
  readonly runId: string;
  readonly stageName: StageName;
  readonly stageOrder: number;
}

export interface StageCompletedPayload {
  readonly runId: string;
  readonly stageName: StageName;
  readonly durationMs: number;
  readonly outputSummary: string | null;
}

export interface StageFailedPayload {
  readonly runId: string;
  readonly stageName: StageName;
  readonly errorMessage: string;
}

export interface ProgressUpdatePayload {
  readonly runId: string;
  readonly currentStep: number;
  readonly totalSteps: number;
  readonly progressPct: number;
  readonly epoch: number;
}

export interface RunCompletedPayload {
  readonly runId: string;
  readonly totalDurationMs: number;
  readonly finalMetrics: Record<MetricName, number>;
}

export interface RunFailedPayload {
  readonly runId: string;
  readonly failureReason: string;
  readonly failureStage: StageName;
  readonly lastStep: number;
}

export interface RunCancelledPayload {
  readonly runId: string;
}

export interface RunPausedPayload {
  readonly runId: string;
  readonly pausedAtStep: number;
}

export interface MetricRecordedPayload {
  readonly runId: string;
  readonly step: number;
  readonly epoch: number;
  readonly metrics: Record<string, number>;
}

export interface LogLinePayload {
  readonly runId: string;
  readonly severity: LogSeverity;
  readonly stage: StageName | null;
  readonly message: string;
  readonly source: string;
}

export interface LogBatchPayload {
  readonly runId: string;
  readonly lines: ReadonlyArray<Omit<LogLinePayload, "runId">>;
}

export interface ResourceUpdatePayload {
  readonly gpuMemoryUsedMb: number;
  readonly gpuUtilizationPct: number;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
}

export interface CheckpointSavedPayload {
  readonly runId: string;
  readonly step: number;
  readonly path: string;
  readonly sizeBytes: number;
}

export interface ArtifactCreatedPayload {
  readonly runId: string;
  readonly artifactType: ArtifactType;
  readonly path: string;
}

export type ClientMessageType = "subscribe" | "unsubscribe" | "ping";

export interface SubscribeMessage {
  readonly type: "subscribe";
  readonly payload: { readonly channels: ReadonlyArray<WebSocketChannel> };
}

export interface UnsubscribeMessage {
  readonly type: "unsubscribe";
  readonly payload: { readonly channels: ReadonlyArray<WebSocketChannel> };
}

export interface PingMessage {
  readonly type: "ping";
  readonly payload: Record<string, never>;
}

export type ClientMessage = SubscribeMessage | UnsubscribeMessage | PingMessage;
