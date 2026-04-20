import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { RunConfigDiff } from "@/types/run";

interface ConfigDiffViewerProps {
  readonly configDiff: RunConfigDiff;
  readonly runIds: ReadonlyArray<string>;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function ConfigDiffViewer({ configDiff, runIds }: ConfigDiffViewerProps): React.JSX.Element {
  const { changed = {} } = configDiff;
  const entries = Object.entries(changed);

  if (entries.length === 0) {
    return (
      <Card>
        <CardHeader className="py-3">
          <CardTitle>Config diff</CardTitle>
        </CardHeader>
        <CardContent className="py-6 text-center font-mono text-[11px] text-ink-3">
          Configurations are identical across selected runs.
        </CardContent>
      </Card>
    );
  }

  const diffCellBackground = "color-mix(in oklch, var(--warn) 10%, var(--surface))";

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle>Config diff</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
          {entries.length} changed
        </span>
      </CardHeader>
      <CardContent className="overflow-x-auto p-0">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr>
              <th className="border-b border-hairline bg-surface-2 px-3.5 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-ink-3">
                param
              </th>
              {runIds.map((runId) => (
                <th
                  key={runId}
                  className="border-b border-hairline bg-surface-2 px-3.5 py-2 text-left font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-ink-3"
                >
                  {runId.slice(0, 8)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {entries.map(([paramKey, valuesByRun]) => {
              const baselineValue = formatValue(valuesByRun[runIds[0]] ?? null);
              return (
                <tr key={paramKey}>
                  <td className="border-b border-hairline px-3.5 py-2 font-mono text-[12px] text-ink-2">
                    {paramKey}
                  </td>
                  {runIds.map((runId, cellIndex) => {
                    const raw = valuesByRun[runId] ?? null;
                    const displayed = formatValue(raw);
                    const isDiff = cellIndex > 0 && displayed !== baselineValue;
                    return (
                      <td
                        key={runId}
                        className={cn(
                          "border-b border-hairline px-3.5 py-2 font-mono text-[12px] text-ink-1",
                        )}
                        style={isDiff ? { background: diffCellBackground } : undefined}
                      >
                        {displayed}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardContent>
    </Card>
  );
}
