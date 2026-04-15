import * as React from "react";
import { X } from "lucide-react";
import type { EvalCall, EvalCase, RubricVersion, Rubric } from "@/types/eval";
import { Button } from "@/components/ui/button";
import { JudgeVerdictBadge } from "./judge-verdict-badge";
import { CotExpansion } from "./cot-expansion";

interface EvalCaseDetailDrawerProps {
  readonly evalCase: EvalCase;
  readonly calls: ReadonlyArray<EvalCall>;
  readonly rubrics: ReadonlyArray<Rubric>;
  readonly onClose: () => void;
}

interface RubricVersionLookup {
  readonly rubric: Rubric;
  readonly version: RubricVersion;
}

function buildRubricLookup(rubrics: ReadonlyArray<Rubric>): Map<string, RubricVersionLookup> {
  const lookup = new Map<string, RubricVersionLookup>();
  for (const rubric of rubrics) {
    for (const version of rubric.versions) {
      lookup.set(version.id, { rubric, version });
    }
  }
  return lookup;
}

function formatUsd(amount: number): string {
  return `$${amount.toFixed(4)}`;
}

function formatLatency(latencyMs: number | null): string {
  if (latencyMs === null) return "—";
  if (latencyMs < 1000) return `${latencyMs}ms`;
  return `${(latencyMs / 1000).toFixed(2)}s`;
}

interface PerCriterionRowProps {
  readonly criterionName: string;
  readonly passed: boolean;
}

function PerCriterionRow({ criterionName, passed }: PerCriterionRowProps): React.JSX.Element {
  return (
    <li className="flex items-center justify-between text-xs">
      <span className="text-muted-foreground">{criterionName}</span>
      <span className={passed ? "text-emerald-600 font-medium" : "text-destructive font-medium"}>
        {passed ? "pass" : "fail"}
      </span>
    </li>
  );
}

interface EvalCallCardProps {
  readonly call: EvalCall;
  readonly rubricLookup: ReadonlyMap<string, RubricVersionLookup>;
}

function EvalCallCard({ call, rubricLookup }: EvalCallCardProps): React.JSX.Element {
  const {
    id,
    rubricVersionId,
    verdict,
    reasoning,
    perCriterion,
    judgeModel,
    tier,
    responseHash,
    costUsd,
    latencyMs,
  } = call;
  const rubricEntry = rubricLookup.get(rubricVersionId);
  const rubricLabel = rubricEntry
    ? `${rubricEntry.rubric.name} · v${rubricEntry.version.versionNumber}`
    : `rubric version ${rubricVersionId.slice(0, 8)}`;
  const perCriterionEntries = perCriterion ? Object.entries(perCriterion) : [];

  return (
    <div className="rounded-md border bg-background p-3 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">{rubricLabel}</span>
            <JudgeVerdictBadge verdict={verdict} />
          </div>
          <div className="text-xs text-muted-foreground">
            {judgeModel} · tier {tier}
          </div>
        </div>
        <div className="text-xs text-muted-foreground text-right space-y-0.5">
          <div>{formatUsd(costUsd)}</div>
          <div>{formatLatency(latencyMs)}</div>
        </div>
      </div>

      <CotExpansion title="Chain-of-thought reasoning" reasoning={reasoning} />

      {perCriterionEntries.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium">Criteria</div>
          <ul className="space-y-1">
            {perCriterionEntries.map(([criterionName, passed]) => (
              <PerCriterionRow
                key={`${id}-${criterionName}`}
                criterionName={criterionName}
                passed={passed}
              />
            ))}
          </ul>
        </div>
      )}

      <div className="text-[10px] font-mono text-muted-foreground/70">
        hash {responseHash.slice(0, 16)}…
      </div>
    </div>
  );
}

interface OutputComparisonProps {
  readonly output: string;
  readonly reference: string | null;
}

function OutputComparison({ output, reference }: OutputComparisonProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
      <div className="space-y-1.5">
        <div className="text-xs font-medium">Model output</div>
        <pre className="text-xs whitespace-pre-wrap bg-muted rounded-md px-3 py-2 font-mono overflow-x-auto">
          {output}
        </pre>
      </div>
      <div className="space-y-1.5">
        <div className="text-xs font-medium">Reference</div>
        <pre className="text-xs whitespace-pre-wrap bg-muted rounded-md px-3 py-2 font-mono overflow-x-auto">
          {reference ?? "(no reference)"}
        </pre>
      </div>
    </div>
  );
}

export function EvalCaseDetailDrawer({
  evalCase,
  calls,
  rubrics,
  onClose,
}: EvalCaseDetailDrawerProps): React.JSX.Element {
  const rubricLookup = React.useMemo(() => buildRubricLookup(rubrics), [rubrics]);
  const { caseInput, id } = evalCase;
  const { prompt, output, reference, retrievedContext, conversationHistory, metadata } = caseInput;
  const metadataEntries = Object.entries(metadata);

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Case detail</h3>
          <span className="font-mono text-xs text-muted-foreground">{id.slice(0, 8)}</span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          aria-label="Close case detail"
          className="h-7 w-7"
        >
          <X className="h-4 w-4" />
        </Button>
      </div>

      <div className="space-y-1.5">
        <div className="text-xs font-medium">Prompt</div>
        <pre className="text-xs whitespace-pre-wrap bg-muted rounded-md px-3 py-2 font-mono overflow-x-auto">
          {prompt}
        </pre>
      </div>

      <OutputComparison output={output} reference={reference} />

      {retrievedContext !== null && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium">Retrieved context</div>
          <pre className="text-xs whitespace-pre-wrap bg-muted rounded-md px-3 py-2 font-mono overflow-x-auto">
            {retrievedContext}
          </pre>
        </div>
      )}

      {conversationHistory !== null && conversationHistory.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium">Conversation history</div>
          <ul className="space-y-1">
            {conversationHistory.map((turn, index) => (
              <li key={index} className="text-xs">
                <span className="font-medium text-muted-foreground">{turn.role}:</span>{" "}
                <span className="whitespace-pre-wrap">{turn.content}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {metadataEntries.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium">Metadata</div>
          <ul className="space-y-0.5">
            {metadataEntries.map(([key, entryValue]) => (
              <li key={key} className="text-xs text-muted-foreground">
                <span className="font-mono">{key}</span>: {entryValue}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <div className="text-xs font-medium">Judge calls</div>
        {calls.length === 0 ? (
          <div className="text-xs text-muted-foreground">No judge calls for this case yet.</div>
        ) : (
          <div className="space-y-2">
            {calls.map((call) => (
              <EvalCallCard key={call.id} call={call} rubricLookup={rubricLookup} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
