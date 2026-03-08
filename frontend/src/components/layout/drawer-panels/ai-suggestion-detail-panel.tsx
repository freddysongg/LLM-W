import * as React from "react";
import { useSuggestion, useAcceptSuggestion, useRejectSuggestion } from "@/hooks/useSuggestions";
import { SuggestionDetail } from "@/components/suggestions/suggestion-detail";

interface AiSuggestionDetailPanelProps {
  readonly projectId: string;
  readonly suggestionId: string;
}

export function AiSuggestionDetailPanel({
  projectId,
  suggestionId,
}: AiSuggestionDetailPanelProps): React.JSX.Element {
  const { data: suggestion, isLoading } = useSuggestion({ projectId, suggestionId });
  const { mutate: accept, isPending: isAccepting } = useAcceptSuggestion();
  const { mutate: reject, isPending: isRejecting } = useRejectSuggestion();

  if (isLoading) {
    return <p className="text-sm text-muted-foreground p-4">Loading…</p>;
  }

  if (!suggestion) {
    return <p className="text-sm text-muted-foreground p-4">Suggestion not found.</p>;
  }

  return (
    <SuggestionDetail
      suggestion={suggestion}
      isAccepting={isAccepting}
      isRejecting={isRejecting}
      onAccept={(id) => accept({ projectId, suggestionId: id })}
      onReject={(id) => reject({ projectId, suggestionId: id })}
    />
  );
}
