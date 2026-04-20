import type { SuggestionEvidence } from "@/types/suggestion";

interface EvidenceListProps {
  readonly evidence: ReadonlyArray<SuggestionEvidence>;
}

export function EvidenceList({ evidence }: EvidenceListProps): React.JSX.Element {
  if (evidence.length === 0) {
    return <p className="font-mono text-[11px] text-ink-3">No evidence recorded.</p>;
  }

  return (
    <ul className="flex flex-col gap-1.5">
      {evidence.map((item) => (
        <li
          key={`${item.type}:${item.referenceId}:${item.label}`}
          className="flex items-start gap-2 text-[13px]"
        >
          <span
            aria-hidden="true"
            className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--iris-3)]"
          />
          <span>
            <span className="font-medium text-ink-1">{item.label}:</span>{" "}
            <span className="text-ink-3">{String(item.value)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}
