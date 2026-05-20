import * as React from "react";
import { createVoiceSession } from "@/api/voice";
import { VoiceWebSocketClient } from "@/ws/voice-client";
import type {
  ToolTraceEntry,
  TranscriptEntry,
  VoiceSessionCreateRequest,
  VoiceSessionEventEnvelope,
  VoiceSessionStatus,
} from "@/types/voice";

const CAPTURE_SAMPLE_RATE = 16_000;
const PLAYBACK_SAMPLE_RATE = 24_000;
const RECORDER_WORKLET_URL = "/pcm-recorder-worklet.js";

interface SessionInfo {
  readonly sessionId: string;
  readonly artifactPath: string;
}

interface VoiceSessionState {
  readonly status: VoiceSessionStatus;
  readonly transcript: ReadonlyArray<TranscriptEntry>;
  readonly toolTrace: ReadonlyArray<ToolTraceEntry>;
  readonly session: SessionInfo | null;
  readonly lastError: string | null;
}

const INITIAL_STATE: VoiceSessionState = {
  status: "idle",
  transcript: [],
  toolTrace: [],
  session: null,
  lastError: null,
};

interface TranscriptPayload {
  readonly role?: unknown;
  readonly text?: unknown;
  readonly started_at?: unknown;
  readonly ended_at?: unknown;
  readonly is_interim?: unknown;
}

interface ToolCallPayload {
  readonly tool_call_id?: unknown;
  readonly name?: unknown;
  readonly arguments?: unknown;
  readonly started_at?: unknown;
}

interface ToolResultPayload {
  readonly tool_call_id?: unknown;
  readonly result?: unknown;
  readonly ended_at?: unknown;
  readonly duration_ms?: unknown;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function toTranscriptEntry({
  payload,
  index,
}: {
  payload: TranscriptPayload;
  index: number;
}): TranscriptEntry | null {
  const role = payload.role === "user" || payload.role === "assistant" ? payload.role : null;
  if (role === null) return null;
  if (typeof payload.text !== "string") return null;
  return {
    index,
    role,
    text: payload.text,
    startedAt: typeof payload.started_at === "string" ? payload.started_at : "",
    endedAt: typeof payload.ended_at === "string" ? payload.ended_at : null,
    isInterim: payload.is_interim === true,
  };
}

function toToolCallEntry({
  payload,
  index,
}: {
  payload: ToolCallPayload;
  index: number;
}): ToolTraceEntry | null {
  if (typeof payload.tool_call_id !== "string" || typeof payload.name !== "string") return null;
  const args = isRecord(payload.arguments) ? payload.arguments : {};
  return {
    index,
    toolCallId: payload.tool_call_id,
    name: payload.name,
    arguments: args,
    result: null,
    startedAt: typeof payload.started_at === "string" ? payload.started_at : "",
    endedAt: null,
    durationMs: null,
  };
}

function mergeToolResult({
  entries,
  payload,
}: {
  entries: ReadonlyArray<ToolTraceEntry>;
  payload: ToolResultPayload;
}): ReadonlyArray<ToolTraceEntry> {
  if (typeof payload.tool_call_id !== "string") return entries;
  return entries.map((entry) => {
    if (entry.toolCallId !== payload.tool_call_id) return entry;
    return {
      ...entry,
      result: isRecord(payload.result) ? payload.result : {},
      endedAt: typeof payload.ended_at === "string" ? payload.ended_at : entry.endedAt,
      durationMs: typeof payload.duration_ms === "number" ? payload.duration_ms : entry.durationMs,
    };
  });
}

interface AppendTranscriptResult {
  readonly transcript: ReadonlyArray<TranscriptEntry>;
  readonly cursorDelta: number;
}

function appendTranscriptEntry({
  transcript,
  entry,
}: {
  transcript: ReadonlyArray<TranscriptEntry>;
  entry: TranscriptEntry;
}): AppendTranscriptResult {
  const trailing = transcript.length > 0 ? transcript[transcript.length - 1] : null;
  const shouldReplaceTrailing =
    !entry.isInterim &&
    trailing !== null &&
    trailing.role === entry.role &&
    trailing.isInterim === true;
  if (shouldReplaceTrailing && trailing !== null) {
    const swapped: TranscriptEntry = { ...entry, index: trailing.index };
    const next = transcript.slice(0, -1).concat(swapped);
    return { transcript: next, cursorDelta: 0 };
  }
  return { transcript: [...transcript, entry], cursorDelta: 1 };
}

interface PlaybackQueue {
  readonly context: AudioContext;
  nextStartTime: number;
}

function decodePcm16ToFloat32(buffer: ArrayBuffer): Float32Array<ArrayBuffer> {
  const view = new Int16Array(buffer);
  const out = new Float32Array(new ArrayBuffer(view.length * Float32Array.BYTES_PER_ELEMENT));
  for (let i = 0; i < view.length; i += 1) {
    out[i] = view[i] / 0x8000;
  }
  return out;
}

function schedulePlayback({ queue, chunk }: { queue: PlaybackQueue; chunk: ArrayBuffer }): void {
  if (chunk.byteLength === 0) return;
  const samples = decodePcm16ToFloat32(chunk);
  const audioBuffer = queue.context.createBuffer(1, samples.length, PLAYBACK_SAMPLE_RATE);
  audioBuffer.copyToChannel(samples, 0);

  const source = queue.context.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(queue.context.destination);

  const now = queue.context.currentTime;
  const startAt = Math.max(now, queue.nextStartTime);
  source.start(startAt);
  queue.nextStartTime = startAt + audioBuffer.duration;
}

interface CaptureResources {
  readonly stream: MediaStream;
  readonly context: AudioContext;
  readonly worklet: AudioWorkletNode;
}

async function startCapture({
  onChunk,
}: {
  onChunk: (chunk: ArrayBuffer) => void;
}): Promise<CaptureResources> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      sampleRate: CAPTURE_SAMPLE_RATE,
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  const context = new AudioContext({ sampleRate: CAPTURE_SAMPLE_RATE });
  await context.audioWorklet.addModule(RECORDER_WORKLET_URL);
  const source = context.createMediaStreamSource(stream);
  const worklet = new AudioWorkletNode(context, "pcm-recorder");
  worklet.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
    onChunk(event.data);
  };
  source.connect(worklet);
  return { stream, context, worklet };
}

function teardownCapture(resources: CaptureResources): void {
  resources.worklet.port.onmessage = null;
  resources.worklet.disconnect();
  for (const track of resources.stream.getTracks()) {
    track.stop();
  }
  void resources.context.close();
}

export interface UseVoiceSessionResult {
  readonly status: VoiceSessionStatus;
  readonly transcript: ReadonlyArray<TranscriptEntry>;
  readonly toolTrace: ReadonlyArray<ToolTraceEntry>;
  readonly session: SessionInfo | null;
  readonly lastError: string | null;
  readonly start: (request: VoiceSessionCreateRequest) => Promise<void>;
  readonly stop: () => void;
}

export function useVoiceSession(): UseVoiceSessionResult {
  const [state, setState] = React.useState<VoiceSessionState>(INITIAL_STATE);
  const wsClientRef = React.useRef<VoiceWebSocketClient | null>(null);
  const captureRef = React.useRef<CaptureResources | null>(null);
  const playbackRef = React.useRef<PlaybackQueue | null>(null);
  const transcriptCursor = React.useRef(0);
  const toolCursor = React.useRef(0);

  const stop = React.useCallback((): void => {
    if (captureRef.current) {
      teardownCapture(captureRef.current);
      captureRef.current = null;
    }
    if (playbackRef.current) {
      void playbackRef.current.context.close();
      playbackRef.current = null;
    }
    if (wsClientRef.current) {
      wsClientRef.current.close();
      wsClientRef.current = null;
    }
    setState((previous) => ({ ...previous, status: "finalized" }));
  }, []);

  const handleControl = React.useCallback((envelope: VoiceSessionEventEnvelope): void => {
    setState((previous) => {
      if (envelope.type === "transcript") {
        const entry = toTranscriptEntry({
          payload: envelope.payload as TranscriptPayload,
          index: transcriptCursor.current,
        });
        if (entry === null) return previous;
        const { transcript, cursorDelta } = appendTranscriptEntry({
          transcript: previous.transcript,
          entry,
        });
        transcriptCursor.current += cursorDelta;
        return { ...previous, transcript };
      }
      if (envelope.type === "agent_text") {
        const entry = toTranscriptEntry({
          payload: { ...envelope.payload, role: "assistant" } as TranscriptPayload,
          index: transcriptCursor.current,
        });
        if (entry === null) return previous;
        const { transcript, cursorDelta } = appendTranscriptEntry({
          transcript: previous.transcript,
          entry,
        });
        transcriptCursor.current += cursorDelta;
        return { ...previous, transcript };
      }
      if (envelope.type === "tool_call") {
        const entry = toToolCallEntry({
          payload: envelope.payload as ToolCallPayload,
          index: toolCursor.current,
        });
        if (entry === null) return previous;
        toolCursor.current += 1;
        return { ...previous, toolTrace: [...previous.toolTrace, entry] };
      }
      if (envelope.type === "tool_result") {
        return {
          ...previous,
          toolTrace: mergeToolResult({
            entries: previous.toolTrace,
            payload: envelope.payload as ToolResultPayload,
          }),
        };
      }
      if (envelope.type === "error") {
        const message =
          typeof envelope.payload.message === "string"
            ? envelope.payload.message
            : "Pipeline error";
        return { ...previous, status: "failed", lastError: message };
      }
      if (envelope.type === "session_end") {
        return { ...previous, status: "finalized" };
      }
      return previous;
    });
  }, []);

  const handleAudio = React.useCallback((chunk: ArrayBuffer): void => {
    if (!playbackRef.current) {
      const context = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE });
      playbackRef.current = { context, nextStartTime: 0 };
    }
    schedulePlayback({ queue: playbackRef.current, chunk });
  }, []);

  const handleClose = React.useCallback((): void => {
    setState((previous) =>
      previous.status === "active" ? { ...previous, status: "finalized" } : previous,
    );
  }, []);

  const start = React.useCallback(
    async (request: VoiceSessionCreateRequest): Promise<void> => {
      transcriptCursor.current = 0;
      toolCursor.current = 0;
      setState({ ...INITIAL_STATE, status: "connecting" });

      let response;
      try {
        response = await createVoiceSession({ request });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to create session";
        setState({ ...INITIAL_STATE, status: "failed", lastError: message });
        return;
      }

      const client = new VoiceWebSocketClient();
      wsClientRef.current = client;
      try {
        await client.connect({
          websocketPath: response.websocket_path,
          onControl: handleControl,
          onAudio: handleAudio,
          onClose: handleClose,
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to open WebSocket";
        wsClientRef.current = null;
        setState({ ...INITIAL_STATE, status: "failed", lastError: message });
        return;
      }

      try {
        captureRef.current = await startCapture({
          onChunk: (chunk) => {
            client.sendAudio({ chunk });
          },
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Microphone access denied";
        client.close();
        wsClientRef.current = null;
        setState({ ...INITIAL_STATE, status: "failed", lastError: message });
        return;
      }

      setState({
        ...INITIAL_STATE,
        status: "active",
        session: {
          sessionId: response.session_id,
          artifactPath: response.artifact_path,
        },
      });
    },
    [handleAudio, handleClose, handleControl],
  );

  React.useEffect(() => {
    return () => {
      stop();
    };
  }, [stop]);

  return {
    status: state.status,
    transcript: state.transcript,
    toolTrace: state.toolTrace,
    session: state.session,
    lastError: state.lastError,
    start,
    stop,
  };
}
