import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import { useRunComparison } from "@/hooks/useRunComparison";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { RunSelector } from "@/components/compare/run-selector";
import { ConfigDiffViewer } from "@/components/compare/config-diff-viewer";
import { MetricOverlayChart } from "@/components/compare/metric-overlay-chart";
import { MetricComparisonTable } from "@/components/compare/metric-comparison-table";
import { ArtifactComparisonPanel } from "@/components/compare/artifact-comparison-panel";
import { OutputComparisonPanel } from "@/components/compare/output-comparison-panel";
import { ActivationComparisonPanel } from "@/components/compare/activation-comparison-panel";
import { AISummaryCard } from "@/components/compare/ai-summary-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface OverlayMetric {
  readonly name: string;
  readonly title: string;
}

const OVERLAY_METRICS: ReadonlyArray<OverlayMetric> = [
  { name: "train_loss", title: "Training Loss" },
  { name: "eval_loss", title: "Eval Loss" },
  { name: "learning_rate", title: "Learning Rate" },
  { name: "grad_norm", title: "Gradient Norm" },
];

export default function ComparePage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedRunIds, setSelectedRunIds] = React.useState<ReadonlyArray<string>>([]);

  const projectId = activeProjectId ?? "";
  const { data: runs = [] } = useRuns({ projectId });
  const isAnimationLocked = useLockEntered();

  const { compareData, runMetrics, isLoading, error } = useRunComparison({
    projectId,
    runIds: selectedRunIds,
  });

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
          Compare runs
        </h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">Select a project to compare runs.</p>
      </div>
    );
  }

  const enteredClass = isAnimationLocked ? "entered" : "";

  return (
    <div className="flex h-full flex-col gap-4 p-6">
      <header className={cn("enter enter-1", enteredClass)}>
        <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
          Compare runs
        </h1>
        <p className="mt-1 font-mono text-[11px] text-ink-3">overlay metrics · diff configs</p>
      </header>

      <div
        className={cn("grid gap-4 enter enter-2", enteredClass)}
        style={{ gridTemplateColumns: "220px 1fr" }}
      >
        <div className="min-w-0">
          <RunSelector
            runs={runs}
            selectedRunIds={selectedRunIds}
            onSelectionChange={setSelectedRunIds}
          />
        </div>

        <div className="flex min-w-0 flex-col gap-4">
          {selectedRunIds.length < 2 ? (
            <Card>
              <CardContent className="py-10 text-center font-mono text-[11px] text-ink-3">
                {selectedRunIds.length === 0
                  ? "Select 2 or more runs to begin comparing."
                  : "Select one more run to start the comparison."}
              </CardContent>
            </Card>
          ) : error ? (
            <Card>
              <CardContent className="py-6 text-center font-mono text-[11px] text-[color:var(--danger)]">
                Failed to load comparison data:{" "}
                {error instanceof Error ? error.message : "Unknown error"}
              </CardContent>
            </Card>
          ) : isLoading ? (
            <Card>
              <CardContent className="py-10 text-center font-mono text-[11px] text-ink-3">
                Loading comparison…
              </CardContent>
            </Card>
          ) : (
            <Tabs defaultValue="metrics" className="flex flex-col gap-3">
              <TabsList>
                <TabsTrigger value="metrics">Metrics</TabsTrigger>
                <TabsTrigger value="config">Config Diff</TabsTrigger>
                <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                <TabsTrigger value="output">Output</TabsTrigger>
                <TabsTrigger value="activations">Activations</TabsTrigger>
                <TabsTrigger value="ai">AI Summary</TabsTrigger>
              </TabsList>

              <TabsContent value="metrics" className="mt-0 flex flex-col gap-4">
                <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                  {OVERLAY_METRICS.map(({ name, title }) => (
                    <MetricOverlayChart
                      key={name}
                      runIds={selectedRunIds}
                      runMetrics={runMetrics}
                      metricName={name}
                      title={title}
                    />
                  ))}
                </div>
                <MetricComparisonTable
                  runIds={selectedRunIds}
                  metricComparison={compareData?.metricComparison ?? {}}
                />
              </TabsContent>

              <TabsContent value="config" className="mt-0">
                <ConfigDiffViewer
                  configDiff={compareData?.configDiff ?? {}}
                  runIds={selectedRunIds}
                />
              </TabsContent>

              <TabsContent value="artifacts" className="mt-0">
                <ArtifactComparisonPanel
                  runIds={selectedRunIds}
                  artifactComparison={compareData?.artifactComparison ?? {}}
                />
              </TabsContent>

              <TabsContent value="output" className="mt-0">
                <OutputComparisonPanel
                  runIds={selectedRunIds}
                  metricComparison={compareData?.metricComparison ?? {}}
                />
              </TabsContent>

              <TabsContent value="activations" className="mt-0">
                <ActivationComparisonPanel runIds={selectedRunIds} />
              </TabsContent>

              <TabsContent value="ai" className="mt-0">
                <AISummaryCard runIds={selectedRunIds} projectId={projectId} />
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </div>
  );
}
