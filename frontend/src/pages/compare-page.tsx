import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useRuns } from "@/hooks/useRuns";
import { useRunComparison } from "@/hooks/useRunComparison";
import { RunSelector } from "@/components/compare/run-selector";
import { ConfigDiffViewer } from "@/components/compare/config-diff-viewer";
import { MetricOverlayChart } from "@/components/compare/metric-overlay-chart";
import { MetricComparisonTable } from "@/components/compare/metric-comparison-table";
import { ArtifactComparisonPanel } from "@/components/compare/artifact-comparison-panel";
import { OutputComparisonPanel } from "@/components/compare/output-comparison-panel";
import { ActivationComparisonPanel } from "@/components/compare/activation-comparison-panel";
import { AISummaryCard } from "@/components/compare/ai-summary-card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const OVERLAY_METRICS: ReadonlyArray<{ name: string; title: string }> = [
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

  const { compareData, runMetrics, isLoading, error } = useRunComparison({
    projectId,
    runIds: selectedRunIds,
  });

  if (!activeProjectId) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Select a project to compare runs.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="px-6 py-4 border-b">
        <h1 className="text-xl font-semibold mb-3">Compare Runs</h1>
        <RunSelector
          runs={runs}
          selectedRunIds={selectedRunIds}
          onSelectionChange={setSelectedRunIds}
        />
        {selectedRunIds.length > 0 && selectedRunIds.length < 2 && (
          <p className="mt-2 text-xs text-muted-foreground">Select at least 2 runs to compare.</p>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {selectedRunIds.length < 2 ? (
          <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
            {selectedRunIds.length === 0
              ? "Select 2 or more runs above to begin comparing."
              : "Select one more run to start the comparison."}
          </div>
        ) : error ? (
          <div className="p-6">
            <div className="rounded-md border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              Failed to load comparison data:{" "}
              {error instanceof Error ? error.message : "Unknown error"}
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
            Loading comparison…
          </div>
        ) : (
          <Tabs defaultValue="metrics" className="flex flex-col h-full">
            <div className="px-6 pt-4 border-b">
              <TabsList>
                <TabsTrigger value="metrics">Metrics</TabsTrigger>
                <TabsTrigger value="config">Config Diff</TabsTrigger>
                <TabsTrigger value="artifacts">Artifacts</TabsTrigger>
                <TabsTrigger value="output">Output</TabsTrigger>
                <TabsTrigger value="activations">Activations</TabsTrigger>
                <TabsTrigger value="ai">AI Summary</TabsTrigger>
              </TabsList>
            </div>

            <TabsContent value="metrics" className="flex-1 p-6 space-y-6 mt-0">
              <div className="grid grid-cols-2 gap-4">
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

              <div>
                <h2 className="text-sm font-medium mb-3">Final Metric Summary</h2>
                <MetricComparisonTable
                  runIds={selectedRunIds}
                  metricComparison={compareData?.metricComparison ?? {}}
                />
              </div>
            </TabsContent>

            <TabsContent value="config" className="flex-1 p-6 mt-0">
              <h2 className="text-sm font-medium mb-3">Configuration Differences</h2>
              <ConfigDiffViewer
                configDiff={compareData?.configDiff ?? {}}
                runIds={selectedRunIds}
              />
            </TabsContent>

            <TabsContent value="artifacts" className="flex-1 p-6 mt-0">
              <h2 className="text-sm font-medium mb-3">Artifact Summary</h2>
              <ArtifactComparisonPanel
                runIds={selectedRunIds}
                artifactComparison={compareData?.artifactComparison ?? {}}
              />
            </TabsContent>

            <TabsContent value="output" className="flex-1 p-6 mt-0">
              <h2 className="text-sm font-medium mb-3">Evaluation Output</h2>
              <OutputComparisonPanel
                runIds={selectedRunIds}
                metricComparison={compareData?.metricComparison ?? {}}
              />
            </TabsContent>

            <TabsContent value="activations" className="flex-1 p-6 mt-0">
              <h2 className="text-sm font-medium mb-3">Activation Comparison</h2>
              <ActivationComparisonPanel runIds={selectedRunIds} />
            </TabsContent>

            <TabsContent value="ai" className="flex-1 p-6 mt-0">
              <AISummaryCard runIds={selectedRunIds} projectId={projectId} />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </div>
  );
}
