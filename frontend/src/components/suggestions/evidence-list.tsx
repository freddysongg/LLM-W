import type { SuggestionEvidence } from "@/types/suggestion";

interface EvidenceListProps {
  readonly evidence: ReadonlyArray<SuggestionEvidence>;
}

export function EvidenceList({ evidence }: EvidenceListProps): React.JSX.Element {
  if (evidence.length === 0) {
    return <p className="text-sm text-muted-foreground italic">No evidence recorded.</p>;
  }

  return (
    <ul className="space-y-1.5">
      {evidence.map((item, idx) => (
        <li key={idx} className="flex items-start gap-2 text-sm">
          <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-primary/60" />
          <span>
            <span className="font-medium">{item.label}:</span>{" "}
            <span className="text-muted-foreground">{String(item.value)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
