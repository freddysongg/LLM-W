import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import {
  useSuggestions,
  useAcceptSuggestion,
  useRejectSuggestion,
  useGenerateSuggestions,
} from "@/hooks/useSuggestions";
import { SuggestionList } from "@/components/suggestions/suggestion-list";
import { SuggestionDetail } from "@/components/suggestions/suggestion-detail";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function SuggestionsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = React.useState<string>("none");
  const [statusFilter, setStatusFilter] = React.useState<string | undefined>(undefined);

  const projectId = activeProjectId ?? "";

  const { data: runs = [] } = useRuns({ projectId });
  const { data: suggestions = [], isLoading } = useSuggestions({
    projectId,
    status: statusFilter,
  });

  const acceptMutation = useAcceptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const generateMutation = useGenerateSuggestions();

  const selectedSuggestion = suggestions.find((s) => s.id === selectedId) ?? null;

  const handleGenerate = (): void => {
    if (!projectId) return;
    generateMutation.mutate(
      {
        projectId,
        request: { sourceRunId: selectedRunId !== "none" ? selectedRunId : undefined },
      },
      {
        onSuccess: (created) => {
          if (created.length > 0) {
            setSelectedId(created[0].id);
          }
        },
      },
    );
  };

  const handleAccept = (suggestionId: string): void => {
    if (!projectId) return;
    acceptMutation.mutate({ projectId, suggestionId });
  };

  const handleReject = (suggestionId: string): void => {
    if (!projectId) return;
    rejectMutation.mutate({ projectId, suggestionId });
  };

  const handleStatusFilterChange = (value: string): void => {
    setStatusFilter(value === "all" ? undefined : value);
    setSelectedId(null);
  };

  if (!activeProjectId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Select a project to view AI suggestions.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-4 border-b">
        <h1 className="text-xl font-semibold">AI Suggestions</h1>
        <div className="flex items-center gap-3">
          <Select value={selectedRunId} onValueChange={setSelectedRunId}>
            <SelectTrigger className="w-52">
              <SelectValue placeholder="No run selected" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">No run selected</SelectItem>
              {runs.map((run) => (
                <SelectItem key={run.id} value={run.id}>
                  Run {run.id.slice(0, 8)}… ({run.status})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            onClick={handleGenerate}
            disabled={!projectId || generateMutation.isPending}
            aria-label="Generate AI suggestions for the selected run"
          >
            {generateMutation.isPending ? "Generating…" : "Generate"}
          </Button>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-80 shrink-0 flex flex-col border-r overflow-hidden">
          <div className="px-4 py-2 border-b">
            <Select value={statusFilter ?? "all"} onValueChange={handleStatusFilterChange}>
              <SelectTrigger className="h-8 text-sm">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="accepted">Accepted</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="p-4 text-sm text-muted-foreground">Loading…</div>
            ) : (
              <SuggestionList
                suggestions={suggestions}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            )}
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          {selectedSuggestion ? (
            <SuggestionDetail
              suggestion={selectedSuggestion}
              isAccepting={acceptMutation.isPending}
              isRejecting={rejectMutation.isPending}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              Select a suggestion to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
