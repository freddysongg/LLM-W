import * as React from "react";
import type { AISuggestion } from "@/types/suggestion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type SuggestionSeverity = "warn" | "iris" | "success" | "danger";

const SEVERITY_COLOR: Record<SuggestionSeverity, string> = {
  warn: "var(--warn)",
  iris: "var(--iris-3)",
  success: "var(--success)",
  danger: "var(--danger)",
};

function severityForSuggestion(suggestion: AISuggestion): SuggestionSeverity {
  const { riskLevel } = suggestion;
  if (riskLevel === "high") return "danger";
  if (riskLevel === "medium") return "warn";
  if (riskLevel === "low") return "success";
  return "iris";
}

function providerLabel(provider: AISuggestion["provider"]): string {
  switch (provider) {
    case "anthropic":
      return "claude";
    case "openai":
    case "openai_compatible":
      return "openai";
    case "rule_engine":
      return "rule-engine";
    default: {
      const exhaustive: never = provider;
      return exhaustive;
    }
  }
}

function firstLine(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "(no title)";
  return trimmed.length > 80 ? `${trimmed.slice(0, 80)}…` : trimmed;
}

export interface SuggestionRowProps {
  readonly suggestion: AISuggestion;
  readonly isActive: boolean;
  readonly onSelect: (suggestionId: string) => void;
}

export function SuggestionRow({
  suggestion,
  isActive,
  onSelect,
}: SuggestionRowProps): React.JSX.Element {
  const { id, rationale, provider, status } = suggestion;
  const severity = severityForSuggestion(suggestion);
  const bulletColor = SEVERITY_COLOR[severity];
  const isApplied = status === "applied" || status === "accepted";

  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={cn(
        "flex w-full items-center gap-3 border-t border-hairline border-l-2 border-l-transparent px-3.5 py-3 text-left transition-colors duration-[var(--dur-1)]",
        "first:border-t-0 hover:bg-surface-2",
        "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
        isActive && "bg-surface-2 border-l-[color:var(--iris-3)]",
      )}
    >
      <span
        aria-hidden="true"
        className="h-2 w-2 shrink-0 rounded-full"
        style={{ background: bulletColor }}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-medium text-ink-1">{firstLine(rationale)}</div>
        <div className="mt-0.5 truncate font-mono text-[10.5px] text-ink-3">
          {providerLabel(provider)}
        </div>
      </div>
      {isApplied ? (
        <Badge variant="success" dot={false}>
          applied
        </Badge>
      ) : null}
    </button>
  );
}
