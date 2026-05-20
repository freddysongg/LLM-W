import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import { useCreateEvalRun, useEvalRun, useEvalRuns, useRubrics } from "@/hooks/useEval";
import { useEvalStream } from "@/hooks/useEvalStream";
import { useLockEntered } from "@/hooks/use-lock-entered";
import type { EvalCall } from "@/types/eval";
import { EvalRunList } from "@/components/eval/eval-run-list";
import { EvalRunHeader } from "@/components/eval/eval-run-header";
import { EvalTriggerPanel } from "@/components/eval/eval-trigger-panel";
import { EvalCaseTable } from "@/components/eval/eval-case-table";
import { EvalCaseDetailDrawer } from "@/components/eval/eval-case-detail-drawer";
import { EvalExportButton } from "@/components/eval/eval-export-button";
import { CostWarningBanner } from "@/components/eval/cost-warning-banner";
import { useToast } from "@/hooks/use-toast";
import { describeApiError } from "@/lib/api-error";
import { cn } from "@/lib/utils";

function buildCallsByCaseId(
  calls: ReadonlyArray<EvalCall>,
): ReadonlyMap<string, ReadonlyArray<EvalCall>> {
  const callsByCaseId = new Map<string, EvalCall[]>();
  for (const call of calls) {
    const existing = callsByCaseId.get(call.caseId);
    if (existing === undefined) {
      callsByCaseId.set(call.caseId, [call]);
    } else {
      existing.push(call);
    }
  }
  return callsByCaseId;
}

export default function EvalPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const isAnimationLocked = useLockEntered();
  const { toast } = useToast();

  const [selectedEvalRunId, setSelectedEvalRunId] = React.useState<string | null>(null);
  const [selectedTrainingRunId, setSelectedTrainingRunId] = React.useState<string | null>(null);
  const [selectedVersionIds, setSelectedVersionIds] = React.useState<ReadonlyArray<string>>([]);
  const [isUncalibratedVisible, setIsUncalibratedVisible] = React.useState<boolean>(false);
  const [maxCostUsd, setMaxCostUsd] = React.useState<number | null>(null);
  const [selectedCaseId, setSelectedCaseId] = React.useState<string | null>(null);

  const { data: trainingRuns = [] } = useRuns({ projectId: activeProjectId ?? "" });
  const { data: rubrics = [] } = useRubrics();
  const { data: evalRuns = [] } = useEvalRuns({});
  const { data: evalRunDetail } = useEvalRun({ evalRunId: selectedEvalRunId });
  const createEvalRunMutation = useCreateEvalRun();

  const streamState = useEvalStream({
    projectId: activeProjectId,
    evalRunId: selectedEvalRunId,
  });

  const handleToggleVersion = React.useCallback((rubricVersionId: string): void => {
    setSelectedVersionIds((previous) => {
      if (previous.includes(rubricVersionId)) {
        return previous.filter((candidate) => candidate !== rubricVersionId);
      }
      return [...previous, rubricVersionId];
    });
  }, []);

  const handleTriggerEval = React.useCallback((): void => {
    if (selectedVersionIds.length === 0) return;
    createEvalRunMutation.mutate(
      {
        trainingRunId: selectedTrainingRunId,
        rubricVersionIds: selectedVersionIds,
        maxCostUsd,
      },
      {
        onSuccess: (createdRun) => {
          setSelectedEvalRunId(createdRun.id);
          setSelectedCaseId(null);
        },
        onError: (cause) => {
          toast({
            title: "Eval failed to start",
            description: describeApiError({
              cause,
              fallback: "Unable to start evaluation run.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  }, [createEvalRunMutation, selectedTrainingRunId, selectedVersionIds, maxCostUsd, toast]);

  const handleSelectEvalRun = React.useCallback((evalRunId: string): void => {
    setSelectedEvalRunId(evalRunId);
    setSelectedCaseId(null);
  }, []);

  const callsByCaseId = React.useMemo<ReadonlyMap<string, ReadonlyArray<EvalCall>>>(
    () =>
      evalRunDetail
        ? buildCallsByCaseId(evalRunDetail.calls)
        : new Map<string, ReadonlyArray<EvalCall>>(),
    [evalRunDetail],
  );

  const selectedCase = React.useMemo(() => {
    if (!evalRunDetail || selectedCaseId === null) return null;
    return evalRunDetail.cases.find((candidate) => candidate.id === selectedCaseId) ?? null;
  }, [evalRunDetail, selectedCaseId]);

  const selectedCaseCalls = React.useMemo(() => {
    if (selectedCase === null) return [];
    return callsByCaseId.get(selectedCase.id) ?? [];
  }, [callsByCaseId, selectedCase]);

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
          Evaluation
        </h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">
          Select a project to run evaluations.
        </p>
      </div>
    );
  }

  const enteredClass = isAnimationLocked ? "entered" : "";

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className={cn("flex items-start justify-between gap-4 enter enter-1", enteredClass)}>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
              Evaluation
            </h1>
            {streamState.isConnected && (
              <span className="font-mono text-[11px] text-ink-3">· live</span>
            )}
          </div>
          <p className="mt-1 font-mono text-[11px] text-ink-3">
            rubric-based evaluation suites against training runs
          </p>
        </div>
        {evalRunDetail && <EvalExportButton evalRunDetail={evalRunDetail} />}
      </header>

      <div className={cn("flex flex-col gap-4 enter enter-2", enteredClass)}>
        <EvalTriggerPanel
          trainingRuns={trainingRuns}
          rubrics={rubrics}
          selectedTrainingRunId={selectedTrainingRunId}
          onSelectTrainingRun={setSelectedTrainingRunId}
          selectedVersionIds={selectedVersionIds}
          onToggleVersion={handleToggleVersion}
          isUncalibratedVisible={isUncalibratedVisible}
          onToggleIsUncalibratedVisible={setIsUncalibratedVisible}
          maxCostUsd={maxCostUsd}
          onMaxCostChange={setMaxCostUsd}
          onTriggerEval={handleTriggerEval}
          isTriggering={createEvalRunMutation.isPending}
        />

        {streamState.lastCostWarning !== null && (
          <CostWarningBanner warning={streamState.lastCostWarning} />
        )}

        <EvalRunList
          evalRuns={evalRuns}
          selectedEvalRunId={selectedEvalRunId}
          onSelectEvalRun={handleSelectEvalRun}
        />

        {evalRunDetail && (
          <>
            <EvalRunHeader evalRun={evalRunDetail.run} />
            <EvalCaseTable
              cases={evalRunDetail.cases}
              callsByCaseId={callsByCaseId}
              selectedCaseId={selectedCaseId}
              onSelectCase={setSelectedCaseId}
            />
            {selectedCase !== null && (
              <EvalCaseDetailDrawer
                evalCase={selectedCase}
                calls={selectedCaseCalls}
                rubrics={rubrics}
                onClose={() => setSelectedCaseId(null)}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
