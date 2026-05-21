import { describe, it, expect } from "vitest";
import { appendTranscriptEntry } from "./use-voice-session";
import type { TranscriptEntry } from "@/types/voice";

function makeEntry({
  index,
  role,
  text,
  isInterim,
}: {
  index: number;
  role: TranscriptEntry["role"];
  text: string;
  isInterim: boolean;
}): TranscriptEntry {
  return {
    index,
    role,
    text,
    startedAt: "2026-05-20T00:00:00Z",
    endedAt: isInterim ? null : "2026-05-20T00:00:01Z",
    isInterim,
  };
}

describe("appendTranscriptEntry", () => {
  it("appends when the transcript is empty", () => {
    const incoming = makeEntry({ index: 0, role: "user", text: "hi", isInterim: true });
    const result = appendTranscriptEntry({ transcript: [], entry: incoming });
    expect(result.transcript).toEqual([incoming]);
    expect(result.cursorDelta).toBe(1);
  });

  it("appends when the trailing entry is not interim", () => {
    const finalized = makeEntry({ index: 0, role: "user", text: "done", isInterim: false });
    const next = makeEntry({ index: 1, role: "user", text: "hello", isInterim: true });
    const result = appendTranscriptEntry({ transcript: [finalized], entry: next });
    expect(result.transcript).toHaveLength(2);
    expect(result.cursorDelta).toBe(1);
  });

  it("replaces trailing interim with a new interim of the same role", () => {
    const interim1 = makeEntry({ index: 0, role: "user", text: "he", isInterim: true });
    const interim2 = makeEntry({ index: 1, role: "user", text: "hello", isInterim: true });
    const result = appendTranscriptEntry({ transcript: [interim1], entry: interim2 });
    expect(result.transcript).toHaveLength(1);
    expect(result.transcript[0].text).toBe("hello");
    expect(result.transcript[0].index).toBe(0);
    expect(result.cursorDelta).toBe(0);
  });

  it("replaces trailing interim with finalized entry of the same role", () => {
    const interim = makeEntry({ index: 0, role: "assistant", text: "he", isInterim: true });
    const finalized = makeEntry({
      index: 1,
      role: "assistant",
      text: "hello world",
      isInterim: false,
    });
    const result = appendTranscriptEntry({ transcript: [interim], entry: finalized });
    expect(result.transcript).toHaveLength(1);
    expect(result.transcript[0].text).toBe("hello world");
    expect(result.transcript[0].isInterim).toBe(false);
    expect(result.transcript[0].index).toBe(0);
    expect(result.cursorDelta).toBe(0);
  });

  it("appends when trailing interim role differs from incoming role", () => {
    const userInterim = makeEntry({ index: 0, role: "user", text: "hi", isInterim: true });
    const assistantInterim = makeEntry({
      index: 1,
      role: "assistant",
      text: "hello",
      isInterim: true,
    });
    const result = appendTranscriptEntry({
      transcript: [userInterim],
      entry: assistantInterim,
    });
    expect(result.transcript).toHaveLength(2);
    expect(result.cursorDelta).toBe(1);
  });

  it("does not accumulate stale partials across a streaming sequence", () => {
    const start: ReadonlyArray<TranscriptEntry> = [];
    const a = makeEntry({ index: 0, role: "user", text: "he", isInterim: true });
    const b = makeEntry({ index: 1, role: "user", text: "hello", isInterim: true });
    const c = makeEntry({ index: 2, role: "user", text: "hello wo", isInterim: true });
    const d = makeEntry({ index: 3, role: "user", text: "hello world", isInterim: false });

    let transcript = start;
    for (const entry of [a, b, c, d]) {
      const result = appendTranscriptEntry({ transcript, entry });
      transcript = result.transcript;
    }

    expect(transcript).toHaveLength(1);
    expect(transcript[0].text).toBe("hello world");
    expect(transcript[0].isInterim).toBe(false);
  });
});
