import * as React from "react";
import { Archive, Download, MoreHorizontal, Trash2 } from "lucide-react";
import type { Artifact } from "@/types/artifact";
import { useAppStore } from "@/stores/app-store";
import { useArtifacts, useDeleteArtifact, useCleanupArtifacts } from "@/hooks/useArtifacts";
import { useCreateMergedModel } from "@/hooks/useMergedModels";
import { useProjectStorage, useCleanupStorage } from "@/hooks/useStorage";
import { useLockEntered } from "@/hooks/use-lock-entered";
import { useToast } from "@/hooks/use-toast";
import { ArtifactDetailDrawer } from "@/components/artifacts/artifact-detail-drawer";
import { StorageBar } from "@/components/artifacts/storage-bar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StatusDot } from "@/components/shared/status-dot";
import { RunRow, RunRowActions, RunRowCell } from "@/components/shared/run-row";
import { SliderRow } from "@/components/shared/slider-row";
import { getArtifactDownloadUrl } from "@/api/artifacts";
import { describeApiError } from "@/lib/api-error";
import { deriveMergedName } from "@/lib/merged-models";
import { cn } from "@/lib/utils";

type ArtifactsTab = "checkpoints" | "exports" | "storage";

const CHECKPOINT_GRID = "18px 1fr 100px 80px 100px 200px 40px";
const EXPORT_GRID = "22px minmax(0, 1fr) 120px 110px 110px 120px";

const EXPORT_TYPES = new Set([
  "metric_export",
  "comparison_summary",
  "weight_delta",
  "eval_output",
  "ai_recommendation",
]);

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = Math.max(0, now - then);
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

function filenameOf(path: string): string {
  return path.split("/").at(-1) ?? path;
}

interface CheckpointRowProps {
  readonly artifact: Artifact;
  readonly projectId: string;
  readonly isSelected: boolean;
  readonly isDeleting: boolean;
  readonly isMerging: boolean;
  readonly onSelect: (artifactId: string) => void;
  readonly onDelete: (artifactId: string) => void;
  readonly onMerge: (runId: string) => void;
}

function CheckpointRow({
  artifact,
  projectId,
  isSelected,
  isDeleting,
  isMerging,
  onSelect,
  onDelete,
  onMerge,
}: CheckpointRowProps): React.JSX.Element {
  const { id, runId, filePath, fileSizeBytes, createdAt, isRetained, metadata } = artifact;
  const stepValue = typeof metadata?.step === "number" ? metadata.step : null;
  const tag = typeof metadata?.tag === "string" ? metadata.tag : null;
  const { toast } = useToast();

  return (
    <RunRow
      selected={isSelected}
      onClick={() => onSelect(id)}
      style={{ gridTemplateColumns: CHECKPOINT_GRID }}
    >
      <StatusDot status={isRetained ? "success" : "pending"} />
      <div className="min-w-0">
        <div className="truncate text-[13px] font-medium text-ink-1">{runId.slice(0, 12)}</div>
        <div className="truncate font-mono text-[10.5px] text-ink-3">
          {stepValue !== null ? `step ${stepValue.toLocaleString()} · ` : ""}
          {filenameOf(filePath)}
        </div>
      </div>
      <div>
        {tag ? (
          <Badge variant={tag === "best" ? "iris" : "success"} dot={false}>
            {tag}
          </Badge>
        ) : (
          <RunRowCell>—</RunRowCell>
        )}
      </div>
      <RunRowCell>{formatBytes(fileSizeBytes)}</RunRowCell>
      <RunRowCell align="end">{formatRelative(createdAt)}</RunRowCell>
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={(event) => {
            event.stopPropagation();
            toast({ title: "Resume", description: "Resume flow is triggered from the Runs page." });
          }}
        >
          Resume
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={isMerging}
          onClick={(event) => {
            event.stopPropagation();
            onMerge(runId);
          }}
        >
          {isMerging ? "Merging…" : "Merge"}
        </Button>
      </div>
      <RunRowActions>
        <Button variant="ghost" size="icon" className="h-7 w-7" asChild>
          <a
            href={getArtifactDownloadUrl({ projectId, artifactId: id })}
            download
            onClick={(event) => event.stopPropagation()}
            aria-label={`Download checkpoint ${filenameOf(filePath)}`}
          >
            <Download className="h-3.5 w-3.5" aria-hidden="true" />
          </a>
        </Button>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-[color:var(--danger)]"
              aria-label={`Delete checkpoint ${filenameOf(filePath)}`}
              disabled={isDeleting}
              onClick={(event) => event.stopPropagation()}
            >
              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Delete checkpoint?</AlertDialogTitle>
              <AlertDialogDescription>
                This will permanently delete{" "}
                <span className="font-mono text-[12px]">{filePath}</span>.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={() => onDelete(id)}
                className="bg-[color:var(--danger)] text-[color:var(--surface)] border-[color:var(--danger)] hover:bg-[color-mix(in_oklch,var(--danger)_88%,black)]"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </RunRowActions>
    </RunRow>
  );
}

interface ExportRowProps {
  readonly artifact: Artifact;
  readonly isSelected: boolean;
  readonly onSelect: (artifactId: string) => void;
}

function ExportRow({ artifact, isSelected, onSelect }: ExportRowProps): React.JSX.Element {
  const { id, artifactType, filePath, fileSizeBytes, createdAt } = artifact;
  const { toast } = useToast();

  return (
    <RunRow
      selected={isSelected}
      onClick={() => onSelect(id)}
      style={{ gridTemplateColumns: EXPORT_GRID }}
    >
      <Archive className="h-3.5 w-3.5 text-ink-3" aria-hidden="true" />
      <div className="min-w-0">
        <div className="flex items-center gap-2 truncate text-[13px] font-medium text-ink-1">
          <span className="truncate">{filenameOf(filePath)}</span>
          <Badge variant="default" dot={false}>
            {artifactType.replace(/_/g, " ")}
          </Badge>
        </div>
        <div className="truncate font-mono text-[10.5px] text-ink-3">{filePath}</div>
      </div>
      <RunRowCell align="end">{formatBytes(fileSizeBytes)}</RunRowCell>
      <RunRowCell align="end">{formatRelative(createdAt)}</RunRowCell>
      <div />
      <div className="flex items-center justify-end gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={(event) => {
            event.stopPropagation();
            toast({ title: "Re-export", description: "Re-export flow is not yet wired." });
          }}
        >
          Re-export
        </Button>
        <Button variant="ghost" size="icon" className="h-7 w-7" aria-label="More actions">
          <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
        </Button>
      </div>
    </RunRow>
  );
}

interface StorageTabProps {
  readonly totalBytes: number;
  readonly breakdownSegments: ReadonlyArray<{ label: string; bytes: number; color: string }>;
  readonly isCleaningUp: boolean;
  readonly onCleanup: () => void;
}

function StorageTab({
  totalBytes,
  breakdownSegments,
  isCleaningUp,
  onCleanup,
}: StorageTabProps): React.JSX.Element {
  const [keepLastN, setKeepLastN] = React.useState<number>(5);
  const [archiveAfterDays, setArchiveAfterDays] = React.useState<number>(30);
  const [isAutoPrune, setIsAutoPrune] = React.useState<boolean>(true);
  const [isCompressExports, setIsCompressExports] = React.useState<boolean>(false);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader className="py-3">
          <CardTitle>Storage usage</CardTitle>
          <Badge dot={false}>{formatBytes(totalBytes)}</Badge>
        </CardHeader>
        <CardContent>
          <StorageBar segments={breakdownSegments} totalBytes={Math.max(totalBytes, 1)} />
          <div className="mt-4 flex justify-end">
            <Button variant="outline" size="sm" onClick={onCleanup} disabled={isCleaningUp}>
              {isCleaningUp ? "Cleaning up…" : "Run cleanup"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="py-3">
          <CardTitle>Retention policy</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <SliderRow
            label="Keep last N runs"
            value={keepLastN}
            min={1}
            max={20}
            step={1}
            formatValue={(value) => value.toFixed(0)}
            onChange={setKeepLastN}
          />
          <SliderRow
            label="Archive after X days"
            value={archiveAfterDays}
            min={1}
            max={180}
            step={1}
            formatValue={(value) => `${value} days`}
            onChange={setArchiveAfterDays}
          />
          <label className="flex items-center justify-between gap-2 font-mono text-[11px] text-ink-2">
            <span>Auto-prune stale checkpoints</span>
            <Switch
              checked={isAutoPrune}
              onCheckedChange={setIsAutoPrune}
              aria-label="Auto-prune stale checkpoints"
            />
          </label>
          <label className="flex items-center justify-between gap-2 font-mono text-[11px] text-ink-2">
            <span>Compress old exports</span>
            <Switch
              checked={isCompressExports}
              onCheckedChange={setIsCompressExports}
              aria-label="Compress old exports"
            />
          </label>
          <p className="font-mono text-[10.5px] text-ink-3">
            Retention adjustments are local previews until a policy endpoint is wired.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ArtifactsPage(): React.JSX.Element {
  const { activeProjectId } = useAppStore();
  const [selectedArtifactId, setSelectedArtifactId] = React.useState<string | null>(null);
  const isAnimationLocked = useLockEntered();

  const projectId = activeProjectId ?? "";

  const { data: allArtifacts = [], isLoading } = useArtifacts({ projectId });
  const { data: storage } = useProjectStorage({ projectId });

  const deleteMutation = useDeleteArtifact();
  const cleanupArtifactsMutation = useCleanupArtifacts();
  const cleanupStorageMutation = useCleanupStorage();
  const createMergedModel = useCreateMergedModel({ projectId });
  const { toast } = useToast();

  const checkpoints = React.useMemo(
    () => allArtifacts.filter((candidate) => candidate.artifactType === "checkpoint"),
    [allArtifacts],
  );

  const exports = React.useMemo(
    () => allArtifacts.filter((candidate) => EXPORT_TYPES.has(candidate.artifactType)),
    [allArtifacts],
  );

  const selectedArtifact: Artifact | null =
    allArtifacts.find((candidate) => candidate.id === selectedArtifactId) ?? null;

  const handleDelete = (artifactId: string): void => {
    if (!projectId) return;
    deleteMutation.mutate(
      { projectId, artifactId },
      {
        onSuccess: () => {
          if (selectedArtifactId === artifactId) {
            setSelectedArtifactId(null);
          }
        },
      },
    );
  };

  const handleBulkCleanup = (): void => {
    if (!projectId) return;
    cleanupArtifactsMutation.mutate({ projectId });
  };

  const handleStorageCleanup = (): void => {
    if (!projectId) return;
    cleanupStorageMutation.mutate({ projectId });
  };

  const handleMerge = (runId: string): void => {
    if (!projectId) return;
    createMergedModel.mutate(
      { sourceRunId: runId },
      {
        onSuccess: (merged) => {
          toast({
            title: "Merged model created",
            description: `${deriveMergedName({
              baseModelId: merged.baseModelId,
              adapterStep: merged.adapterStep,
            })} · ${formatBytes(merged.fileSizeBytes)}`,
          });
        },
        onError: (cause) => {
          toast({
            title: "Merge failed",
            description: describeApiError({
              cause,
              fallback: "Merging the adapter into the base model failed.",
            }),
            variant: "destructive",
          });
        },
      },
    );
  };

  if (!activeProjectId) {
    return (
      <div className="p-6">
        <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
          Artifacts
        </h1>
        <p className="mt-2 font-mono text-[11px] text-ink-3">Select a project to view artifacts.</p>
      </div>
    );
  }

  const enteredClass = isAnimationLocked ? "entered" : "";

  const breakdownSegments = storage
    ? [
        {
          label: "Checkpoints",
          bytes: storage.breakdown.checkpoints.bytes,
          color: "oklch(0.88 0.14 150)",
        },
        {
          label: "Exports",
          bytes: storage.breakdown.exports.bytes,
          color: "oklch(0.86 0.11 200)",
        },
        {
          label: "Logs",
          bytes: storage.breakdown.logs.bytes,
          color: "oklch(0.80 0.14 260)",
        },
        {
          label: "Activations",
          bytes: storage.breakdown.activations.bytes,
          color: "oklch(0.82 0.13 310)",
        },
      ]
    : [];

  return (
    <div className="flex flex-col gap-4 p-6">
      <header className={cn("flex items-start justify-between gap-4 enter enter-1", enteredClass)}>
        <div>
          <h1 className="font-mono text-[22px] font-semibold tracking-[-0.01em] text-ink-1">
            Artifacts
          </h1>
          <p className="mt-1 font-mono text-[11px] text-ink-3">checkpoints · exports · storage</p>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="sm" disabled={cleanupArtifactsMutation.isPending}>
              <Trash2 aria-hidden="true" />
              {cleanupArtifactsMutation.isPending ? "Cleaning…" : "Bulk cleanup"}
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>Run retention policy cleanup?</AlertDialogTitle>
              <AlertDialogDescription>
                This will delete non-retained artifacts according to the project retention policy.
                Retained artifacts will not be affected.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction onClick={handleBulkCleanup}>Run cleanup</AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </header>

      <Tabs
        defaultValue={"checkpoints" satisfies ArtifactsTab}
        className={cn("flex flex-col gap-4 enter enter-2", enteredClass)}
      >
        <TabsList>
          <TabsTrigger value="checkpoints">Checkpoints</TabsTrigger>
          <TabsTrigger value="exports">Exports</TabsTrigger>
          <TabsTrigger value="storage">Storage</TabsTrigger>
        </TabsList>

        <TabsContent value="checkpoints" className="mt-0">
          {isLoading ? (
            <div className="font-mono text-[11px] text-ink-3">Loading artifacts…</div>
          ) : checkpoints.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center font-mono text-[11px] text-ink-3">
                No checkpoints saved yet.
              </CardContent>
            </Card>
          ) : (
            <Card className="p-0">
              <RunRow isHeader style={{ gridTemplateColumns: CHECKPOINT_GRID }}>
                <span />
                <RunRowCell>run · file</RunRowCell>
                <RunRowCell>tag</RunRowCell>
                <RunRowCell>size</RunRowCell>
                <RunRowCell align="end">age</RunRowCell>
                <RunRowCell>actions</RunRowCell>
                <span />
              </RunRow>
              {checkpoints.map((artifact) => (
                <CheckpointRow
                  key={artifact.id}
                  artifact={artifact}
                  projectId={projectId}
                  isSelected={selectedArtifactId === artifact.id}
                  isDeleting={deleteMutation.isPending}
                  isMerging={createMergedModel.isPending}
                  onSelect={setSelectedArtifactId}
                  onDelete={handleDelete}
                  onMerge={handleMerge}
                />
              ))}
            </Card>
          )}
        </TabsContent>

        <TabsContent value="exports" className="mt-0">
          {isLoading ? (
            <div className="font-mono text-[11px] text-ink-3">Loading exports…</div>
          ) : exports.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center font-mono text-[11px] text-ink-3">
                No exports yet.
              </CardContent>
            </Card>
          ) : (
            <Card className="p-0">
              <RunRow isHeader style={{ gridTemplateColumns: EXPORT_GRID }}>
                <span />
                <RunRowCell>file · format</RunRowCell>
                <RunRowCell align="end">size</RunRowCell>
                <RunRowCell align="end">age</RunRowCell>
                <span />
                <RunRowCell align="end">actions</RunRowCell>
              </RunRow>
              {exports.map((artifact) => (
                <ExportRow
                  key={artifact.id}
                  artifact={artifact}
                  isSelected={selectedArtifactId === artifact.id}
                  onSelect={setSelectedArtifactId}
                />
              ))}
            </Card>
          )}
        </TabsContent>

        <TabsContent value="storage" className="mt-0">
          <StorageTab
            totalBytes={storage?.totalBytes ?? 0}
            breakdownSegments={breakdownSegments}
            isCleaningUp={cleanupStorageMutation.isPending}
            onCleanup={handleStorageCleanup}
          />
        </TabsContent>
      </Tabs>

      <ArtifactDetailDrawer
        artifact={selectedArtifact}
        projectId={projectId}
        onClose={() => setSelectedArtifactId(null)}
      />
    </div>
  );
}
