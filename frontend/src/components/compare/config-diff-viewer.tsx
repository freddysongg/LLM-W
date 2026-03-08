import * as React from "react";
import { DiffEditor } from "@monaco-editor/react";
import type { RunConfigDiff } from "@/types/run";

interface ConfigDiffViewerProps {
  readonly configDiff: RunConfigDiff;
  readonly runIds: ReadonlyArray<string>;
}

function formatConfigSide(
  changedKeys: Record<string, Record<string, unknown>>,
  runId: string,
): string {
  if (Object.keys(changedKeys).length === 0) return "# No differences";
  return Object.entries(changedKeys)
    .map(([key, values]) => `${key}: ${JSON.stringify(values[runId] ?? null)}`)
    .join("\n");
}

function ConfigDiffTable({
  changed,
  runIds,
}: {
  readonly changed: Record<string, Record<string, unknown>>;
  readonly runIds: ReadonlyArray<string>;
}): React.JSX.Element {
  const entries = Object.entries(changed);
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">Configurations are identical.</p>;
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="text-left px-3 py-2 font-medium text-muted-foreground">Config Key</th>
            {runIds.map((id) => (
              <th key={id} className="text-left px-3 py-2 font-medium font-mono text-xs">
                {id.slice(0, 8)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {entries.map(([key, values]) => (
            <tr key={key} className="border-b hover:bg-muted/30">
              <td className="px-3 py-2 font-mono text-xs text-muted-foreground">{key}</td>
              {runIds.map((id) => (
                <td key={id} className="px-3 py-2 font-mono text-xs">
                  {JSON.stringify(values[id] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ConfigDiffViewer({ configDiff, runIds }: ConfigDiffViewerProps): React.JSX.Element {
  const { changed = {} } = configDiff;

  if (Object.keys(changed).length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-muted-foreground">
        Configurations are identical across selected runs.
      </div>
    );
  }

  if (runIds.length !== 2) {
    return (
      <div className="border rounded-md overflow-hidden">
        <div className="px-4 py-2 border-b bg-muted/50 text-xs text-muted-foreground">
          {Object.keys(changed).length} changed key{Object.keys(changed).length !== 1 ? "s" : ""}
        </div>
        <ConfigDiffTable changed={changed} runIds={runIds} />
      </div>
    );
  }

  const [runId1, runId2] = runIds;
  const original = formatConfigSide(changed, runId1);
  const modified = formatConfigSide(changed, runId2);

  return (
    <div className="border rounded-md overflow-hidden">
      <div className="flex border-b text-xs text-muted-foreground bg-muted/50">
        <div className="flex-1 px-4 py-2 font-mono">{runId1.slice(0, 8)} (original)</div>
        <div className="w-px bg-border" />
        <div className="flex-1 px-4 py-2 font-mono">{runId2.slice(0, 8)} (modified)</div>
      </div>
      <DiffEditor
        original={original}
        modified={modified}
        language="yaml"
        height={360}
        theme="vs-dark"
        options={{
          readOnly: true,
          renderSideBySide: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          fontSize: 12,
          lineNumbers: "off",
          folding: false,
        }}
      />
    </div>
  );
}
