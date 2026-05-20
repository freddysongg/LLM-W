import { create } from "zustand";
import type { LogEntry, MetricPoint, Checkpoint } from "@/types/run";
import type { FallbackProposedPayload } from "@/types/websocket";

interface SystemResources {
  readonly gpuMemoryUsedMb: number;
  readonly vramTotalMb: number | null;
  readonly cpuPct: number;
  readonly ramUsedMb: number;
  readonly ramTotalMb: number;
}

interface RunStreamData {
  readonly liveLogs: ReadonlyArray<LogEntry>;
  readonly liveMetrics: ReadonlyArray<MetricPoint>;
  readonly liveCheckpoints: ReadonlyArray<Checkpoint>;
  readonly progressPct: number | null;
  readonly currentStep: number | null;
  readonly totalSteps: number | null;
}

const MAX_LIVE_LOGS = 2000;
const MAX_LIVE_METRICS = 5000;

const EMPTY_RUN_DATA: RunStreamData = {
  liveLogs: [],
  liveMetrics: [],
  liveCheckpoints: [],
  progressPct: null,
  currentStep: null,
  totalSteps: null,
};

interface RunStreamStoreState {
  readonly runData: Readonly<Record<string, RunStreamData>>;
  readonly systemResources: SystemResources | null;
  readonly fallbackProposals: Readonly<Record<string, FallbackProposedPayload>>;
}

interface RunStreamStoreActions {
  appendLogs: (runId: string, entries: ReadonlyArray<LogEntry>) => void;
  appendMetricPoints: (runId: string, points: ReadonlyArray<MetricPoint>) => void;
  appendCheckpoint: (runId: string, checkpoint: Checkpoint) => void;
  setProgress: (
    runId: string,
    progressPct: number,
    currentStep: number,
    totalSteps: number,
  ) => void;
  setSystemResources: (resources: SystemResources) => void;
  setFallbackProposal: (runId: string, proposal: FallbackProposedPayload) => void;
  clearFallbackProposal: (runId: string) => void;
}

type RunStreamStore = RunStreamStoreState & RunStreamStoreActions;

function getOrEmpty(
  runData: Readonly<Record<string, RunStreamData>>,
  runId: string,
): RunStreamData {
  return runData[runId] ?? EMPTY_RUN_DATA;
}

export const useRunStreamStore = create<RunStreamStore>()((set) => ({
  runData: {},
  systemResources: null,
  fallbackProposals: {},

  appendLogs: (runId, entries) =>
    set((state) => {
      const existing = getOrEmpty(state.runData, runId);
      const combined = [...existing.liveLogs, ...entries];
      const trimmed = combined.length > MAX_LIVE_LOGS ? combined.slice(-MAX_LIVE_LOGS) : combined;
      return {
        runData: {
          ...state.runData,
          [runId]: { ...existing, liveLogs: trimmed },
        },
      };
    }),

  appendMetricPoints: (runId, points) =>
    set((state) => {
      const existing = getOrEmpty(state.runData, runId);
      const combined = [...existing.liveMetrics, ...points];
      const trimmed =
        combined.length > MAX_LIVE_METRICS ? combined.slice(-MAX_LIVE_METRICS) : combined;
      return {
        runData: {
          ...state.runData,
          [runId]: { ...existing, liveMetrics: trimmed },
        },
      };
    }),

  appendCheckpoint: (runId, checkpoint) =>
    set((state) => {
      const existing = getOrEmpty(state.runData, runId);
      return {
        runData: {
          ...state.runData,
          [runId]: {
            ...existing,
            liveCheckpoints: [...existing.liveCheckpoints, checkpoint],
          },
        },
      };
    }),

  setProgress: (runId, progressPct, currentStep, totalSteps) =>
    set((state) => {
      const existing = getOrEmpty(state.runData, runId);
      return {
        runData: {
          ...state.runData,
          [runId]: { ...existing, progressPct, currentStep, totalSteps },
        },
      };
    }),

  setSystemResources: (resources) => set({ systemResources: resources }),

  setFallbackProposal: (runId, proposal) =>
    set((state) => ({
      fallbackProposals: { ...state.fallbackProposals, [runId]: proposal },
    })),

  clearFallbackProposal: (runId) =>
    set((state) => {
      if (!(runId in state.fallbackProposals)) return {};
      const next = { ...state.fallbackProposals };
      delete next[runId];
      return { fallbackProposals: next };
    }),
}));
