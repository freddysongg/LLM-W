import { useConfigSnapshot } from "@/hooks/useConfigSnapshot";
import type { ConfigDiff } from "@/types/config-snapshot";

interface ConfigSnapshotTabProps {
  readonly projectId: string;
  readonly runId: string;
}

export function ConfigSnapshotTab({ projectId, runId }: ConfigSnapshotTabProps) {
  const { data, isLoading, error } = useConfigSnapshot({ projectId, runId });

  if (isLoading) {
    return <div className="text-xs text-muted-foreground">Loading config…</div>;
  }
  if (error !== null) {
    return (
      <div className="text-xs text-destructive">
        Failed to load config snapshot: {error instanceof Error ? error.message : "unknown"}
      </div>
    );
  }
  if (data === undefined) {
    return <div className="text-xs text-muted-foreground">No snapshot.</div>;
  }

  return (
    <div className="grid grid-cols-[1fr_1fr] gap-3">
      <ConfigYamlPane yaml={data.yaml} />
      <ConfigDiffPane diff={data.diff} />
    </div>
  );
}

function ConfigYamlPane({ yaml }: { readonly yaml: string }) {
  return (
    <pre className="overflow-auto rounded-md border border-border bg-muted/30 p-3 text-[11px] leading-relaxed font-mono">
      {yaml}
    </pre>
  );
}

function ConfigDiffPane({ diff }: { readonly diff: ConfigDiff }) {
  const hasChanges =
    Object.keys(diff.changed).length > 0 ||
    Object.keys(diff.added).length > 0 ||
    Object.keys(diff.removed).length > 0;

  if (!hasChanges) {
    return (
      <div className="rounded-md border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
        No differences from parent config version.
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-md border border-border bg-muted/20 p-3 text-[11px] font-mono">
      {Object.entries(diff.changed).map(([key, entry]) => (
        <div key={`c-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-destructive">- {String(entry.old)}</span>
          <span className="text-emerald-600">+ {String(entry.new)}</span>
        </div>
      ))}
      {Object.entries(diff.added).map(([key, value]) => (
        <div key={`a-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-emerald-600">+ {String(value)}</span>
        </div>
      ))}
      {Object.entries(diff.removed).map(([key, value]) => (
        <div key={`r-${key}`} className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">{key}</span>
          <span className="text-destructive">- {String(value)}</span>
        </div>
      ))}
    </div>
  );
}
