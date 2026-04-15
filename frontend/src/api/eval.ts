import type {
  ConversationTurn,
  EvalCall,
  EvalCallsPage,
  EvalCase,
  EvalListQuery,
  EvalRun,
  EvalRunCreateRequest,
  EvalRunDetail,
  EvalRunStatus,
  EvaluationCasePayload,
  JudgeTier,
  JudgeVerdict,
  Rubric,
  RubricCalibrationStatus,
  RubricVersion,
} from "@/types/eval";
import { fetchApi } from "./client";

interface RawEvaluationCasePayload {
  readonly prompt: string;
  readonly output: string;
  readonly reference: string | null;
  readonly retrieved_context: string | null;
  readonly conversation_history: ReadonlyArray<ConversationTurn> | null;
  readonly metadata: Readonly<Record<string, string>>;
}

interface RawEvalRun {
  readonly id: string;
  readonly training_run_id: string | null;
  readonly status: string;
  readonly started_at: string;
  readonly completed_at: string | null;
  readonly pass_rate: number | null;
  readonly total_cost_usd: number;
  readonly max_cost_usd: number | null;
}

interface RawEvalCase {
  readonly id: string;
  readonly eval_run_id: string;
  readonly case_input: RawEvaluationCasePayload;
  readonly input_hash: string;
}

interface RawEvalCall {
  readonly id: string;
  readonly eval_run_id: string;
  readonly case_id: string;
  readonly rubric_version_id: string;
  readonly judge_model: string;
  readonly tier: string;
  readonly verdict: string;
  readonly reasoning: string;
  readonly per_criterion: Readonly<Record<string, boolean>> | null;
  readonly response_hash: string;
  readonly cost_usd: number;
  readonly latency_ms: number | null;
  readonly replayed_from_id: string | null;
  readonly created_at: string;
}

interface RawEvalRunListResponse {
  readonly items: ReadonlyArray<RawEvalRun>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

interface RawEvalRunDetail {
  readonly run: RawEvalRun;
  readonly cases: ReadonlyArray<RawEvalCase>;
  readonly calls: ReadonlyArray<RawEvalCall>;
}

interface RawEvalCallsPage {
  readonly items: ReadonlyArray<RawEvalCall>;
  readonly total: number;
  readonly limit: number;
  readonly offset: number;
}

interface RawRubricVersion {
  readonly id: string;
  readonly rubric_id: string;
  readonly version_number: number;
  readonly content_hash: string;
  readonly calibration_status: string;
  readonly judge_model_pin: string;
  readonly created_at: string;
}

interface RawRubric {
  readonly id: string;
  readonly name: string;
  readonly description: string;
  readonly research_basis: string | null;
  readonly versions: ReadonlyArray<RawRubricVersion>;
  readonly created_at: string;
}

function normalizeEvaluationCase(raw: RawEvaluationCasePayload): EvaluationCasePayload {
  return {
    prompt: raw.prompt,
    output: raw.output,
    reference: raw.reference,
    retrievedContext: raw.retrieved_context,
    conversationHistory: raw.conversation_history,
    metadata: raw.metadata,
  };
}

function normalizeEvalRun(raw: RawEvalRun): EvalRun {
  return {
    id: raw.id,
    trainingRunId: raw.training_run_id,
    status: raw.status as EvalRunStatus,
    startedAt: raw.started_at,
    completedAt: raw.completed_at,
    passRate: raw.pass_rate,
    totalCostUsd: raw.total_cost_usd,
    maxCostUsd: raw.max_cost_usd,
  };
}

function normalizeEvalCase(raw: RawEvalCase): EvalCase {
  return {
    id: raw.id,
    evalRunId: raw.eval_run_id,
    caseInput: normalizeEvaluationCase(raw.case_input),
    inputHash: raw.input_hash,
  };
}

function normalizeEvalCall(raw: RawEvalCall): EvalCall {
  return {
    id: raw.id,
    evalRunId: raw.eval_run_id,
    caseId: raw.case_id,
    rubricVersionId: raw.rubric_version_id,
    judgeModel: raw.judge_model,
    tier: raw.tier as JudgeTier,
    verdict: raw.verdict as JudgeVerdict,
    reasoning: raw.reasoning,
    perCriterion: raw.per_criterion,
    responseHash: raw.response_hash,
    costUsd: raw.cost_usd,
    latencyMs: raw.latency_ms,
    replayedFromId: raw.replayed_from_id,
    createdAt: raw.created_at,
  };
}

function normalizeRubricVersion(raw: RawRubricVersion): RubricVersion {
  return {
    id: raw.id,
    rubricId: raw.rubric_id,
    versionNumber: raw.version_number,
    contentHash: raw.content_hash,
    calibrationStatus: raw.calibration_status as RubricCalibrationStatus,
    judgeModelPin: raw.judge_model_pin,
    createdAt: raw.created_at,
  };
}

function normalizeRubric(raw: RawRubric): Rubric {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    researchBasis: raw.research_basis,
    versions: raw.versions.map(normalizeRubricVersion),
    createdAt: raw.created_at,
  };
}

function buildEvalListQuery({ trainingRunId, limit, offset }: EvalListQuery): string {
  const searchParams = new URLSearchParams();
  if (trainingRunId !== undefined && trainingRunId !== null) {
    searchParams.set("training_run_id", trainingRunId);
  }
  if (limit !== undefined) {
    searchParams.set("limit", String(limit));
  }
  if (offset !== undefined) {
    searchParams.set("offset", String(offset));
  }
  const suffix = searchParams.toString();
  return suffix ? `?${suffix}` : "";
}

export async function fetchEvalRuns(params: EvalListQuery = {}): Promise<ReadonlyArray<EvalRun>> {
  const raw = await fetchApi<RawEvalRunListResponse>({
    path: `/eval/runs${buildEvalListQuery(params)}`,
  });
  return raw.items.map(normalizeEvalRun);
}

export async function fetchEvalRun({ evalRunId }: { evalRunId: string }): Promise<EvalRunDetail> {
  const raw = await fetchApi<RawEvalRunDetail>({ path: `/eval/runs/${evalRunId}` });
  return {
    run: normalizeEvalRun(raw.run),
    cases: raw.cases.map(normalizeEvalCase),
    calls: raw.calls.map(normalizeEvalCall),
  };
}

export async function fetchEvalRunCalls({
  evalRunId,
  limit,
  offset,
}: {
  evalRunId: string;
  limit?: number;
  offset?: number;
}): Promise<EvalCallsPage> {
  const searchParams = new URLSearchParams();
  if (limit !== undefined) searchParams.set("limit", String(limit));
  if (offset !== undefined) searchParams.set("offset", String(offset));
  const suffix = searchParams.toString();
  const raw = await fetchApi<RawEvalCallsPage>({
    path: `/eval/runs/${evalRunId}/calls${suffix ? `?${suffix}` : ""}`,
  });
  return {
    items: raw.items.map(normalizeEvalCall),
    total: raw.total,
    limit: raw.limit,
    offset: raw.offset,
  };
}

export async function createEvalRun({
  trainingRunId,
  rubricVersionIds,
  maxCostUsd,
}: EvalRunCreateRequest): Promise<EvalRun> {
  const raw = await fetchApi<RawEvalRun>({
    path: `/eval/runs`,
    method: "POST",
    body: {
      training_run_id: trainingRunId,
      rubric_version_ids: rubricVersionIds,
      max_cost_usd: maxCostUsd,
    },
  });
  return normalizeEvalRun(raw);
}

export async function fetchRubrics(): Promise<ReadonlyArray<Rubric>> {
  const raw = await fetchApi<ReadonlyArray<RawRubric>>({ path: `/rubrics` });
  return raw.map(normalizeRubric);
}
