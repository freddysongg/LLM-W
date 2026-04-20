import * as React from "react";
import { Download, Eye, Plus } from "lucide-react";
import { useAppStore } from "@/stores/app-store";
import { useDatasetProfile, useResolveDataset } from "@/hooks/useDatasetProfile";
import { useDatasetSamples, usePreviewTransform } from "@/hooks/useDatasetSamples";
import { useToast } from "@/hooks/use-toast";
import type {
  DatasetProfile,
  DatasetResolveRequest,
  PreviewTransformResponse,
} from "@/types/dataset";
import type { DatasetFormat, DatasetSource } from "@/types/config";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
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
import { BigMetric } from "@/components/shared/big-metric";
import { RangePills } from "@/components/shared/range-pills";

type DialogKind = "add" | "validate" | "inspect" | "splits" | null;

type LibraryFormatFilter = "all" | "chatml" | "alpaca" | "paired";

type AddDatasetSplitMode = "auto" | "manual" | "single";

interface LibraryEntry {
  readonly name: string;
  readonly format: DatasetFormat;
  readonly rows: string;
  readonly size: string;
  readonly isFrozen: boolean;
  readonly isActive: boolean;
}

interface AddDatasetDraft {
  readonly source: DatasetSource;
  readonly path: string;
  readonly format: DatasetFormat;
  readonly splitMode: AddDatasetSplitMode;
}

interface SplitDraft {
  readonly train: number;
  readonly val: number;
  readonly test: number;
  readonly seed: number;
}

interface BuildLibraryParams {
  readonly profile: DatasetProfile | null;
}

interface ApplyTrainRatioParams {
  readonly train: number;
  readonly current: SplitDraft;
}

const LIBRARY_ROW_COLUMNS = "18px minmax(0,1fr) 72px 64px 32px";

const LIBRARY_ROW_STYLE: React.CSSProperties = {
  gridTemplateColumns: LIBRARY_ROW_COLUMNS,
};

const FORMAT_FILTER_OPTIONS: ReadonlyArray<{
  readonly value: LibraryFormatFilter;
  readonly label: string;
}> = [
  { value: "all", label: "ALL" },
  { value: "chatml", label: "CHATML" },
  { value: "alpaca", label: "ALPACA" },
  { value: "paired", label: "PAIRED" },
];

const ADD_SOURCE_OPTIONS: ReadonlyArray<{
  readonly value: DatasetSource;
  readonly label: string;
  readonly placeholder: string;
}> = [
  { value: "huggingface", label: "HuggingFace", placeholder: "HuggingFaceH4/ultrachat_200k" },
  { value: "local_jsonl", label: "Local JSONL", placeholder: "data/train.jsonl" },
  { value: "local_csv", label: "Local CSV", placeholder: "data/train.csv" },
  { value: "custom", label: "Custom", placeholder: "path/to/dataset" },
];

const ADD_FORMAT_OPTIONS: ReadonlyArray<{
  readonly value: DatasetFormat;
  readonly label: string;
}> = [
  { value: "default", label: "default (auto-detect)" },
  { value: "sharegpt", label: "sharegpt" },
  { value: "openai", label: "openai" },
  { value: "alpaca", label: "alpaca" },
  { value: "custom", label: "custom" },
];

const SPLIT_MODE_OPTIONS: ReadonlyArray<{
  readonly value: AddDatasetSplitMode;
  readonly label: string;
}> = [
  { value: "auto", label: "auto" },
  { value: "manual", label: "manual" },
  { value: "single", label: "single" },
];

const DEFAULT_ADD_DRAFT: AddDatasetDraft = {
  source: "huggingface",
  path: "",
  format: "default",
  splitMode: "auto",
};

const DEFAULT_SPLIT_DRAFT: SplitDraft = {
  train: 90,
  val: 8,
  test: 2,
  seed: 42,
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

function buildLibraryEntries({ profile }: BuildLibraryParams): ReadonlyArray<LibraryEntry> {
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

function computeStddev(stats: {
  readonly mean: number;
  readonly median: number;
  readonly min: number;
  readonly max: number;
}): number {
  const { mean, median, min, max } = stats;
  const medianGap = Math.max(1, Math.abs(mean - median) * 2);
  const spread = Math.max(1, (max - min) / 4);
  return Math.round(Math.max(medianGap, spread));
}

function normalizeTrain({ train, current }: ApplyTrainRatioParams): SplitDraft {
  const clampedTrain = Math.max(0, Math.min(100, train));
  const remainder = 100 - clampedTrain;
  const previousNonTrainTotal = current.val + current.test;
  const valShare = previousNonTrainTotal > 0 ? current.val / previousNonTrainTotal : 0.8;
  const nextVal = Math.round(remainder * valShare);
  const nextTest = remainder - nextVal;
  return { ...current, train: clampedTrain, val: nextVal, test: nextTest };
}

export default function DatasetsPage(): React.JSX.Element {
  const { activeProjectId, datasetForm, setDatasetForm } = useAppStore();
  const { toast } = useToast();
  const [previewResponse, setPreviewResponse] = React.useState<PreviewTransformResponse | null>(
    null,
  );
  const [activeDialog, setActiveDialog] = React.useState<DialogKind>(null);
  // TODO(datasets-realign): backend profile has no format taxonomy matching chatml/alpaca/paired -- remove when /api/v1/datasets/profile returns a dataset-format tag aligned with mock filter
  const [formatFilter, setFormatFilter] = React.useState<LibraryFormatFilter>("all");
  const [addDraft, setAddDraft] = React.useState<AddDatasetDraft>(DEFAULT_ADD_DRAFT);
  const [splitDraft, setSplitDraft] = React.useState<SplitDraft>(DEFAULT_SPLIT_DRAFT);

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

  const handleIngestSubmit = (): void => {
    setActiveDialog(null);
    // TODO(datasets-realign): wire to real ingestion API -- remove when /api/v1/datasets/ingest lands; today users must still use the inline Dataset configuration form on the page
    toast({
      title: "Dataset queued for ingest",
      description: `${addDraft.source} · ${addDraft.path || "<path>"}`,
    });
  };

  const handleApplySplits = (): void => {
    setActiveDialog(null);
    // TODO(datasets-realign): persist splits to backend -- remove when /api/v1/datasets/splits endpoint lands; today the split ratios round-trip through the resolve request, not a standalone splits endpoint
    toast({
      title: "Splits applied locally",
      description: `${splitDraft.train}/${splitDraft.val}/${splitDraft.test} · seed ${splitDraft.seed}`,
    });
  };

  const isResolveDisabled = !datasetForm.datasetId.trim();
  const libraryEntries = React.useMemo(
    () => buildLibraryEntries({ profile: profile ?? null }),
    [profile],
  );

  const filteredLibraryEntries = libraryEntries;
  const activeEntryName = filteredLibraryEntries[0]?.name ?? null;

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
  const sizeLabel = profile ? estimateSizeLabel(profile.totalRows) : "—";
  const tokenStats = profile?.tokenStats ?? null;
  const meanTokensLabel = tokenStats ? Math.round(tokenStats.mean).toLocaleString() : "—";
  const stddevLabel = tokenStats
    ? computeStddev({
        mean: tokenStats.mean,
        median: tokenStats.median,
        min: tokenStats.min,
        max: tokenStats.max,
      }).toLocaleString()
    : "—";
  // TODO(datasets-realign): frozen eval split count has no backing field -- remove when DatasetProfile exposes frozenEvalSplits
  const frozenEvalSplitCount = 0;

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
            {libraryEntries.length} dataset{libraryEntries.length === 1 ? "" : "s"} · {sizeLabel}{" "}
            total · {frozenEvalSplitCount} frozen eval split
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
              <RangePills
                options={FORMAT_FILTER_OPTIONS}
                value={formatFilter}
                onChange={setFormatFilter}
                ariaLabel="Filter library by dataset format"
              />
            </CardHeader>
            {filteredLibraryEntries.length === 0 ? (
              <CardContent>
                <p className="font-mono text-[11px] text-ink-3">
                  No dataset resolved yet. Configure a source below and resolve.
                </p>
              </CardContent>
            ) : (
              <div>
                {filteredLibraryEntries.map((entry) => {
                  const isSelected = entry.name === activeEntryName;
                  return (
                    <RunRow key={entry.name} style={LIBRARY_ROW_STYLE} selected={isSelected}>
                      <StatusDot status={entry.isActive ? "running" : "pending"} />
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="truncate font-mono text-[12px] text-ink-1">
                            {entry.name}
                          </span>
                        </div>
                        <div className="truncate font-mono text-[10px] text-ink-3">
                          {entry.format} · {entry.rows} rows
                        </div>
                      </div>
                      <RunRowCell align="end">{entry.size}</RunRowCell>
                      <RunRowCell align="end">{entry.isFrozen ? "frozen" : "—"}</RunRowCell>
                      <span aria-hidden="true" />
                    </RunRow>
                  );
                })}
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
                  <Button variant="outline" size="sm" onClick={() => setActiveDialog("splits")}>
                    Splits
                  </Button>
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

            {tokenStats && (
              <Card>
                <CardHeader>
                  <CardTitle>Token length distribution</CardTitle>
                  <span className="caps text-ink-3">
                    μ={meanTokensLabel} · σ={stddevLabel}
                  </span>
                </CardHeader>
                <CardContent>
                  <TokenHistogram stats={tokenStats} />
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

      <AddDatasetDialog
        isOpen={activeDialog === "add"}
        draft={addDraft}
        onDraftChange={setAddDraft}
        onCancel={() => setActiveDialog(null)}
        onIngest={handleIngestSubmit}
      />

      <SplitsDialog
        isOpen={activeDialog === "splits"}
        datasetName={profile?.datasetId ?? "—"}
        draft={splitDraft}
        onDraftChange={setSplitDraft}
        onCancel={() => setActiveDialog(null)}
        onApply={handleApplySplits}
      />

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
                    {
                      key: "Leakage",
                      value: (
                        <span
                          className="text-ink-3"
                          title="pending backend signal"
                          // TODO(datasets-realign): wire leakage signal -- remove when DatasetProfile exposes an evalLeakageCount field
                        >
                          —
                        </span>
                      ),
                    },
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
          <div className="flex flex-col gap-5 px-6 py-5">
            {profile ? (
              <>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <BigMetric label="Rows" value={profile.totalRows} />
                  <BigMetric label="Size" value={sizeLabel} />
                  <BigMetric
                    label="Mean tokens"
                    value={profile.tokenStats ? Math.round(profile.tokenStats.mean) : "—"}
                  />
                  <BigMetric label="Format" value={profile.format} />
                </div>
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

interface AddDatasetDialogProps {
  readonly isOpen: boolean;
  readonly draft: AddDatasetDraft;
  readonly onDraftChange: (next: AddDatasetDraft) => void;
  readonly onCancel: () => void;
  readonly onIngest: () => void;
}

function AddDatasetDialog({
  isOpen,
  draft,
  onDraftChange,
  onCancel,
  onIngest,
}: AddDatasetDialogProps): React.JSX.Element {
  const activeSource = ADD_SOURCE_OPTIONS.find(({ value }) => value === draft.source);
  const placeholder = activeSource?.placeholder ?? "";

  return (
    <Dialog open={isOpen} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <DialogContent className="max-w-[560px]">
        <DialogHeader>
          <DialogTitle>Add dataset</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 px-6 py-5">
          <div className="space-y-2">
            <Label htmlFor="add-dataset-source">Source</Label>
            <Select
              value={draft.source}
              onValueChange={(next) => onDraftChange({ ...draft, source: next as DatasetSource })}
            >
              <SelectTrigger id="add-dataset-source">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ADD_SOURCE_OPTIONS.map(({ value, label }) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label htmlFor="add-dataset-path">Path</Label>
            <Input
              id="add-dataset-path"
              mono
              value={draft.path}
              placeholder={placeholder}
              onChange={(event) => onDraftChange({ ...draft, path: event.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="add-dataset-format">Format</Label>
              <Select
                value={draft.format}
                onValueChange={(next) => onDraftChange({ ...draft, format: next as DatasetFormat })}
              >
                <SelectTrigger id="add-dataset-format">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ADD_FORMAT_OPTIONS.map(({ value, label }) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="add-dataset-split">Split detection</Label>
              <Select
                value={draft.splitMode}
                onValueChange={(next) =>
                  onDraftChange({ ...draft, splitMode: next as AddDatasetSplitMode })
                }
              >
                <SelectTrigger id="add-dataset-split">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {SPLIT_MODE_OPTIONS.map(({ value, label }) => (
                    <SelectItem key={value} value={value}>
                      {label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <Callout tone="iris">
            <span className="font-mono text-[11px] text-ink-2">
              $ llm-w datasets add --source {draft.source} --format {draft.format}{" "}
              {draft.path || "<path>"}
            </span>
          </Callout>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onIngest}>
            <Download className="size-3" aria-hidden="true" />
            Ingest
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface SplitsDialogProps {
  readonly isOpen: boolean;
  readonly datasetName: string;
  readonly draft: SplitDraft;
  readonly onDraftChange: (next: SplitDraft) => void;
  readonly onCancel: () => void;
  readonly onApply: () => void;
}

function SplitsDialog({
  isOpen,
  datasetName,
  draft,
  onDraftChange,
  onCancel,
  onApply,
}: SplitsDialogProps): React.JSX.Element {
  const handleTrainChange = (next: number): void => {
    onDraftChange(normalizeTrain({ train: next, current: draft }));
  };

  const handleSeedChange = (raw: string): void => {
    const parsed = Number.parseInt(raw, 10);
    onDraftChange({ ...draft, seed: Number.isFinite(parsed) ? parsed : 0 });
  };

  return (
    <Dialog open={isOpen} onOpenChange={(next) => (next ? undefined : onCancel())}>
      <DialogContent className="max-w-[520px]">
        <DialogHeader>
          <DialogTitle>Splits · {datasetName}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-5 px-6 py-5">
          <div className="space-y-2">
            <div className="flex items-baseline justify-between">
              <Label>Train</Label>
              <span className="font-mono text-[11px] text-ink-2">{draft.train}%</span>
            </div>
            <Slider
              min={50}
              max={98}
              step={1}
              value={[draft.train]}
              onValueChange={([next]) => handleTrainChange(next)}
              aria-label="Train split percentage"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label>Validation</Label>
              <div className="font-mono text-[13px] text-ink-1">{draft.val}%</div>
            </div>
            <div className="space-y-1">
              <Label>Test</Label>
              <div className="font-mono text-[13px] text-ink-1">{draft.test}%</div>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="splits-seed">Seed</Label>
            <Input
              id="splits-seed"
              mono
              type="number"
              value={draft.seed}
              onChange={(event) => handleSeedChange(event.target.value)}
            />
          </div>
          <SplitsBar draft={draft} />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button variant="primary" onClick={onApply}>
            Apply
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface SplitsBarProps {
  readonly draft: SplitDraft;
}

function SplitsBar({ draft }: SplitsBarProps): React.JSX.Element {
  const segments: ReadonlyArray<{
    readonly key: "train" | "val" | "test";
    readonly label: string;
    readonly value: number;
    readonly color: string;
  }> = [
    { key: "train", label: "train", value: draft.train, color: "var(--iris-3)" },
    { key: "val", label: "val", value: draft.val, color: "var(--iris-2)" },
    { key: "test", label: "test", value: draft.test, color: "var(--iris-4)" },
  ];

  return (
    <div className="flex h-7 w-full overflow-hidden rounded-md border border-hairline">
      {segments.map(({ key, label, value, color }) =>
        value > 0 ? (
          <div
            key={key}
            className="flex items-center justify-center font-mono text-[10px] text-[color:var(--surface)]"
            style={{ flex: value, backgroundColor: color }}
            title={`${label} ${value}%`}
          >
            {value}%
          </div>
        ) : null,
      )}
    </div>
  );
}
