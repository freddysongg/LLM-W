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
import { InvariantError } from "@/lib/errors";
import { fetchApi } from "./client";

const EVAL_RUN_STATUSES: ReadonlyArray<EvalRunStatus> = [
  "pending",
  "running",
  "completed",
  "failed",
  "cancelled",
];
const JUDGE_TIERS: ReadonlyArray<JudgeTier> = ["tier1", "llm"];
const JUDGE_VERDICTS: ReadonlyArray<JudgeVerdict> = ["pass", "fail"];
const RUBRIC_CALIBRATION_STATUSES: ReadonlyArray<RubricCalibrationStatus> = [
  "uncalibrated",
  "calibrated",
  "failed",
];

function parseEvalRunStatus(raw: unknown): EvalRunStatus {
  const candidate = EVAL_RUN_STATUSES.find((status) => status === raw);
  if (candidate !== undefined) return candidate;
  throw new InvariantError(`invalid eval run status: ${String(raw)}`);
}

function parseJudgeTier(raw: unknown): JudgeTier {
  const candidate = JUDGE_TIERS.find((tier) => tier === raw);
  if (candidate !== undefined) return candidate;
  throw new InvariantError(`invalid judge tier: ${String(raw)}`);
}

function parseJudgeVerdict(raw: unknown): JudgeVerdict {
  const candidate = JUDGE_VERDICTS.find((verdict) => verdict === raw);
  if (candidate !== undefined) return candidate;
  throw new InvariantError(`invalid judge verdict: ${String(raw)}`);
}

function parseRubricCalibrationStatus(raw: unknown): RubricCalibrationStatus {
  const candidate = RUBRIC_CALIBRATION_STATUSES.find((status) => status === raw);
  if (candidate !== undefined) return candidate;
  throw new InvariantError(`invalid rubric calibration status: ${String(raw)}`);
}

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
    status: parseEvalRunStatus(raw.status),
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
    tier: parseJudgeTier(raw.tier),
    verdict: parseJudgeVerdict(raw.verdict),
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
    calibrationStatus: parseRubricCalibrationStatus(raw.calibration_status),
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

const JSON_INDENT_SPACES = 2;
const DOWNLOAD_MIME_TYPE = "application/json";

interface DownloadEvalRunAsJsonParams {
  readonly evalRunDetail: EvalRunDetail;
}

export function downloadEvalRunAsJson({ evalRunDetail }: DownloadEvalRunAsJsonParams): void {
  const jsonPayload = JSON.stringify(evalRunDetail, null, JSON_INDENT_SPACES);
  const filename = `eval-run-${evalRunDetail.run.id}.json`;
  const blob = new Blob([jsonPayload], { type: DOWNLOAD_MIME_TYPE });
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(objectUrl);
}
