import * as React from "react";
import { Loader2 } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useModelArchitecture, useLayerDetail } from "@/hooks/useModelArchitecture";
import { useCaptureActivations, useRequestFullTensor } from "@/hooks/useActivations";
import { useRuns } from "@/hooks/useRuns";
import { ArchFlow } from "@/components/weights/arch-flow";
import { LayerTree } from "@/components/weights/layer-tree";
import { LayerWeightHistory } from "@/components/weights/layer-weight-history";
import { LayerInspector } from "@/components/weights/layer-inspector";
import { ModuleSearchInput } from "@/components/weights/module-search-input";
import { LayerDetailDrawer } from "@/components/weights/layer-detail-drawer";
import { ParameterSummaryTable } from "@/components/weights/parameter-summary-table";
import { ActivationSampleSelector } from "@/components/weights/activation-sample-selector";
import { ActivationLayerSelector } from "@/components/weights/activation-layer-selector";
import { ActivationSummaryView } from "@/components/weights/activation-summary-view";
import { ActivationCheckpointCompare } from "@/components/weights/activation-checkpoint-compare";
import { RequestFullTensorButton } from "@/components/weights/request-full-tensor-button";
import { DeltaMagnitudeChart } from "@/components/weights/delta-magnitude-chart";
import { DeltaHeatmap } from "@/components/weights/delta-heatmap";
import { BeforeAfterSummary } from "@/components/weights/before-after-summary";
import { ExpertModeToggle } from "@/components/weights/expert-mode-toggle";
import { TensorEditor } from "@/components/weights/tensor-editor";
import { CheckpointBackupNotice } from "@/components/weights/checkpoint-backup-notice";
import { RevertButton } from "@/components/weights/revert-button";
import { FlowVisualization } from "@/components/weights/flow-visualization";
import { ArchitectureTree } from "@/components/weights/architecture-tree";
import { flattenToFlowColumns } from "@/lib/flatten-to-flow-columns";
import { NoProjectSelected } from "@/components/shared/no-project-selected";
import { CopyForAI } from "@/components/shared/copy-for-ai";
import { buildArchitecturePrompt } from "@/lib/ai-copy-prompts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RangePills } from "@/components/shared/range-pills";
import type { FlowMode } from "@/types/flow";
import type {
  ActivationSnapshotResponse,
  LayerNode,
  ModelArchitectureResponse,
  ParameterRow,
  WeightDelta,
} from "@/types/model";

type ParameterFilter = "all" | "trainable" | "frozen";
type SecondaryTab =
  | "parameters"
  | "activations"
  | "deltas"
  | "flow"
  | "expert"
  | "tree"
  | "weights";

const DEFAULT_INSPECTOR_STATS = { mean: 0.0002, std: 0.0186, max: 0.2431 } as const;

interface LayerSummary {
  readonly index: number;
  readonly attnStrength: number;
  readonly mlpStrength: number;
}

function flattenTreeToRows({
  node,
  path,
}: {
  node: LayerNode;
  path: string;
}): ReadonlyArray<ParameterRow> {
  const fullPath = path ? `${path}.${node.name}` : node.name;
  const rows: ParameterRow[] = [];
  if (node.params !== null && node.params > 0) {
    rows.push({
      path: fullPath,
      type: node.type,
      params: node.params,
      trainable: node.trainable,
      dtype: node.dtype,
    });
  }
  for (const child of node.children ?? []) {
    rows.push(...flattenTreeToRows({ node: child, path: fullPath }));
  }
  return rows;
}

function collectLeafLayerNames({
  node,
  path,
}: {
  node: LayerNode;
  path: string;
}): ReadonlyArray<string> {
  const fullPath = path ? `${path}.${node.name}` : node.name;
  const hasChildren = (node.children ?? []).length > 0;
  if (!hasChildren) return [fullPath];
  return (node.children ?? []).flatMap((child) =>
    collectLeafLayerNames({ node: child, path: fullPath }),
  );
}

function findLayerStackNode(node: LayerNode): LayerNode | null {
  for (const child of node.children ?? []) {
    const grandChildren = child.children ?? [];
    if (grandChildren.length >= 2) {
      const sameType = grandChildren.every((g) => g.type === grandChildren[0].type);
      if (sameType) return child;
    }
    const deeper = findLayerStackNode(child);
    if (deeper) return deeper;
  }
  return null;
}

function buildLayerSummaries({
  architecture,
}: {
  readonly architecture: ModelArchitectureResponse;
}): ReadonlyArray<LayerSummary> {
  const stack = findLayerStackNode(architecture.tree);
  const layerNodes = stack?.children ?? [];
  if (layerNodes.length === 0) {
    return Array.from({ length: 28 }, (_, i) => ({
      index: i,
      attnStrength: 0.55 + ((i * 17) % 40) / 100,
      mlpStrength: 0.35 + ((i * 23) % 50) / 100,
    }));
  }
  return layerNodes.map((layer, i) => {
    const attnChild = (layer.children ?? []).find((child) =>
      child.name.toLowerCase().includes("attn"),
    );
    const mlpChild = (layer.children ?? []).find(
      (child) =>
        child.name.toLowerCase().includes("mlp") || child.name.toLowerCase().includes("ff"),
    );
    const attnParams = attnChild?.params ?? 0;
    const mlpParams = mlpChild?.params ?? 0;
    const totalParams = Math.max(1, attnParams + mlpParams);
    return {
      index: i,
      attnStrength: attnParams > 0 ? 0.4 + (attnParams / totalParams) * 0.5 : 0.55,
      mlpStrength: mlpParams > 0 ? 0.4 + (mlpParams / totalParams) * 0.6 : 0.45,
    };
  });
}

function buildLayerPath({
  architecture,
  layerIndex,
}: {
  readonly architecture: ModelArchitectureResponse;
  readonly layerIndex: number;
}): string | null {
  const stack = findLayerStackNode(architecture.tree);
  const layerNodes = stack?.children ?? [];
  if (layerNodes.length === 0 || !stack) return null;
  const clamped = Math.min(Math.max(0, layerIndex), layerNodes.length - 1);
  return `${architecture.tree.name}.${stack.name}.${layerNodes[clamped].name}`;
}

function computeDeltas({
  snapshotA,
  snapshotB,
}: {
  snapshotA: ActivationSnapshotResponse;
  snapshotB: ActivationSnapshotResponse;
}): ReadonlyArray<WeightDelta> {
  const layerMapA = new Map(snapshotA.layers.map((l) => [l.layer_name, l]));
  return snapshotB.layers.flatMap((layerB) => {
    const layerA = layerMapA.get(layerB.layer_name);
    if (!layerA) return [];
    return [
      {
        layerName: layerB.layer_name,
        deltaMagnitude: Math.abs(layerB.tier1.mean - layerA.tier1.mean),
        meanBefore: layerA.tier1.mean,
        meanAfter: layerB.tier1.mean,
        stdBefore: layerA.tier1.std,
        stdAfter: layerB.tier1.std,
      },
    ];
  });
}

export default function WeightsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const projectId = activeProjectId ?? "";

  const [searchQuery, setSearchQuery] = React.useState("");
  const [selectedLayerIndex, setSelectedLayerIndex] = React.useState(0);
  const [selectedLayerName, setSelectedLayerName] = React.useState<string | null>(null);
  const [selectedLayerNames, setSelectedLayerNames] = React.useState<ReadonlyArray<string>>([]);
  const [sampleInput, setSampleInput] = React.useState("");
  const [capturedSnapshots, setCapturedSnapshots] = React.useState<
    ReadonlyArray<ActivationSnapshotResponse>
  >([]);
  const [compareIndexA, setCompareIndexA] = React.useState(0);
  const [compareIndexB, setCompareIndexB] = React.useState(1);
  const [isExpertMode, setIsExpertMode] = React.useState(false);
  const [paramFilter, setParamFilter] = React.useState<ParameterFilter>("all");
  const [flowMode, setFlowMode] = React.useState<FlowMode>("structural");
  const [flowSnapshotIndex, setFlowSnapshotIndex] = React.useState(0);
  const [secondaryTab, setSecondaryTab] = React.useState<SecondaryTab>("parameters");
  const [selectedWeightsRunId, setSelectedWeightsRunId] = React.useState<string | null>(null);
  const [selectedWeightLayerName, setSelectedWeightLayerName] = React.useState<string | null>(null);

  const { data: architecture, isLoading: isArchLoading } = useModelArchitecture({ projectId });
  const { data: runs = [] } = useRuns({ projectId });

  React.useEffect(() => {
    if (selectedWeightsRunId === null && runs.length > 0) {
      setSelectedWeightsRunId(runs[0].id);
    }
  }, [runs, selectedWeightsRunId]);

  React.useEffect(() => {
    setSelectedWeightLayerName(null);
  }, [selectedWeightsRunId]);

  const backendLayerName = React.useMemo((): string | null => {
    if (!selectedLayerName || !architecture) return null;
    const rootPrefix = `${architecture.tree.name}.`;
    if (selectedLayerName.startsWith(rootPrefix)) {
      return selectedLayerName.slice(rootPrefix.length);
    }
    return selectedLayerName;
  }, [selectedLayerName, architecture]);

  const { data: layerDetail, isLoading: isLayerLoading } = useLayerDetail({
    projectId,
    layerName: backendLayerName,
  });

  const captureActivations = useCaptureActivations({ projectId });
  const requestFullTensor = useRequestFullTensor({ projectId });

  const parameterRows: ReadonlyArray<ParameterRow> = React.useMemo(() => {
    if (!architecture) return [];
    return flattenTreeToRows({ node: architecture.tree, path: "" });
  }, [architecture]);

  const availableLayerNames: ReadonlyArray<string> = React.useMemo(() => {
    if (!architecture) return [];
    return collectLeafLayerNames({ node: architecture.tree, path: "" });
  }, [architecture]);

  const flowColumns = React.useMemo(() => {
    if (!architecture) return [];
    return flattenToFlowColumns({ tree: architecture.tree });
  }, [architecture]);

  const flowLayerNames = React.useMemo(
    () => flowColumns.flatMap((col) => col.nodes.map((n) => n.fullPath)),
    [flowColumns],
  );

  const flowActivationSnapshot = React.useMemo(() => {
    if (capturedSnapshots.length === 0) return null;
    const idx = Math.min(flowSnapshotIndex, capturedSnapshots.length - 1);
    return capturedSnapshots[idx] ?? null;
  }, [capturedSnapshots, flowSnapshotIndex]);

  const deltas: ReadonlyArray<WeightDelta> = React.useMemo(() => {
    const snapshotA = capturedSnapshots[compareIndexA];
    const snapshotB = capturedSnapshots[compareIndexB];
    if (!snapshotA || !snapshotB) return [];
    return computeDeltas({ snapshotA, snapshotB });
  }, [capturedSnapshots, compareIndexA, compareIndexB]);

  const layerSummaries = React.useMemo(
    () => (architecture ? buildLayerSummaries({ architecture }) : []),
    [architecture],
  );

  const selectedLayerPath = React.useMemo(
    () => (architecture ? buildLayerPath({ architecture, layerIndex: selectedLayerIndex }) : null),
    [architecture, selectedLayerIndex],
  );

  const selectedLayerLabel = selectedLayerPath
    ? `${selectedLayerPath.split(".").slice(-2).join(".")} · attn.q_proj`
    : "attn.q_proj";

  const handleToggleLayer = (layerName: string): void => {
    setSelectedLayerNames((prev) => {
      const set = new Set(prev);
      if (set.has(layerName)) {
        set.delete(layerName);
      } else {
        set.add(layerName);
      }
      return Array.from(set);
    });
  };

  const handleCapture = (): void => {
    captureActivations.mutate(
      { layerNames: selectedLayerNames, sampleInput },
      {
        onSuccess: (snapshot) => {
          setCapturedSnapshots((prev) => [...prev, snapshot]);
        },
      },
    );
  };

  const handleFlowCapture = (): void => {
    captureActivations.mutate(
      { layerNames: flowLayerNames, sampleInput },
      {
        onSuccess: (snapshot) => {
          setCapturedSnapshots((prev) => {
            setFlowSnapshotIndex(prev.length);
            return [...prev, snapshot];
          });
        },
      },
    );
  };

  const handleRequestFullTensor = (snapshotId: string): void => {
    requestFullTensor.mutate({ snapshotId, layerNames: null });
  };

  const inspectorStats = React.useMemo(() => {
    const latest = capturedSnapshots[capturedSnapshots.length - 1];
    if (!latest || latest.layers.length === 0) return DEFAULT_INSPECTOR_STATS;
    const layer = latest.layers[0];
    return { mean: layer.tier1.mean, std: layer.tier1.std, max: layer.tier1.max };
  }, [capturedSnapshots]);

  if (!activeProjectId) {
    return (
      <NoProjectSelected
        pageTitle="Weights & Architecture"
        description="Select a project on the Dashboard to explore its model weights and architecture."
      />
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-hairline px-6">
        <div>
          <h1 className="font-mono text-[16px] font-semibold tracking-tight text-ink-1">
            Weights &amp; Architecture
          </h1>
          {architecture && (
            <p className="font-mono text-[11px] text-ink-3">
              {architecture.architecture_name} · {(architecture.total_parameters / 1e9).toFixed(2)}B
              params · inspect by layer
            </p>
          )}
        </div>
        {architecture && (
          <CopyForAI buildPrompt={() => buildArchitecturePrompt({ architecture })} />
        )}
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {isArchLoading && (
          <div className="flex items-center gap-2 font-mono text-[11px] text-ink-3">
            <Loader2 className="size-3 animate-spin" aria-hidden="true" />
            Loading model architecture…
          </div>
        )}

        {!isArchLoading && !architecture && (
          <div className="py-12 text-center font-mono text-[11px] text-ink-3">
            No model resolved for this project. Resolve a model from the Models screen first.
          </div>
        )}

        {architecture && (
          <>
            <ArchFlow
              architecture={architecture}
              selectedLayerIndex={selectedLayerIndex}
              onSelectLayer={setSelectedLayerIndex}
              dtype="bf16"
            />

            <LayerInspector
              layers={layerSummaries}
              selectedLayerIndex={selectedLayerIndex}
              onSelectLayer={setSelectedLayerIndex}
              selectedLayerLabel={selectedLayerLabel}
              stats={inspectorStats}
            />

            <Tabs
              value={secondaryTab}
              onValueChange={(value) => setSecondaryTab(value as SecondaryTab)}
            >
              <TabsList>
                <TabsTrigger value="parameters">Parameters</TabsTrigger>
                <TabsTrigger value="activations">Activations</TabsTrigger>
                <TabsTrigger value="deltas">Deltas</TabsTrigger>
                <TabsTrigger value="flow">Flow</TabsTrigger>
                <TabsTrigger value="tree">Tree</TabsTrigger>
                <TabsTrigger value="weights">Weights</TabsTrigger>
                <TabsTrigger value="expert">Expert edit</TabsTrigger>
              </TabsList>

              <TabsContent value="parameters">
                <Card>
                  <CardHeader>
                    <CardTitle>Parameter summary</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ParameterSummaryTable
                      rows={parameterRows}
                      filter={paramFilter}
                      onFilterChange={setParamFilter}
                    />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="tree">
                <Card>
                  <CardHeader>
                    <CardTitle>Architecture tree</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <ModuleSearchInput value={searchQuery} onChange={setSearchQuery} />
                    <ArchitectureTree
                      tree={architecture.tree}
                      onSelectLayer={setSelectedLayerName}
                      searchQuery={searchQuery}
                    />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="activations">
                <Card>
                  <CardHeader>
                    <CardTitle>Activations</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ActivationSampleSelector
                      sampleInput={sampleInput}
                      onSampleInputChange={setSampleInput}
                      onCapture={handleCapture}
                      isCapturing={captureActivations.isPending}
                      hasLayersSelected={selectedLayerNames.length > 0}
                    />

                    <ActivationLayerSelector
                      availableLayers={availableLayerNames}
                      selectedLayers={selectedLayerNames}
                      onToggleLayer={handleToggleLayer}
                    />

                    {capturedSnapshots.length > 0 && (
                      <div className="space-y-4">
                        <div className="border-t border-hairline pt-4">
                          <h3 className="mb-3 font-mono text-[12px] font-medium text-ink-1">
                            Latest snapshot ({capturedSnapshots.length} captured)
                          </h3>
                          <ActivationSummaryView
                            snapshot={capturedSnapshots[capturedSnapshots.length - 1]!}
                          />
                          <div className="mt-3">
                            <RequestFullTensorButton
                              snapshotId={capturedSnapshots[capturedSnapshots.length - 1]!.id}
                              isRequesting={requestFullTensor.isPending}
                              onRequest={handleRequestFullTensor}
                            />
                          </div>
                        </div>

                        {capturedSnapshots.length >= 2 && (
                          <div className="space-y-3 border-t border-hairline pt-4">
                            <div className="flex items-center gap-3">
                              <h3 className="font-mono text-[12px] font-medium text-ink-1">
                                Compare snapshots
                              </h3>
                              <Select
                                value={String(compareIndexA)}
                                onValueChange={(value) => setCompareIndexA(Number(value))}
                              >
                                <SelectTrigger className="h-7 w-auto min-w-24 text-[11px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {capturedSnapshots.map((snap, idx) => (
                                    <SelectItem key={snap.id} value={String(idx)}>
                                      {new Date(snap.created_at).toLocaleTimeString()}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                              <span className="font-mono text-[11px] text-ink-3">vs</span>
                              <Select
                                value={String(compareIndexB)}
                                onValueChange={(value) => setCompareIndexB(Number(value))}
                              >
                                <SelectTrigger className="h-7 w-auto min-w-24 text-[11px]">
                                  <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                  {capturedSnapshots.map((snap, idx) => (
                                    <SelectItem key={snap.id} value={String(idx)}>
                                      {new Date(snap.created_at).toLocaleTimeString()}
                                    </SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <ActivationCheckpointCompare
                              snapshotA={capturedSnapshots[compareIndexA]!}
                              snapshotB={capturedSnapshots[compareIndexB]!}
                            />
                          </div>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="deltas">
                <Card>
                  <CardHeader>
                    <CardTitle>Deltas</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {capturedSnapshots.length < 2 ? (
                      <div className="py-8 text-center font-mono text-[11px] text-ink-3">
                        Capture at least two activation snapshots in the Activations tab to compare
                        weight deltas.
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-[11px] text-ink-3">Comparing:</span>
                          <Select
                            value={String(compareIndexA)}
                            onValueChange={(value) => setCompareIndexA(Number(value))}
                          >
                            <SelectTrigger className="h-7 w-auto min-w-24 text-[11px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {capturedSnapshots.map((snap, idx) => (
                                <SelectItem key={snap.id} value={String(idx)}>
                                  {new Date(snap.created_at).toLocaleTimeString()}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <span className="font-mono text-[11px] text-ink-3">→</span>
                          <Select
                            value={String(compareIndexB)}
                            onValueChange={(value) => setCompareIndexB(Number(value))}
                          >
                            <SelectTrigger className="h-7 w-auto min-w-24 text-[11px]">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              {capturedSnapshots.map((snap, idx) => (
                                <SelectItem key={snap.id} value={String(idx)}>
                                  {new Date(snap.created_at).toLocaleTimeString()}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <section className="space-y-2">
                          <h3 className="font-mono text-[12px] font-medium text-ink-1">
                            Delta magnitude by layer
                          </h3>
                          <DeltaMagnitudeChart deltas={deltas} />
                        </section>
                        <section className="space-y-2">
                          <h3 className="font-mono text-[12px] font-medium text-ink-1">Heatmap</h3>
                          <DeltaHeatmap deltas={deltas} />
                        </section>
                        <section className="space-y-2">
                          <h3 className="font-mono text-[12px] font-medium text-ink-1">
                            Before / after summary
                          </h3>
                          <BeforeAfterSummary deltas={deltas} />
                        </section>
                      </>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="flow">
                <Card>
                  <CardHeader>
                    <CardTitle>Flow</CardTitle>
                    <RangePills<FlowMode>
                      options={[
                        { value: "structural", label: "structural" },
                        { value: "activation", label: "activation" },
                      ]}
                      value={flowMode}
                      onChange={setFlowMode}
                    />
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {flowMode === "activation" && (
                      <div className="space-y-3">
                        <ActivationSampleSelector
                          sampleInput={sampleInput}
                          onSampleInputChange={setSampleInput}
                          onCapture={handleFlowCapture}
                          isCapturing={captureActivations.isPending}
                          hasLayersSelected={flowLayerNames.length > 0}
                        />
                        {capturedSnapshots.length > 1 && (
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-[11px] text-ink-3">Snapshot:</span>
                            <Select
                              value={String(flowSnapshotIndex)}
                              onValueChange={(value) => setFlowSnapshotIndex(Number(value))}
                            >
                              <SelectTrigger className="h-7 w-auto min-w-24 text-[11px]">
                                <SelectValue />
                              </SelectTrigger>
                              <SelectContent>
                                {capturedSnapshots.map((snap, idx) => (
                                  <SelectItem key={snap.id} value={String(idx)}>
                                    {new Date(snap.created_at).toLocaleTimeString()}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}
                      </div>
                    )}
                    <FlowVisualization
                      columns={flowColumns}
                      onSelectNode={setSelectedLayerName}
                      mode={flowMode}
                      activationSnapshot={flowActivationSnapshot}
                      onCaptureRequest={handleFlowCapture}
                      isCapturing={captureActivations.isPending}
                      sampleInput={sampleInput}
                    />
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="weights">
                <Card>
                  <CardHeader>
                    <CardTitle>Per-layer weights</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {runs.length === 0 ? (
                      <div className="py-8 text-center font-mono text-[11px] text-ink-3">
                        No runs recorded for this project yet. Start a training run to populate
                        per-layer weight snapshots.
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-[11px] text-ink-3">Run:</span>
                          <Select
                            value={selectedWeightsRunId ?? ""}
                            onValueChange={(value) => setSelectedWeightsRunId(value)}
                          >
                            <SelectTrigger className="h-7 w-[260px] text-[11px]">
                              <SelectValue placeholder="Select training run" />
                            </SelectTrigger>
                            <SelectContent>
                              {runs.map((run) => (
                                <SelectItem key={run.id} value={run.id}>
                                  <span className="font-mono text-xs">{run.id.slice(0, 8)}</span>
                                  <span className="ml-2 text-xs text-ink-3">{run.status}</span>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        {selectedWeightsRunId ? (
                          <div className="grid grid-cols-[1fr_1.2fr] gap-4">
                            <LayerTree
                              projectId={projectId}
                              runId={selectedWeightsRunId}
                              selectedLayer={selectedWeightLayerName}
                              onSelectLayer={setSelectedWeightLayerName}
                            />
                            {selectedWeightLayerName !== null ? (
                              <LayerWeightHistory
                                projectId={projectId}
                                runId={selectedWeightsRunId}
                                layerName={selectedWeightLayerName}
                              />
                            ) : (
                              <div className="font-mono text-[11px] text-ink-3">
                                Select a layer to view weight history.
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="font-mono text-[11px] text-ink-3">
                            Select a run to view its weights.
                          </div>
                        )}
                      </>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>

              <TabsContent value="expert">
                <Card>
                  <CardHeader>
                    <CardTitle>Expert edit</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <ExpertModeToggle isEnabled={isExpertMode} onToggle={setIsExpertMode} />
                    {isExpertMode && (
                      <>
                        <CheckpointBackupNotice />
                        <TensorEditor
                          layerDetail={layerDetail ?? null}
                          isExpertMode={isExpertMode}
                        />
                        <RevertButton
                          onRevert={() => undefined}
                          isReverting={false}
                          isDisabled={true}
                        />
                      </>
                    )}
                  </CardContent>
                </Card>
              </TabsContent>
            </Tabs>

            <LayerDetailDrawer
              layerDetail={layerDetail ?? null}
              isLoading={isLayerLoading && selectedLayerName !== null}
              onClose={() => setSelectedLayerName(null)}
            />
          </>
        )}
      </div>
    </div>
  );
}
