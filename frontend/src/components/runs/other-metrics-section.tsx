import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

import { ChartBox } from "@/components/shared/chart-box";
import { Sparkline } from "@/components/shared/sparkline";
import { useMetricNames } from "@/hooks/useMetricNames";
import type { MetricPoint } from "@/types/run";

const CANONICAL_METRICS: ReadonlySet<string> = new Set([
  "train_loss",
  "eval_loss",
  "grad_norm",
  "learning_rate",
]);

const OTHER_METRIC_COLOR = "oklch(0.70 0.12 200)";

interface OtherMetricsSectionProps {
  readonly projectId: string;
  readonly runId: string;
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

export function OtherMetricsSection({
  projectId,
  runId,
  metricPoints,
}: OtherMetricsSectionProps): React.JSX.Element | null {
  const [isOpen, setIsOpen] = React.useState(false);
  const [expandedName, setExpandedName] = React.useState<string | null>(null);
  const { data } = useMetricNames({ projectId, runId });

  const otherNames = React.useMemo(
    () => (data?.metricNames ?? []).filter((name) => !CANONICAL_METRICS.has(name)),
    [data?.metricNames],
  );

  if (otherNames.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-muted/10">
      <button
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        className="flex w-full items-center gap-2 px-3 py-2 text-[11px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground"
      >
        {isOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Other metrics ({otherNames.length})
      </button>
      {isOpen ? (
        <div className="divide-y divide-border">
          {otherNames.map((name) => (
            <OtherMetricRow
              key={name}
              name={name}
              isExpanded={expandedName === name}
              onToggle={() => setExpandedName((current) => (current === name ? null : name))}
              metricPoints={metricPoints}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

interface OtherMetricRowProps {
  readonly name: string;
  readonly isExpanded: boolean;
  readonly onToggle: () => void;
  readonly metricPoints: ReadonlyArray<MetricPoint>;
}

function OtherMetricRow({
  name,
  isExpanded,
  onToggle,
  metricPoints,
}: OtherMetricRowProps): React.JSX.Element {
  const series = React.useMemo(
    () =>
      metricPoints
        .filter((point) => point.metricName === name)
        .slice()
        .sort((left, right) => left.step - right.step),
    [metricPoints, name],
  );
  const values = React.useMemo(() => series.map((point) => point.metricValue), [series]);
  const latest = values.length > 0 ? values[values.length - 1] : null;

  return (
    <div className="px-3 py-2">
      <button type="button" onClick={onToggle} className="flex w-full items-center gap-3 text-left">
        <span className="flex-1 font-mono text-xs text-foreground">{name}</span>
        {latest !== null ? (
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {latest.toFixed(4)}
          </span>
        ) : null}
        <div className="h-6 w-24">
          <Sparkline data={values} height={24} color={OTHER_METRIC_COLOR} />
        </div>
      </button>
      {isExpanded && series.length > 0 ? (
        <div className="mt-2">
          <ChartBox
            title={name}
            series={[
              {
                key: name,
                label: name,
                color: OTHER_METRIC_COLOR,
                data: series.map((point) => ({ x: point.step, y: point.metricValue })),
              },
            ]}
            height={200}
          />
        </div>
      ) : null}
    </div>
  );
}
