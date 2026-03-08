import type { AISuggestion } from "@/types/suggestion";
import { ConfidenceBadge, RiskBadge, ProviderBadge } from "./suggestion-badges";

interface SuggestionListProps {
  readonly suggestions: ReadonlyArray<AISuggestion>;
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
}

const STATUS_STYLES: Record<AISuggestion["status"], string> = {
  pending: "border-l-blue-400",
  accepted: "border-l-green-400",
  rejected: "border-l-muted-foreground",
  applied: "border-l-green-600",
  expired: "border-l-muted",
};

function formatDate(isoString: string): string {
  return new Date(isoString).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function SuggestionList({
  suggestions,
  selectedId,
  onSelect,
}: SuggestionListProps): React.JSX.Element {
  if (suggestions.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-40 px-4 text-center text-muted-foreground text-sm">
        No suggestions yet. Click Generate to analyse the current run.
      </div>
    );
  }

  return (
    <ul className="divide-y">
      {suggestions.map((suggestion) => (
        <li key={suggestion.id}>
          <button
            type="button"
            onClick={() => onSelect(suggestion.id)}
            className={`w-full text-left px-4 py-3 border-l-4 transition-colors hover:bg-muted/50 ${STATUS_STYLES[suggestion.status]} ${selectedId === suggestion.id ? "bg-muted/50" : ""}`}
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-medium line-clamp-2 flex-1">{suggestion.rationale}</p>
              <span className="shrink-0 text-xs text-muted-foreground capitalize">
                {suggestion.status}
              </span>
            </div>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              <ProviderBadge provider={suggestion.provider} />
              <RiskBadge riskLevel={suggestion.riskLevel} />
              <ConfidenceBadge confidence={suggestion.confidence} />
              <span className="text-xs text-muted-foreground ml-auto">
                {formatDate(suggestion.createdAt)}
              </span>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
