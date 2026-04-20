import * as React from "react";
import { Play } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import { useCreateEvalRun, useEvalRun, useEvalRuns, useRubrics } from "@/hooks/useEval";
import { useEvalStream } from "@/hooks/useEvalStream";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { useToast } from "@/hooks/use-toast";
import type { EvalCall } from "@/types/eval";
import { EvalRunList } from "@/components/eval/eval-run-list";
import { EvalRunHeader } from "@/components/eval/eval-run-header";
import { EvalTriggerPanel } from "@/components/eval/eval-trigger-panel";
import { EvalCaseTable } from "@/components/eval/eval-case-table";
import { EvalCaseDetailDrawer } from "@/components/eval/eval-case-detail-drawer";
import { EvalExportButton } from "@/components/eval/eval-export-button";
import { CostWarningBanner } from "@/components/eval/cost-warning-banner";
import { BenchmarkRow } from "@/components/eval/benchmark-row";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SliderRow } from "@/components/shared/slider-row";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";

interface BenchmarkEntry {
  readonly name: string;
  readonly basePercent: number;
  readonly ftPercent: number;
  readonly deltaPercent: number;
}

// TODO(P8): benchmark data is stubbed until a benchmarks endpoint exists -- remove when wired
const BENCHMARK_STUB: ReadonlyArray<BenchmarkEntry> = [
  { name: "MMLU (5-shot)", basePercent: 53.2, ftPercent: 58.1, deltaPercent: 4.9 },
  { name: "HellaSwag", basePercent: 75.1, ftPercent: 76.4, deltaPercent: 1.3 },
  { name: "ARC-Challenge", basePercent: 42.8, ftPercent: 48.6, deltaPercent: 5.8 },
  { name: "GSM8k", basePercent: 12.4, ftPercent: 28.2, deltaPercent: 15.8 },
  { name: "HumanEval (pass@1)", basePercent: 18.9, ftPercent: 23.2, deltaPercent: 4.3 },
  { name: "TruthfulQA", basePercent: 38.1, ftPercent: 41.0, deltaPercent: 2.9 },
  { name: "Custom:support-v2", basePercent: 61.2, ftPercent: 82.4, deltaPercent: 21.2 },
];

// TODO(P8): playground output is stubbed until a generation endpoint exists -- remove when wired
const PLAYGROUND_DEFAULT_PROMPT = "Explain LoRA fine-tuning like I'm a senior ML engineer.";
const PLAYGROUND_DEFAULT_BASE_OUTPUT =
  "LoRA is a parameter-efficient method that adds trainable rank-decomposition matrices to attention layers while freezing the base weights.";
const PLAYGROUND_DEFAULT_FT_OUTPUT =
  "LoRA injects two trainable matrices B ∈ R^{d×r} and A ∈ R^{r×k} into each target module so ΔW = BA. Only B,A are updated — typically < 1% of params — while the base W stays frozen in bf16.";

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

function BenchmarksTab(): React.JSX.Element {
  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle>Base vs Fine-tuned</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[color:var(--iris-4)]">
          avg Δ +8.0
        </span>
      </CardHeader>
      <div>
        {BENCHMARK_STUB.map((entry) => (
          <BenchmarkRow
            key={entry.name}
            name={entry.name}
            basePercent={entry.basePercent}
            ftPercent={entry.ftPercent}
            deltaPercent={entry.deltaPercent}
          />
        ))}
      </div>
    </Card>
  );
}

function PlaygroundTab(): React.JSX.Element {
  const { toast } = useToast();
  const [prompt, setPrompt] = React.useState<string>(PLAYGROUND_DEFAULT_PROMPT);
  const [temperature, setTemperature] = React.useState<number>(0.7);
  const [topP, setTopP] = React.useState<number>(0.95);
  const [maxTokens, setMaxTokens] = React.useState<number>(256);

  const handleGenerate = (): void => {
    toast({
      title: "Playground preview",
      description: "Side-by-side generation is not yet wired to a live endpoint.",
    });
  };

  return (
    <div className="grid gap-4" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.2fr)" }}>
      <Card>
        <CardHeader className="py-3">
          <CardTitle>Prompt</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Textarea
            mono
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={6}
            aria-label="Playground prompt"
          />
          <SliderRow
            label="Temperature"
            value={temperature}
            min={0}
            max={2}
            step={0.05}
            formatValue={(value) => value.toFixed(2)}
            onChange={setTemperature}
          />
          <SliderRow
            label="top-p"
            value={topP}
            min={0}
            max={1}
            step={0.01}
            formatValue={(value) => value.toFixed(2)}
            onChange={setTopP}
          />
          <SliderRow
            label="Max tokens"
            value={maxTokens}
            min={32}
            max={2048}
            step={32}
            formatValue={(value) => value.toFixed(0)}
            onChange={setMaxTokens}
          />
          <Button variant="primary" size="sm" onClick={handleGenerate}>
            <Play aria-hidden="true" />
            Generate both
          </Button>
        </CardContent>
      </Card>

      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader className="py-3">
            <div className="flex flex-col gap-1">
              <CardTitle className="flex items-center gap-2">
                <span>base model</span>
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                  BASE
                </span>
              </CardTitle>
              <span className="font-mono text-[10.5px] text-ink-3">312ms · 84 tok</span>
            </div>
          </CardHeader>
          <CardContent className="min-h-[120px] font-sans text-[13.5px] leading-[1.6] text-ink-1">
            {PLAYGROUND_DEFAULT_BASE_OUTPUT}
          </CardContent>
        </Card>

        <Card className="iris-glow">
          <CardHeader className="py-3">
            <div className="flex flex-col gap-1">
              <CardTitle className="flex items-center gap-2">
                <span>fine-tuned</span>
                <Badge variant="iris" dot={false}>
                  FINE-TUNED
                </Badge>
              </CardTitle>
              <span className="font-mono text-[10.5px] text-ink-3">418ms · 128 tok</span>
            </div>
          </CardHeader>
          <CardContent className="min-h-[120px] font-sans text-[13.5px] leading-[1.6] text-ink-1">
            {PLAYGROUND_DEFAULT_FT_OUTPUT}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function EvalPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const isAnimationLocked = useLockEntered();

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
      },
    );
  }, [createEvalRunMutation, selectedTrainingRunId, selectedVersionIds, maxCostUsd]);

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
            benchmarks · side-by-side generations · custom suites
          </p>
        </div>
        {evalRunDetail && <EvalExportButton evalRunDetail={evalRunDetail} />}
      </header>

      <Tabs
        defaultValue="benchmarks"
        className={cn("flex flex-col gap-4 enter enter-2", enteredClass)}
      >
        <TabsList>
          <TabsTrigger value="benchmarks">Benchmarks</TabsTrigger>
          <TabsTrigger value="playground">Playground</TabsTrigger>
          <TabsTrigger value="custom">Custom suites</TabsTrigger>
        </TabsList>

        <TabsContent value="benchmarks" className="mt-0">
          <BenchmarksTab />
        </TabsContent>

        <TabsContent value="playground" className="mt-0">
          <PlaygroundTab />
        </TabsContent>

        <TabsContent value="custom" className="mt-0 flex flex-col gap-4">
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
        </TabsContent>
      </Tabs>
    </div>
  );
}
