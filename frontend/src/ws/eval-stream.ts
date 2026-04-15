import type { WebSocketEnvelope } from "@/types/websocket";
import type {
  EvalCaseCompletedPayload,
  EvalCostWarningPayload,
  EvalEventName,
  EvalRunCompletedPayload,
} from "@/types/eval";

export const EVAL_CHANNEL = "eval" as const;
export const EVAL_EVENT_CASE_COMPLETED: EvalEventName = "case_completed";
export const EVAL_EVENT_RUN_COMPLETED: EvalEventName = "run_completed";
export const EVAL_EVENT_COST_WARNING: EvalEventName = "cost_warning";

export type EvalStreamEvent =
  | { readonly kind: "case_completed"; readonly payload: EvalCaseCompletedPayload }
  | { readonly kind: "run_completed"; readonly payload: EvalRunCompletedPayload }
  | { readonly kind: "cost_warning"; readonly payload: EvalCostWarningPayload };

function isEvalCaseCompletedPayload(candidate: unknown): candidate is EvalCaseCompletedPayload {
  if (typeof candidate !== "object" || candidate === null) return false;
  const record = candidate as Record<string, unknown>;
  return (
    typeof record.evalRunId === "string" &&
    typeof record.caseId === "string" &&
    typeof record.rubricVersionId === "string" &&
    typeof record.evalCallId === "string" &&
    (record.verdict === "pass" || record.verdict === "fail") &&
    typeof record.costUsd === "number"
  );
}

function isEvalRunCompletedPayload(candidate: unknown): candidate is EvalRunCompletedPayload {
  if (typeof candidate !== "object" || candidate === null) return false;
  const record = candidate as Record<string, unknown>;
  return typeof record.evalRunId === "string" && typeof record.totalCostUsd === "number";
}

function isEvalCostWarningPayload(candidate: unknown): candidate is EvalCostWarningPayload {
  if (typeof candidate !== "object" || candidate === null) return false;
  const record = candidate as Record<string, unknown>;
  return (
    typeof record.evalRunId === "string" &&
    typeof record.currentCostUsd === "number" &&
    typeof record.maxCostUsd === "number" &&
    typeof record.warningPct === "number"
  );
}

export function parseEvalEnvelope(envelope: WebSocketEnvelope): EvalStreamEvent | null {
  if (envelope.channel !== EVAL_CHANNEL) return null;

  if (
    envelope.event === EVAL_EVENT_CASE_COMPLETED &&
    isEvalCaseCompletedPayload(envelope.payload)
  ) {
    return { kind: "case_completed", payload: envelope.payload };
  }
  if (envelope.event === EVAL_EVENT_RUN_COMPLETED && isEvalRunCompletedPayload(envelope.payload)) {
    return { kind: "run_completed", payload: envelope.payload };
  }
  if (envelope.event === EVAL_EVENT_COST_WARNING && isEvalCostWarningPayload(envelope.payload)) {
    return { kind: "cost_warning", payload: envelope.payload };
  }
  return null;
}
