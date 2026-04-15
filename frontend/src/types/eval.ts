export type EvalRunStatus = "pending" | "running" | "completed" | "failed" | "cancelled";

export type JudgeVerdict = "pass" | "fail";

export type JudgeTier = "tier1" | "llm";

export type RubricCalibrationStatus = "uncalibrated" | "calibrated" | "failed";

export interface ConversationTurn {
  readonly role: string;
  readonly content: string;
}

export interface EvaluationCasePayload {
  readonly prompt: string;
  readonly output: string;
  readonly reference: string | null;
  readonly retrievedContext: string | null;
  readonly conversationHistory: ReadonlyArray<ConversationTurn> | null;
  readonly metadata: Readonly<Record<string, string>>;
}

export interface EvalRun {
  readonly id: string;
  readonly trainingRunId: string | null;
  readonly status: EvalRunStatus;
  readonly startedAt: string;
  readonly completedAt: string | null;
  readonly passRate: number | null;
  readonly totalCostUsd: number;
  readonly maxCostUsd: number | null;
}

export interface EvalCase {
  readonly id: string;
  readonly evalRunId: string;
  readonly caseInput: EvaluationCasePayload;
  readonly inputHash: string;
}

export interface EvalCall {
  readonly id: string;
  readonly evalRunId: string;
  readonly caseId: string;
  readonly rubricVersionId: string;
  readonly judgeModel: string;
  readonly tier: JudgeTier;
  readonly verdict: JudgeVerdict;
  readonly reasoning: string;
  readonly perCriterion: Readonly<Record<string, boolean>> | null;
  readonly responseHash: string;
  readonly costUsd: number;
  readonly latencyMs: number | null;
  readonly replayedFromId: string | null;
  readonly createdAt: string;
}

export interface EvalRunDetail {
  readonly run: EvalRun;
  readonly cases: ReadonlyArray<EvalCase>;
  readonly calls: ReadonlyArray<EvalCall>;
}

export interface EvalCallsPage {
  readonly items: ReadonlyArray<EvalCall>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

export interface RubricVersion {
  readonly id: string;
  readonly rubricId: string;
  readonly versionNumber: number;
  readonly contentHash: string;
  readonly calibrationStatus: RubricCalibrationStatus;
  readonly judgeModelPin: string;
  readonly createdAt: string;
}

export interface Rubric {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly researchBasis: string | null;
  readonly versions: ReadonlyArray<RubricVersion>;
  readonly createdAt: string;
}

export interface EvalRunCreateRequest {
  readonly trainingRunId: string | null;
  readonly rubricVersionIds: ReadonlyArray<string>;
  readonly maxCostUsd: number | null;
}

export interface EvalListQuery {
  readonly trainingRunId?: string | null;
  readonly limit?: number;
  readonly offset?: number;
}

export interface EvalCaseCompletedPayload {
  readonly evalRunId: string;
  readonly caseId: string;
  readonly rubricVersionId: string;
  readonly evalCallId: string;
  readonly verdict: JudgeVerdict;
  readonly costUsd: number;
  readonly latencyMs: number | null;
}

export interface EvalRunCompletedPayload {
  readonly evalRunId: string;
  readonly status: EvalRunStatus;
  readonly passRate: number | null;
  readonly totalCostUsd: number;
}

export interface EvalCostWarningPayload {
  readonly evalRunId: string;
  readonly currentCostUsd: number;
  readonly maxCostUsd: number;
  readonly warningPct: number;
}

export type EvalEventName = "case_completed" | "run_completed" | "cost_warning";
