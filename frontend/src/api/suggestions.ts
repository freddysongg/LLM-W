import type {
  AISuggestion,
  GenerateSuggestionsRequest,
  SuggestionEvidence,
  SuggestionConfigDiff,
} from "@/types/suggestion";
import { fetchApi } from "./client";

interface RawSuggestion {
  readonly id: string;
  readonly project_id: string;
  readonly source_run_id: string | null;
  readonly provider: string;
  readonly config_diff: string;
  readonly rationale: string;
  readonly evidence_json: string | null;
  readonly expected_effect: string | null;
  readonly tradeoffs: string | null;
  readonly confidence: number | null;
  readonly risk_level: string | null;
  readonly status: string;
  readonly applied_config_version_id: string | null;
  readonly created_at: string;
  readonly resolved_at: string | null;
}

interface RawSuggestionListResponse {
  readonly items: ReadonlyArray<RawSuggestion>;
  readonly total: number;
}

function parseSuggestion(raw: RawSuggestion): AISuggestion {
  let configDiff: SuggestionConfigDiff = {};
  try {
    configDiff = JSON.parse(raw.config_diff) as SuggestionConfigDiff;
  } catch {
    // malformed diff — treat as empty
  }

  let evidence: ReadonlyArray<SuggestionEvidence> = [];
  if (raw.evidence_json) {
    try {
      evidence = JSON.parse(raw.evidence_json) as ReadonlyArray<SuggestionEvidence>;
    } catch {
      evidence = [];
    }
  }

  return {
    id: raw.id,
    projectId: raw.project_id,
    sourceRunId: raw.source_run_id,
    provider: raw.provider as AISuggestion["provider"],
    configDiff,
    rationale: raw.rationale,
    evidence,
    expectedEffect: raw.expected_effect,
    tradeoffs: raw.tradeoffs,
    confidence: raw.confidence,
    riskLevel: raw.risk_level as AISuggestion["riskLevel"],
    status: raw.status as AISuggestion["status"],
    appliedConfigVersionId: raw.applied_config_version_id,
    createdAt: raw.created_at,
    resolvedAt: raw.resolved_at,
  };
}

export interface FetchSuggestionsParams {
  readonly projectId: string;
  readonly status?: string;
}

export async function fetchSuggestions({
  projectId,
  status,
}: FetchSuggestionsParams): Promise<ReadonlyArray<AISuggestion>> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  const raw = await fetchApi<RawSuggestionListResponse>({
    path: `/projects/${projectId}/suggestions${query}`,
  });
  return raw.items.map(parseSuggestion);
}

export async function fetchSuggestion({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}): Promise<AISuggestion> {
  const raw = await fetchApi<RawSuggestion>({
    path: `/projects/${projectId}/suggestions/${suggestionId}`,
  });
  return parseSuggestion(raw);
}

export async function generateSuggestions({
  projectId,
  request,
}: {
  projectId: string;
  request: GenerateSuggestionsRequest;
}): Promise<ReadonlyArray<AISuggestion>> {
  const raw = await fetchApi<RawSuggestionListResponse>({
    path: `/projects/${projectId}/suggestions/generate`,
    method: "POST",
    body: {
      source_run_id: request.sourceRunId ?? null,
      notes: request.notes ?? null,
    },
  });
  return raw.items.map(parseSuggestion);
}

export async function acceptSuggestion({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}): Promise<AISuggestion> {
  const raw = await fetchApi<RawSuggestion>({
    path: `/projects/${projectId}/suggestions/${suggestionId}/accept`,
    method: "POST",
  });
  return parseSuggestion(raw);
}

export async function rejectSuggestion({
  projectId,
  suggestionId,
}: {
  projectId: string;
  suggestionId: string;
}): Promise<AISuggestion> {
  const raw = await fetchApi<RawSuggestion>({
    path: `/projects/${projectId}/suggestions/${suggestionId}/reject`,
    method: "POST",
  });
  return parseSuggestion(raw);
}
