import * as React from "react";
import { Eye, Plus } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useDatasetProfile, useResolveDataset } from "@/hooks/useDatasetProfile";
import { useDatasetSamples, usePreviewTransform } from "@/hooks/useDatasetSamples";
import type {
  DatasetProfile,
  DatasetResolveRequest,
  PreviewTransformResponse,
} from "@/types/dataset";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DatasetSourceSelector } from "@/components/dataset/dataset-source-selector";
import { DatasetIdInput } from "@/components/dataset/dataset-id-input";
import { FormatSelector } from "@/components/dataset/format-selector";
import { FieldMappingEditor } from "@/components/dataset/field-mapping-editor";
import { DatasetSubsetSelector } from "@/components/dataset/dataset-subset-selector";
import { DatasetResolveButton } from "@/components/dataset/dataset-resolve-button";
import { SplitInfoCards } from "@/components/dataset/split-info-cards";
import { SamplePreview } from "@/components/dataset/sample-preview";
import { QualityWarnings } from "@/components/dataset/quality-warnings";
import { PreprocessingPreview } from "@/components/dataset/preprocessing-preview";
import { TokenHistogram } from "@/components/dataset/token-histogram";
import { StatusDot } from "@/components/shared/status-dot";
import { RunRow, RunRowCell } from "@/components/shared/run-row";
import { KVList } from "@/components/shared/kv-list";
import { CodeBlock } from "@/components/shared/code-block";
import { Callout } from "@/components/shared/callout";

type DialogKind = "add" | "validate" | "inspect" | null;

interface LibraryEntry {
  readonly name: string;
  readonly format: string;
  readonly rows: string;
  readonly size: string;
  readonly isFrozen: boolean;
  readonly isActive: boolean;
}

const LIBRARY_ROW_COLUMNS = "18px minmax(0,1fr) 72px 64px 32px";

const LIBRARY_ROW_STYLE: React.CSSProperties = {
  gridTemplateColumns: LIBRARY_ROW_COLUMNS,
};

function formatRowCount(count: number): string {
  return count.toLocaleString();
}

function estimateSizeLabel(totalRows: number): string {
  if (totalRows <= 0) return "—";
  if (totalRows >= 1_000_000) return `${(totalRows / 1_000_000).toFixed(1)}M rows`;
  if (totalRows >= 1_000) return `${(totalRows / 1_000).toFixed(0)}k rows`;
  return `${totalRows} rows`;
}

function buildLibraryEntries({
  profile,
}: {
  readonly profile: DatasetProfile | null;
}): ReadonlyArray<LibraryEntry> {
  if (!profile) return [];
  return [
    {
      name: profile.datasetId,
      format: profile.format,
      rows: formatRowCount(profile.totalRows),
      size: estimateSizeLabel(profile.totalRows),
      isFrozen: false,
      isActive: true,
    },
  ];
}

export default function DatasetsPage(): React.JSX.Element {
  const { activeProjectId, datasetForm, setDatasetForm } = useAppStore();
  const [previewResponse, setPreviewResponse] = React.useState<PreviewTransformResponse | null>(
    null,
  );
  const [activeDialog, setActiveDialog] = React.useState<DialogKind>(null);

  const projectId = activeProjectId ?? "";
  const {
    data: profile,
    isLoading: isProfileLoading,
    error: profileError,
  } = useDatasetProfile({ projectId });

  const resolveDataset = useResolveDataset({ projectId });

  const { data: samplesResponse, isLoading: isSamplesLoading } = useDatasetSamples({
    projectId,
    enabled: profile !== undefined,
  });

  const previewTransform = usePreviewTransform({ projectId });

  React.useEffect(() => {
    if (profile && !datasetForm.datasetId) {
      setDatasetForm({
        source: profile.source,
        datasetId: profile.datasetId,
        format: profile.format,
      });
    }
  }, [profile, datasetForm.datasetId, setDatasetForm]);

  const handleResolve = (): void => {
    const request: DatasetResolveRequest = {
      source: datasetForm.source,
      datasetId: datasetForm.datasetId,
      subset: null,
      trainSplit: datasetForm.trainSplit,
      evalSplit: datasetForm.evalSplit,
      format: datasetForm.format,
      formatMapping:
        Object.keys(datasetForm.formatMapping).length > 0 ? datasetForm.formatMapping : null,
      maxSamples: datasetForm.maxSamples,
      trainRatio: datasetForm.trainRatio,
      valRatio: datasetForm.valRatio,
      testRatio: datasetForm.testRatio,
    };
    resolveDataset.mutate(request, {
      onSuccess: (resolvedProfile) => {
        const { train, validation, test } = resolvedProfile.splitCounts;
        const total = resolvedProfile.totalRows;
        if (total === 0) return;
        setDatasetForm({
          trainRatio: train !== null ? Math.round((train / total) * 100) : null,
          valRatio: validation !== null ? Math.round((validation / total) * 100) : null,
          testRatio: test !== null ? Math.round((test / total) * 100) : null,
        });
      },
    });
  };

  const handlePreviewTransform = (): void => {
    previewTransform.mutate(
      {
        format: datasetForm.format,
        formatMapping:
          Object.keys(datasetForm.formatMapping).length > 0 ? datasetForm.formatMapping : null,
        sampleCount: 5,
      },
      { onSuccess: (response) => setPreviewResponse(response) },
    );
  };

  const isResolveDisabled = !datasetForm.datasetId.trim();
  const libraryEntries = React.useMemo(
    () => buildLibraryEntries({ profile: profile ?? null }),
    [profile],
  );

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[16px] font-semibold tracking-tight text-ink-1">Datasets</h1>
        <p className="mt-2 font-mono text-[12px] text-ink-3">
          Select a project to configure datasets.
        </p>
      </div>
    );
  }

  const totalRowsLabel = profile ? formatRowCount(profile.totalRows) : "—";
  const inspectCode = profile
    ? JSON.stringify(
        {
          datasetId: profile.datasetId,
          source: profile.source,
          format: profile.format,
          totalRows: profile.totalRows,
          splitCounts: profile.splitCounts,
          detectedFields: profile.detectedFields,
        },
        null,
        2,
      )
    : "{}";

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 items-center justify-between border-b border-hairline px-6">
        <div>
          <h1 className="font-mono text-[16px] font-semibold tracking-tight text-ink-1">
            Datasets
          </h1>
          <p className="font-mono text-[11px] text-ink-3">
            {libraryEntries.length} dataset{libraryEntries.length === 1 ? "" : "s"} ·{" "}
            {profile?.format ?? "—"} format
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => setActiveDialog("inspect")}>
            <Eye className="size-3" aria-hidden="true" />
            Inspect
          </Button>
          <Button variant="primary" size="sm" onClick={() => setActiveDialog("add")}>
            <Plus className="size-3" aria-hidden="true" />
            Add dataset
          </Button>
        </div>
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
          <Card>
            <CardHeader>
              <CardTitle>Library</CardTitle>
              <Badge variant="iris" dot={false}>
                {libraryEntries.length}
              </Badge>
            </CardHeader>
            {libraryEntries.length === 0 ? (
              <CardContent>
                <p className="font-mono text-[11px] text-ink-3">
                  No dataset resolved yet. Configure a source below and resolve.
                </p>
              </CardContent>
            ) : (
              <div>
                {libraryEntries.map((entry) => (
                  <RunRow key={entry.name} style={LIBRARY_ROW_STYLE}>
                    <StatusDot status={entry.isActive ? "running" : "pending"} />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate font-mono text-[12px] text-ink-1">
                          {entry.name}
                        </span>
                        {entry.isActive ? (
                          <Badge variant="iris" dot={false}>
                            ACTIVE
                          </Badge>
                        ) : null}
                      </div>
                      <div className="truncate font-mono text-[10px] text-ink-3">
                        {entry.format} · {entry.rows} rows
                      </div>
                    </div>
                    <RunRowCell align="end">{entry.size}</RunRowCell>
                    <RunRowCell align="end">{entry.isFrozen ? "frozen" : "—"}</RunRowCell>
                    <span aria-hidden="true" />
                  </RunRow>
                ))}
              </div>
            )}
          </Card>

          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <div className="min-w-0">
                  <CardTitle className="truncate">{profile?.datasetId ?? "—"}</CardTitle>
                  <p className="font-mono text-[11px] text-ink-3">
                    preview ·{" "}
                    {samplesResponse
                      ? `${samplesResponse.samples.length} of ${totalRowsLabel}`
                      : "loading"}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={() => setActiveDialog("validate")}>
                    Validate
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {isSamplesLoading && (
                  <p className="font-mono text-[11px] text-ink-3">Loading samples…</p>
                )}
                {samplesResponse !== undefined && profile !== undefined && (
                  <SamplePreview
                    samples={samplesResponse.samples}
                    detectedFields={profile.detectedFields}
                  />
                )}
              </CardContent>
            </Card>

            {profile?.tokenStats && (
              <Card>
                <CardHeader>
                  <CardTitle>Token length distribution</CardTitle>
                  <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
                    μ={Math.round(profile.tokenStats.mean)} · p95=
                    {Math.round(profile.tokenStats.p95)}
                  </span>
                </CardHeader>
                <CardContent>
                  <TokenHistogram stats={profile.tokenStats} />
                </CardContent>
              </Card>
            )}
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Dataset configuration</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <DatasetSourceSelector
              value={datasetForm.source}
              onChange={(source) => setDatasetForm({ source })}
            />

            <DatasetIdInput
              source={datasetForm.source}
              value={datasetForm.datasetId}
              onChange={(datasetId) => setDatasetForm({ datasetId })}
            />

            <FormatSelector
              value={datasetForm.format}
              onChange={(format) => setDatasetForm({ format })}
            />

            {(datasetForm.format === "custom" || datasetForm.format === "sharegpt") && (
              <FieldMappingEditor
                mapping={datasetForm.formatMapping}
                onChange={(formatMapping) => setDatasetForm({ formatMapping })}
              />
            )}

            <DatasetSubsetSelector
              trainRatio={datasetForm.trainRatio}
              valRatio={datasetForm.valRatio}
              testRatio={datasetForm.testRatio}
              splitCounts={profile?.splitCounts ?? null}
              sampleMode={datasetForm.sampleMode}
              maxSamples={datasetForm.maxSamples}
              totalRows={profile?.totalRows ?? null}
              onTrainRatioChange={(trainRatio) => setDatasetForm({ trainRatio })}
              onValRatioChange={(valRatio) => setDatasetForm({ valRatio })}
              onTestRatioChange={(testRatio) => setDatasetForm({ testRatio })}
              onSampleModeChange={(sampleMode) => setDatasetForm({ sampleMode })}
              onMaxSamplesChange={(maxSamples) => setDatasetForm({ maxSamples })}
            />

            {resolveDataset.error instanceof Error && (
              <p className="font-mono text-[11px] text-[color:var(--danger)]">
                {resolveDataset.error.message}
              </p>
            )}

            <DatasetResolveButton
              isPending={resolveDataset.isPending}
              isDisabled={isResolveDisabled}
              onResolve={handleResolve}
            />
          </CardContent>
        </Card>

        {isProfileLoading && (
          <p className="font-mono text-[11px] text-ink-3">Loading dataset profile…</p>
        )}

        {profileError !== null && !resolveDataset.isPending && (
          <p className="font-mono text-[11px] text-ink-3">
            No dataset resolved yet for this project.
          </p>
        )}

        {profile !== undefined && (
          <>
            <SplitInfoCards splitCounts={profile.splitCounts} totalRows={profile.totalRows} />

            <QualityWarnings
              warnings={profile.qualityWarnings}
              duplicateCount={profile.duplicateCount}
              malformedCount={profile.malformedCount}
            />

            <PreprocessingPreview
              format={datasetForm.format}
              isPending={previewTransform.isPending}
              response={previewResponse}
              onPreview={handlePreviewTransform}
            />
          </>
        )}
      </div>

      <Dialog
        open={activeDialog === "add"}
        onOpenChange={(open) => setActiveDialog(open ? "add" : null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add dataset</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 px-6 py-5">
            <p className="font-mono text-[11px] text-ink-3">
              Configure source and identifier in the page form and press Resolve &amp; Profile to
              ingest.
            </p>
            <Callout tone="iris">
              <span className="font-mono text-[11px] text-ink-2">
                $ llm-w datasets add --source {datasetForm.source} --format {datasetForm.format}{" "}
                {datasetForm.datasetId || "<path>"}
              </span>
            </Callout>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActiveDialog(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={activeDialog === "validate"}
        onOpenChange={(open) => setActiveDialog(open ? "validate" : null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Validate · {profile?.datasetId ?? "—"}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 px-6 py-5">
            {profile ? (
              <>
                <KVList
                  rows={[
                    {
                      key: "Schema",
                      value: `${profile.format} · ${profile.detectedFields.length} fields`,
                    },
                    {
                      key: "Tokens",
                      value: profile.tokenStats
                        ? `μ=${Math.round(profile.tokenStats.mean)} · p99=${Math.round(profile.tokenStats.p99)}`
                        : "—",
                    },
                    { key: "Duplicates", value: profile.duplicateCount.toLocaleString() },
                    { key: "Malformed", value: profile.malformedCount.toLocaleString() },
                  ]}
                />
                <QualityWarnings
                  warnings={profile.qualityWarnings}
                  duplicateCount={profile.duplicateCount}
                  malformedCount={profile.malformedCount}
                />
              </>
            ) : (
              <p className="font-mono text-[11px] text-ink-3">Resolve a dataset first.</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActiveDialog(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={activeDialog === "inspect"}
        onOpenChange={(open) => setActiveDialog(open ? "inspect" : null)}
      >
        <DialogContent className="max-w-[640px]">
          <DialogHeader>
            <DialogTitle>Inspect · {profile?.datasetId ?? "—"}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 px-6 py-5">
            {profile ? (
              <>
                <KVList
                  rows={[
                    { key: "Rows", value: totalRowsLabel },
                    { key: "Format", value: profile.format },
                    { key: "Source", value: profile.source },
                    {
                      key: "Detected fields",
                      value: profile.detectedFields.join(", ") || "—",
                    },
                  ]}
                />
                <CodeBlock code={inspectCode} language="json" />
              </>
            ) : (
              <p className="font-mono text-[11px] text-ink-3">Resolve a dataset first.</p>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setActiveDialog(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
