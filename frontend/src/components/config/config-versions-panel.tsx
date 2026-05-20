import * as React from "react";
import { ChevronDown, ChevronRight, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useConfigVersions } from "@/hooks/useConfigVersions";
import type { ConfigVersionSummary } from "@/types/config-version";

interface ConfigVersionsPanelProps {
  readonly projectId: string;
  readonly activeVersionId: string | null;
  readonly onRestore: (version: ConfigVersionSummary) => void;
}

interface VersionRowProps {
  readonly version: ConfigVersionSummary;
  readonly isActive: boolean;
  readonly onRestore: () => void;
}

interface DiffShape {
  readonly changed: Record<string, unknown>;
  readonly added: Record<string, unknown>;
  readonly removed: Record<string, unknown>;
}

export function ConfigVersionsPanel({
  projectId,
  activeVersionId,
  onRestore,
}: ConfigVersionsPanelProps): React.JSX.Element {
  const [isOpen, setIsOpen] = React.useState(false);
  const { data, isLoading, error } = useConfigVersions({ projectId });

  const items = data?.items ?? [];

  return (
    <div className="rounded-md border border-hairline bg-surface-2">
      <button
        type="button"
        onClick={() => setIsOpen((previous) => !previous)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-ink-3 hover:text-ink-1"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        History ({items.length})
      </button>

      {isOpen ? (
        <div className="divide-y divide-hairline">
          {isLoading ? (
            <div className="px-3 py-2 text-[11px] text-ink-3">Loading…</div>
          ) : error !== null ? (
            <div className="px-3 py-2 text-[11px] text-red-600">Failed to load history</div>
          ) : items.length === 0 ? (
            <div className="px-3 py-2 text-[11px] text-ink-3">No versions yet.</div>
          ) : (
            items.map((version) => (
              <VersionRow
                key={version.id}
                version={version}
                isActive={version.id === activeVersionId}
                onRestore={() => onRestore(version)}
              />
            ))
          )}
        </div>
      ) : null}
    </div>
  );
}

function VersionRow({ version, isActive, onRestore }: VersionRowProps): React.JSX.Element {
  const changeSummary = summarizeDiff(version.diffFromPrev);
  const detailLabel = version.sourceDetail ?? version.sourceTag;

  return (
    <div className="grid grid-cols-[80px_1fr_120px_auto] items-center gap-3 px-3 py-2">
      <span className="font-mono text-xs text-ink-1">v{version.versionNumber}</span>
      <div className="flex items-center gap-2 text-[11px] text-ink-3">
        <span className="font-mono">{formatRelative(version.createdAt)}</span>
        <Badge variant="secondary" className="text-[10px]">
          {detailLabel}
        </Badge>
        {isActive ? (
          <Badge variant="secondary" className="bg-emerald-600/20 text-emerald-700">
            active
          </Badge>
        ) : null}
      </div>
      <span className="font-mono text-[11px] text-ink-3">{changeSummary}</span>
      <Button variant="ghost" size="sm" onClick={onRestore} disabled={isActive} className="gap-1">
        <RotateCcw className="h-3 w-3" />
        Restore
      </Button>
    </div>
  );
}

function summarizeDiff(diff: unknown): string {
  if (
    diff === null ||
    typeof diff !== "object" ||
    !("changed" in diff) ||
    !("added" in diff) ||
    !("removed" in diff)
  ) {
    return "—";
  }
  const typed = diff as DiffShape;
  const changedCount = Object.keys(typed.changed ?? {}).length;
  const addedCount = Object.keys(typed.added ?? {}).length;
  const removedCount = Object.keys(typed.removed ?? {}).length;
  if (changedCount + addedCount + removedCount === 0) {
    return "no diff";
  }
  const parts: string[] = [];
  if (changedCount > 0) parts.push(`${changedCount} changed`);
  if (addedCount > 0) parts.push(`${addedCount} added`);
  if (removedCount > 0) parts.push(`${removedCount} removed`);
  return parts.join(", ");
}

function formatRelative(isoString: string): string {
  const deltaMs = Date.now() - new Date(isoString).getTime();
  const minutes = Math.floor(deltaMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
