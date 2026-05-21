import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceSessionControls } from "./voice-session-controls";
import type { VoiceSessionStatus } from "@/types/voice";

interface LabelExpectation {
  readonly status: VoiceSessionStatus;
  readonly statusLabel: string;
  readonly buttonLabel: string;
}

const STATUS_LABEL_CASES: ReadonlyArray<LabelExpectation> = [
  { status: "idle", statusLabel: "Idle", buttonLabel: "Start session" },
  { status: "connecting", statusLabel: "Connecting…", buttonLabel: "Stop" },
  { status: "active", statusLabel: "Active", buttonLabel: "Stop" },
  { status: "failed", statusLabel: "Failed", buttonLabel: "Start session" },
  { status: "finalized", statusLabel: "Session ended", buttonLabel: "Start session" },
];

function renderControls({
  status,
  canStart = true,
}: {
  status: VoiceSessionStatus;
  canStart?: boolean;
}): void {
  render(
    <VoiceSessionControls
      status={status}
      canStart={canStart}
      onStart={() => undefined}
      onStop={() => undefined}
    />,
  );
}

describe("VoiceSessionControls", () => {
  it.each(STATUS_LABEL_CASES)(
    "shows status label '$statusLabel' and button '$buttonLabel' when status is $status",
    ({ status, statusLabel, buttonLabel }) => {
      renderControls({ status });

      expect(screen.getByText(statusLabel)).toBeInTheDocument();
      expect(screen.getByRole("button", { name: new RegExp(buttonLabel) })).toBeInTheDocument();
    },
  );

  it("disables the start button when canStart is false", () => {
    renderControls({ status: "idle", canStart: false });

    const startButton = screen.getByRole("button", { name: /Start session/ });
    expect(startButton).toBeDisabled();
  });

  it("enables the stop button while connecting even when canStart is false", () => {
    renderControls({ status: "connecting", canStart: false });

    const stopButton = screen.getByRole("button", { name: /Stop/ });
    expect(stopButton).toBeEnabled();
  });
});
