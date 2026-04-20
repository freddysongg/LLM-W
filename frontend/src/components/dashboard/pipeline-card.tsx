import * as React from "react";
import { Link } from "react-router-dom";
import type { Run, RunStatus } from "@/types/run";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RangePills } from "@/components/shared/range-pills";
import { cn } from "@/lib/utils";

interface PipelineCardProps {
  readonly runs: ReadonlyArray<Run>;
}

type RangeValue = "7D" | "30D" | "ALL";
type PipelineBucket = "queued" | "running" | "completed" | "failed";

interface PipelineStage {
  readonly id: PipelineBucket;
  readonly label: string;
  readonly color: string;
  readonly count: number;
}

const RANGE_OPTIONS = [
  { value: "7D" as RangeValue, label: "7D" },
  { value: "30D" as RangeValue, label: "30D" },
  { value: "ALL" as RangeValue, label: "All" },
];

const RANGE_WINDOW_MS: Record<RangeValue, number | null> = {
  "7D": 7 * 24 * 60 * 60 * 1000,
  "30D": 30 * 24 * 60 * 60 * 1000,
  ALL: null,
};

function bucketFor(status: RunStatus): PipelineBucket {
  switch (status) {
    case "pending":
      return "queued";
    case "running":
    case "paused":
      return "running";
    case "completed":
      return "completed";
    case "failed":
    case "cancelled":
      return "failed";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function countRunsInRange({
  runs,
  range,
}: {
  readonly runs: ReadonlyArray<Run>;
  readonly range: RangeValue;
}): Record<PipelineBucket, number> {
  const windowMs = RANGE_WINDOW_MS[range];
  const cutoffTime = windowMs === null ? 0 : Date.now() - windowMs;
  const counts: Record<PipelineBucket, number> = {
    queued: 0,
    running: 0,
    completed: 0,
    failed: 0,
  };
  for (const run of runs) {
    const createdTime = new Date(run.createdAt).getTime();
    if (createdTime < cutoffTime) continue;
    counts[bucketFor(run.status)] += 1;
  }
  return counts;
}

function buildStages(counts: Record<PipelineBucket, number>): ReadonlyArray<PipelineStage> {
  return [
    { id: "queued", label: "Queued", color: "var(--ink-3)", count: counts.queued },
    { id: "running", label: "Running", color: "var(--info)", count: counts.running },
    { id: "completed", label: "Completed", color: "var(--success)", count: counts.completed },
    { id: "failed", label: "Failed", color: "var(--danger)", count: counts.failed },
  ];
}

export function PipelineCard({ runs }: PipelineCardProps): React.JSX.Element {
  const [range, setRange] = React.useState<RangeValue>("7D");
  const counts = React.useMemo(() => countRunsInRange({ runs, range }), [runs, range]);
  const stages = React.useMemo(() => buildStages(counts), [counts]);
  const total = stages.reduce((sum, stage) => sum + stage.count, 0);

  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Training pipeline</CardTitle>
          <div className="mt-0.5 font-mono text-[11px] text-ink-3">
            run.status · rolling {range.toLowerCase()}
          </div>
        </div>
        <RangePills
          options={RANGE_OPTIONS}
          value={range}
          onChange={setRange}
          ariaLabel="Pipeline range"
        />
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-end gap-4">
          {stages.map((stage) => (
            <div
              key={stage.id}
              className="flex-1 border-r border-hairline pr-3 last:border-r-0 last:pr-0"
            >
              <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
                {stage.label}
              </div>
              <div
                className="mt-1 font-mono text-[22px] font-semibold leading-none tracking-[-0.02em]"
                style={{ color: stage.color }}
              >
                {stage.count}
              </div>
            </div>
          ))}
          <div className="flex-1">
            <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">Total</div>
            <div className="mt-1 font-mono text-[22px] font-semibold leading-none tracking-[-0.02em] text-ink-1">
              {total}
            </div>
          </div>
        </div>
        <div
          aria-hidden="true"
          className={cn(
            "flex h-2 w-full overflow-hidden rounded-full bg-surface-3",
            "transition-[flex] duration-[var(--dur-3)]",
          )}
        >
          {total === 0
            ? null
            : stages.map((stage) =>
                stage.count === 0 ? null : (
                  <div key={stage.id} style={{ flex: stage.count, backgroundColor: stage.color }} />
                ),
              )}
        </div>
        <div className="flex items-center justify-between font-mono text-[11px] text-ink-3">
          <span>
            {total} run{total === 1 ? "" : "s"} in window
          </span>
          <Link to="/runs" className="inline-flex items-center gap-1 text-ink-2 hover:text-ink-1">
            View runs →
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
