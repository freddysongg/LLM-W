export type SuggestionStatus = "pending" | "accepted" | "rejected" | "applied" | "expired";
export type SuggestionProvider = "anthropic" | "openai_compatible" | "rule_engine";
export type RiskLevel = "low" | "medium" | "high";

export interface SuggestionEvidence {
  readonly type: string;
  readonly referenceId: string;
  readonly label: string;
  readonly value: string | number;
}

export interface SuggestionConfigChange {
  readonly current: unknown;
  readonly suggested: unknown;
}

export type SuggestionConfigDiff = Record<string, SuggestionConfigChange>;

export interface AISuggestion {
  readonly id: string;
  readonly projectId: string;
  readonly sourceRunId: string | null;
  readonly provider: SuggestionProvider;
  readonly configDiff: SuggestionConfigDiff;
  readonly rationale: string;
  readonly evidence: ReadonlyArray<SuggestionEvidence>;
  readonly expectedEffect: string | null;
  readonly tradeoffs: string | null;
  readonly confidence: number | null;
  readonly riskLevel: RiskLevel | null;
  readonly status: SuggestionStatus;
  readonly appliedConfigVersionId: string | null;
  readonly createdAt: string;
  readonly resolvedAt: string | null;
}

export interface GenerateSuggestionsRequest {
  readonly sourceRunId?: string;
  readonly notes?: string;
}
