import * as React from "react";
import { useAppStore } from "@/stores/app-store";
import { useModelArchitecture, useLayerDetail } from "@/hooks/useModelArchitecture";
import { useCaptureActivations, useRequestFullTensor } from "@/hooks/useActivations";
import { ArchitectureTree } from "@/components/weights/architecture-tree";
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
import { flattenToFlowColumns } from "@/lib/flatten-to-flow-columns";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { FlowMode } from "@/types/flow";
import type {
  ActivationSnapshotResponse,
  LayerNode,
  ParameterRow,
  WeightDelta,
} from "@/types/model";

type ParameterFilter = "all" | "trainable" | "frozen";

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

  if (!hasChildren) {
    return [fullPath];
  }

  return (node.children ?? []).flatMap((child) =>
    collectLeafLayerNames({ node: child, path: fullPath }),
  );
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

  const [searchQuery, setSearchQuery] = React.useState("");
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

  const projectId = activeProjectId ?? "";

  const { data: architecture, isLoading: isArchLoading } = useModelArchitecture({ projectId });
  const { data: layerDetail, isLoading: isLayerLoading } = useLayerDetail({
    projectId,
    layerName: selectedLayerName,
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

  const handleToggleLayer = (layerName: string): void => {
    setSelectedLayerNames((prev) => {
      const s = new Set(prev);
      if (s.has(layerName)) {
        s.delete(layerName);
      } else {
        s.add(layerName);
      }
      return Array.from(s);
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

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="text-xl font-semibold mb-2">Weights & Architecture</h1>
        <p className="text-sm text-muted-foreground">Select a project to explore its model.</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Weights & Architecture</h1>
          {architecture && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {architecture.architecture_name} — {(architecture.total_parameters / 1e9).toFixed(2)}B
              params
            </p>
          )}
        </div>
      </div>

      {isArchLoading && (
        <div className="text-sm text-muted-foreground">Loading model architecture…</div>
      )}

      {!isArchLoading && !architecture && (
        <div className="py-12 text-center text-sm text-muted-foreground">
          No model resolved for this project. Resolve a model from the Models screen first.
        </div>
      )}

      {architecture && (
        <>
          <Tabs defaultValue="architecture">
            <TabsList>
              <TabsTrigger value="architecture">Architecture</TabsTrigger>
              <TabsTrigger value="parameters">Parameters</TabsTrigger>
              <TabsTrigger value="activations">Activations</TabsTrigger>
              <TabsTrigger value="deltas">Deltas</TabsTrigger>
              <TabsTrigger value="flow">Flow</TabsTrigger>
              <TabsTrigger value="expert">Expert Edit</TabsTrigger>
            </TabsList>

            <TabsContent value="architecture" className="mt-4 space-y-3">
              <ModuleSearchInput value={searchQuery} onChange={setSearchQuery} />
              <ArchitectureTree
                tree={architecture.tree}
                onSelectLayer={setSelectedLayerName}
                searchQuery={searchQuery}
              />
              <LayerDetailDrawer
                layerDetail={layerDetail ?? null}
                isLoading={isLayerLoading && selectedLayerName !== null}
                onClose={() => setSelectedLayerName(null)}
              />
            </TabsContent>

            <TabsContent value="parameters" className="mt-4">
              <ParameterSummaryTable
                rows={parameterRows}
                filter={paramFilter}
                onFilterChange={setParamFilter}
              />
            </TabsContent>

            <TabsContent value="activations" className="mt-4 space-y-4">
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
                  <div className="border-t pt-4">
                    <h3 className="text-sm font-medium mb-3">
                      Latest Snapshot ({capturedSnapshots.length} captured)
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
                    <div className="border-t pt-4 space-y-3">
                      <div className="flex items-center gap-3">
                        <h3 className="text-sm font-medium">Compare Snapshots</h3>
                        <select
                          value={compareIndexA}
                          onChange={(e) => setCompareIndexA(Number(e.target.value))}
                          className="text-xs border rounded px-2 py-1 bg-background"
                        >
                          {capturedSnapshots.map((snap, idx) => (
                            <option key={snap.id} value={idx}>
                              {new Date(snap.created_at).toLocaleTimeString()}
                            </option>
                          ))}
                        </select>
                        <span className="text-xs text-muted-foreground">vs</span>
                        <select
                          value={compareIndexB}
                          onChange={(e) => setCompareIndexB(Number(e.target.value))}
                          className="text-xs border rounded px-2 py-1 bg-background"
                        >
                          {capturedSnapshots.map((snap, idx) => (
                            <option key={snap.id} value={idx}>
                              {new Date(snap.created_at).toLocaleTimeString()}
                            </option>
                          ))}
                        </select>
                      </div>
                      <ActivationCheckpointCompare
                        snapshotA={capturedSnapshots[compareIndexA]!}
                        snapshotB={capturedSnapshots[compareIndexB]!}
                      />
                    </div>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="deltas" className="mt-4 space-y-4">
              {capturedSnapshots.length < 2 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  Capture at least two activation snapshots in the Activations tab to compare weight
                  deltas.
                </div>
              ) : (
                <>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-muted-foreground">Comparing:</span>
                    <select
                      value={compareIndexA}
                      onChange={(e) => setCompareIndexA(Number(e.target.value))}
                      className="text-xs border rounded px-2 py-1 bg-background"
                    >
                      {capturedSnapshots.map((snap, idx) => (
                        <option key={snap.id} value={idx}>
                          {new Date(snap.created_at).toLocaleTimeString()}
                        </option>
                      ))}
                    </select>
                    <span className="text-xs text-muted-foreground">→</span>
                    <select
                      value={compareIndexB}
                      onChange={(e) => setCompareIndexB(Number(e.target.value))}
                      className="text-xs border rounded px-2 py-1 bg-background"
                    >
                      {capturedSnapshots.map((snap, idx) => (
                        <option key={snap.id} value={idx}>
                          {new Date(snap.created_at).toLocaleTimeString()}
                        </option>
                      ))}
                    </select>
                  </div>

                  <section className="space-y-2">
                    <h3 className="text-sm font-medium">Delta Magnitude by Layer</h3>
                    <DeltaMagnitudeChart deltas={deltas} />
                  </section>

                  <section className="space-y-2">
                    <h3 className="text-sm font-medium">Heatmap</h3>
                    <DeltaHeatmap deltas={deltas} />
                  </section>

                  <section className="space-y-2">
                    <h3 className="text-sm font-medium">Before / After Summary</h3>
                    <BeforeAfterSummary deltas={deltas} />
                  </section>
                </>
              )}
            </TabsContent>

            <TabsContent value="flow" className="mt-4 space-y-4">
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setFlowMode("structural")}
                  className={[
                    "px-3 py-1.5 text-xs font-medium rounded transition-colors",
                    flowMode === "structural"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80",
                  ].join(" ")}
                >
                  Structural
                </button>
                <button
                  onClick={() => setFlowMode("activation")}
                  className={[
                    "px-3 py-1.5 text-xs font-medium rounded transition-colors",
                    flowMode === "activation"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted text-muted-foreground hover:bg-muted/80",
                  ].join(" ")}
                >
                  Activation
                </button>
              </div>

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
                      <span className="text-xs text-muted-foreground">Snapshot:</span>
                      <select
                        value={flowSnapshotIndex}
                        onChange={(e) => setFlowSnapshotIndex(Number(e.target.value))}
                        className="text-xs border rounded px-2 py-1 bg-background"
                      >
                        {capturedSnapshots.map((snap, idx) => (
                          <option key={snap.id} value={idx}>
                            {new Date(snap.created_at).toLocaleTimeString()}
                          </option>
                        ))}
                      </select>
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
              <LayerDetailDrawer
                layerDetail={layerDetail ?? null}
                isLoading={isLayerLoading && selectedLayerName !== null}
                onClose={() => setSelectedLayerName(null)}
              />
            </TabsContent>

            <TabsContent value="expert" className="mt-4 space-y-4">
              <ExpertModeToggle isEnabled={isExpertMode} onToggle={setIsExpertMode} />

              {isExpertMode && (
                <>
                  <CheckpointBackupNotice />
                  <TensorEditor layerDetail={layerDetail ?? null} isExpertMode={isExpertMode} />
                  <RevertButton onRevert={() => {}} isReverting={false} isDisabled={true} />
                </>
              )}
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );
}
