import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { VoiceTranscript } from "./voice-transcript";
import type { TranscriptEntry } from "@/types/voice";

const SCROLL_HEIGHT_PX = 480;

function buildEntry({
  index,
  role,
  text,
  isInterim = false,
}: {
  index: number;
  role: "user" | "assistant";
  text: string;
  isInterim?: boolean;
}): TranscriptEntry {
  return {
    index,
    role,
    text,
    startedAt: "2025-01-01T00:00:00.000Z",
    endedAt: null,
    isInterim,
  };
}

function getScrollContainer(): HTMLDivElement {
  const containers = document.querySelectorAll<HTMLDivElement>("div.h-full.overflow-y-auto");
  if (containers.length !== 1) {
    throw new Error(`expected exactly one scroll container, found ${containers.length}`);
  }
  return containers[0];
}

describe("VoiceTranscript", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLDivElement.prototype, "scrollHeight", {
      configurable: true,
      get: () => SCROLL_HEIGHT_PX,
    });
  });

  it("renders entry text and role labels", () => {
    const entries: ReadonlyArray<TranscriptEntry> = [
      buildEntry({ index: 0, role: "user", text: "Hello there" }),
      buildEntry({ index: 1, role: "assistant", text: "Hi, how can I help?" }),
      buildEntry({ index: 2, role: "user", text: "What is two plus two?" }),
    ];

    render(<VoiceTranscript entries={entries} />);

    expect(screen.getByText("Hello there")).toBeInTheDocument();
    expect(screen.getByText("Hi, how can I help?")).toBeInTheDocument();
    expect(screen.getByText("What is two plus two?")).toBeInTheDocument();

    const userLabels = screen.getAllByText("user");
    expect(userLabels).toHaveLength(2);
    expect(screen.getByText("assistant")).toBeInTheDocument();
  });

  it("shows interim indicator on partial entries", () => {
    const entries: ReadonlyArray<TranscriptEntry> = [
      buildEntry({ index: 0, role: "user", text: "partial speech", isInterim: true }),
    ];

    render(<VoiceTranscript entries={entries} />);

    expect(screen.getByText(/interim/)).toBeInTheDocument();
  });

  it("renders the empty-state hint when no entries are present", () => {
    render(<VoiceTranscript entries={[]} />);

    expect(screen.getByText(/Transcript will appear here/)).toBeInTheDocument();
  });

  it("scrolls to bottom after a new entry is appended", () => {
    const initialEntries: ReadonlyArray<TranscriptEntry> = [
      buildEntry({ index: 0, role: "user", text: "first" }),
      buildEntry({ index: 1, role: "assistant", text: "second" }),
    ];

    const { rerender } = render(<VoiceTranscript entries={initialEntries} />);

    const container = getScrollContainer();
    container.scrollTop = 0;

    const updatedEntries: ReadonlyArray<TranscriptEntry> = [
      ...initialEntries,
      buildEntry({ index: 2, role: "user", text: "third" }),
    ];
    rerender(<VoiceTranscript entries={updatedEntries} />);

    expect(container.scrollTop).toBe(SCROLL_HEIGHT_PX);
  });
});
