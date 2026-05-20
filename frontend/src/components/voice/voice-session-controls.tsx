import * as React from "react";
import { Mic, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { StatusDot, type RunStatus } from "@/components/shared/status-dot";
import type { VoiceSessionStatus } from "@/types/voice";

interface VoiceSessionControlsProps {
  readonly status: VoiceSessionStatus;
  readonly canStart: boolean;
  readonly onStart: () => void;
  readonly onStop: () => void;
}

const STATUS_DOT: Record<VoiceSessionStatus, RunStatus> = {
  idle: "pending",
  connecting: "paused",
  active: "running",
  failed: "failed",
  finalized: "pending",
};

const STATUS_LABEL: Record<VoiceSessionStatus, string> = {
  idle: "Idle",
  connecting: "Connecting…",
  active: "Active",
  failed: "Failed",
  finalized: "Session ended",
};

export function VoiceSessionControls({
  status,
  canStart,
  onStart,
  onStop,
}: VoiceSessionControlsProps): React.JSX.Element {
  const isActiveLike = status === "active" || status === "connecting";

  return (
    <div className="flex items-center gap-3">
      <span className="inline-flex items-center gap-2 font-mono text-[11px] text-ink-2">
        <StatusDot status={STATUS_DOT[status]} />
        <span>{STATUS_LABEL[status]}</span>
      </span>
      {isActiveLike ? (
        <Button variant="outline" size="sm" onClick={onStop}>
          <Square className="size-3" aria-hidden="true" />
          Stop
        </Button>
      ) : (
        <Button variant="default" size="sm" onClick={onStart} disabled={!canStart}>
          <Mic className="size-3" aria-hidden="true" />
          Start session
        </Button>
      )}
    </div>
  );
}
