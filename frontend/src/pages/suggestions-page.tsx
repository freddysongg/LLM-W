import * as React from "react";
import { RefreshCw, Sparkle, Settings as SettingsIcon } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import {
  useSuggestions,
  useAcceptSuggestion,
  useRejectSuggestion,
  useGenerateSuggestions,
} from "@/hooks/useSuggestions";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { useToast } from "@/hooks/use-toast";
import { SuggestionList } from "@/components/suggestions/suggestion-list";
import { SuggestionDetail, SuggestionEmptyHint } from "@/components/suggestions/suggestion-detail";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export default function SuggestionsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = React.useState<string>("none");
  const [statusFilter, setStatusFilter] = React.useState<string | undefined>(undefined);
  const [isAutoApply, setIsAutoApply] = React.useState<boolean>(false);
  const isAnimationLocked = useLockEntered();
  const { toast } = useToast();

  const projectId = activeProjectId ?? "";

  const { data: runs = [] } = useRuns({ projectId });
  const { data: suggestions = [], isLoading } = useSuggestions({
    projectId,
    status: statusFilter,
  });

  const acceptMutation = useAcceptSuggestion();
  const rejectMutation = useRejectSuggestion();
  const generateMutation = useGenerateSuggestions();

  const selectedSuggestion = suggestions.find((candidate) => candidate.id === selectedId) ?? null;

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

  const handleToggleAutoApply = (): void => {
    const nextValue = !isAutoApply;
    setIsAutoApply(nextValue);
    toast({
      title: nextValue ? "Auto-apply enabled" : "Auto-apply disabled",
      description: "Rules configuration is not yet wired.",
    });
  };

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
          AI Suggestions
        </h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">
          Select a project to view AI suggestions.
        </p>
      </div>
    );
  }

  const enteredClass = isAnimationLocked ? "entered" : "";

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className={cn("flex items-start justify-between gap-4 enter enter-1", enteredClass)}>
        <div>
          <h1 className="flex items-center gap-2 font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            <Sparkle className="h-5 w-5" aria-hidden="true" />
            AI Suggestions
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            Claude watches your runs, datasets and configs · {suggestions.length} active
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={selectedRunId} onValueChange={setSelectedRunId}>
            <SelectTrigger className="w-[200px]" aria-label="Source run for suggestions">
              <SelectValue placeholder="No run selected" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">No run selected</SelectItem>
              {runs.map((run) => (
                <SelectItem key={run.id} value={run.id}>
                  Run {run.id.slice(0, 8)} ({run.status})
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="sm"
            onClick={handleGenerate}
            disabled={!projectId || generateMutation.isPending}
          >
            <RefreshCw aria-hidden="true" />
            {generateMutation.isPending ? "Scanning…" : "Re-scan"}
          </Button>
          <Button
            variant={isAutoApply ? "primary" : "outline"}
            size="sm"
            onClick={handleToggleAutoApply}
            aria-pressed={isAutoApply}
          >
            <SettingsIcon aria-hidden="true" />
            Auto-apply rules
          </Button>
        </div>
      </header>

      <div
        className={cn("grid gap-4 enter enter-2", enteredClass)}
        style={{ gridTemplateColumns: "340px 1fr" }}
      >
        <Card className="flex max-h-[calc(100vh-220px)] flex-col">
          <CardHeader className="py-3">
            <CardTitle>Inbox</CardTitle>
            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
              {suggestions.length}
            </span>
          </CardHeader>
          <div className="border-b border-hairline px-3.5 py-2">
            <Select value={statusFilter ?? "all"} onValueChange={handleStatusFilterChange}>
              <SelectTrigger className="h-7 text-[11px]" aria-label="Filter suggestions by status">
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
              <div className="p-4 font-mono text-[11px] text-ink-3">Loading…</div>
            ) : (
              <SuggestionList
                suggestions={suggestions}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            )}
          </div>
        </Card>

        <div className="min-w-0">
          {selectedSuggestion ? (
            <SuggestionDetail
              suggestion={selectedSuggestion}
              isAccepting={acceptMutation.isPending}
              isRejecting={rejectMutation.isPending}
              onAccept={handleAccept}
              onReject={handleReject}
            />
          ) : (
            <Card className="h-full">
              <CardContent className="flex h-full min-h-[200px] items-center justify-center py-10">
                <SuggestionEmptyHint />
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
