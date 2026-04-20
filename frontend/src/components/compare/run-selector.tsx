import * as React from "react";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { colorForRunId } from "@/lib/run-color-palette";
import type { Run } from "@/types/run";

interface RunSelectorProps {
  readonly runs: ReadonlyArray<Run>;
  readonly selectedRunIds: ReadonlyArray<string>;
  readonly onSelectionChange: (runIds: ReadonlyArray<string>) => void;
}

interface RunCheckRowProps {
  readonly run: Run;
  readonly isSelected: boolean;
  readonly onToggle: () => void;
}

function RunCheckRow({ run, isSelected, onToggle }: RunCheckRowProps): React.JSX.Element {
  const swatchColor = colorForRunId(run.id);
  const labelId = `run-check-${run.id}`;
  return (
    <label
      htmlFor={labelId}
      className="flex cursor-pointer items-center gap-2 rounded-sm px-1.5 py-1 transition-colors hover:bg-surface-2"
    >
      <Checkbox
        id={labelId}
        checked={isSelected}
        onCheckedChange={onToggle}
        aria-label={`Include run ${run.id.slice(0, 8)} in comparison`}
      />
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 shrink-0 rounded-[2px]"
        style={{ background: swatchColor }}
      />
      <span className="truncate font-mono text-[12px] text-ink-1">{run.id.slice(0, 8)}</span>
    </label>
  );
}

export function RunSelector({
  runs,
  selectedRunIds,
  onSelectionChange,
}: RunSelectorProps): React.JSX.Element {
  const toggleRun = (runId: string): void => {
    const isSelected = selectedRunIds.includes(runId);
    if (isSelected) {
      onSelectionChange(selectedRunIds.filter((candidate) => candidate !== runId));
    } else {
      onSelectionChange([...selectedRunIds, runId]);
    }
  };

  return (
    <Card>
      <CardHeader className="py-3">
        <CardTitle>Runs</CardTitle>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-ink-3">
          {selectedRunIds.length}/{runs.length}
        </span>
      </CardHeader>
      <CardContent className="flex flex-col gap-1 py-3">
        {runs.length === 0 ? (
          <p className="font-mono text-[11px] text-ink-3">No runs available.</p>
        ) : (
          runs.map((run) => (
            <RunCheckRow
              key={run.id}
              run={run}
              isSelected={selectedRunIds.includes(run.id)}
              onToggle={() => toggleRun(run.id)}
            />
          ))
        )}
      </CardContent>
    </Card>
  );
}
