import * as React from "react";
import type { RunStage, StageStatus } from "@/types/run";
import { Timeline } from "@/components/shared/timeline";
import type { TimelineItem, TimelineStatus } from "@/components/shared/timeline";

interface RunTimelineProps {
  readonly stages: ReadonlyArray<RunStage>;
  readonly selectedStageId: string | null;
  readonly onSelectStage: (stageId: string) => void;
}

function mapStageStatus(status: StageStatus): TimelineStatus {
  switch (status) {
    case "completed":
      return "done";
    case "running":
      return "running";
    case "failed":
      return "failed";
    case "skipped":
      return "pending";
    case "pending":
      return "pending";
    default: {
      const _exhaustive: never = status;
      return _exhaustive;
    }
  }
}

function formatDuration(durationMs: number | null): string | undefined {
  if (durationMs === null) return undefined;
  const totalSeconds = Math.round(durationMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes.toString().padStart(2, "0")}:${seconds.toString().padStart(2, "0")}`;
}

function humanizeStageName(stageName: string): string {
  return stageName
    .split("_")
    .map((segment) => (segment.length === 0 ? "" : segment[0].toUpperCase() + segment.slice(1)))
    .join(" ");
}

export function RunTimeline({
  stages,
  selectedStageId,
  onSelectStage,
}: RunTimelineProps): React.JSX.Element {
  if (stages.length === 0) {
    return (
      <div className="py-6 text-center font-mono text-[11px] text-ink-3">No stage data yet.</div>
    );
  }

  const sorted = React.useMemo(() => {
    return [...stages].sort((left, right) => left.stageOrder - right.stageOrder);
  }, [stages]);

  const items = React.useMemo<ReadonlyArray<TimelineItem>>(() => {
    return sorted.map<TimelineItem>((stage, index) => ({
      id: stage.id,
      title: humanizeStageName(stage.stageName),
      sub: stage.outputSummary ?? undefined,
      meta: formatDuration(stage.durationMs),
      status: mapStageStatus(stage.status),
      number: index + 1,
    }));
  }, [sorted]);

  return (
    <Timeline items={items} activeId={selectedStageId ?? undefined} onSelect={onSelectStage} />
  );
}
