import type { AISuggestion } from "@/types/suggestion";
import { SuggestionRow } from "./suggestion-row";

interface SuggestionListProps {
  readonly suggestions: ReadonlyArray<AISuggestion>;
  readonly selectedId: string | null;
  readonly onSelect: (id: string) => void;
}

export function SuggestionList({
  suggestions,
  selectedId,
  onSelect,
}: SuggestionListProps): React.JSX.Element {
  if (suggestions.length === 0) {
    return (
      <div className="flex h-40 flex-col items-center justify-center px-4 text-center font-mono text-[11px] text-ink-3">
        No suggestions yet. Click Generate to analyse the current run.
      </div>
    );
  }

  return (
    <div>
      {suggestions.map((suggestion) => (
        <SuggestionRow
          key={suggestion.id}
          suggestion={suggestion}
          isActive={selectedId === suggestion.id}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
