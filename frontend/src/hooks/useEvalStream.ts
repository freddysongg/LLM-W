import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { wsClient } from "@/ws/client";
import { EVAL_CHANNEL, parseEvalEnvelope } from "@/ws/eval-stream";
import { invalidateEvalRunQueries } from "@/hooks/useEval";
import type {
  EvalCaseCompletedPayload,
  EvalCostWarningPayload,
  EvalRunCompletedPayload,
} from "@/types/eval";

export interface EvalStreamState {
  readonly isConnected: boolean;
  readonly liveCaseEvents: ReadonlyArray<EvalCaseCompletedPayload>;
  readonly lastRunCompletion: EvalRunCompletedPayload | null;
  readonly lastCostWarning: EvalCostWarningPayload | null;
}

const EVAL_STREAM_CHANNELS = [EVAL_CHANNEL] as const;

export function useEvalStream({
  projectId,
  evalRunId,
}: {
  projectId: string | null;
  evalRunId: string | null;
}): EvalStreamState {
  const queryClient = useQueryClient();
  const [isConnected, setIsConnected] = React.useState<boolean>(wsClient.isConnected);
  const [liveCaseEvents, setLiveCaseEvents] = React.useState<
    ReadonlyArray<EvalCaseCompletedPayload>
  >([]);
  const [lastRunCompletion, setLastRunCompletion] = React.useState<EvalRunCompletedPayload | null>(
    null,
  );
  const [lastCostWarning, setLastCostWarning] = React.useState<EvalCostWarningPayload | null>(null);

  React.useEffect(() => {
    setLiveCaseEvents([]);
    setLastRunCompletion(null);
    setLastCostWarning(null);
  }, [evalRunId]);

  React.useEffect(() => {
    if (!projectId) return;

    wsClient.connect({ projectId, channels: EVAL_STREAM_CHANNELS });

    const removeConnectionListener = wsClient.onConnectionChange(({ isConnected: connected }) => {
      setIsConnected(connected);
    });

    const removeMessageListener = wsClient.onMessage((envelope) => {
      const parsed = parseEvalEnvelope(envelope);
      if (parsed === null) return;

      if (evalRunId !== null && parsed.payload.evalRunId !== evalRunId) return;

      switch (parsed.kind) {
        case "case_completed":
          setLiveCaseEvents((previous) => [...previous, parsed.payload]);
          invalidateEvalRunQueries({ queryClient, evalRunId: parsed.payload.evalRunId });
          break;
        case "run_completed":
          setLastRunCompletion(parsed.payload);
          invalidateEvalRunQueries({ queryClient, evalRunId: parsed.payload.evalRunId });
          break;
        case "cost_warning":
          setLastCostWarning(parsed.payload);
          break;
        default: {
          const exhaustive: never = parsed;
          return exhaustive;
        }
      }
    });

    return () => {
      removeConnectionListener();
      removeMessageListener();
    };
  }, [projectId, evalRunId, queryClient]);

  return {
    isConnected,
    liveCaseEvents,
    lastRunCompletion,
    lastCostWarning,
  };
}
