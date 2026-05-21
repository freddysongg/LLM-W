export type VoiceSessionStatus = "idle" | "connecting" | "active" | "failed" | "finalized";

export type VoiceEventType =
  | "transcript"
  | "tool_call"
  | "tool_result"
  | "agent_text"
  | "error"
  | "session_end";

export type VoiceTerminationReason =
  | "session_end"
  | "client_disconnect"
  | "pipeline_error"
  | "session_timeout";

export interface VoiceSessionCreateRequest {
  readonly system_prompt: string;
  readonly cartesia_voice_id: string;
  readonly openai_model_id?: string;
}

export interface VoiceSessionCreateResponse {
  readonly session_id: string;
  readonly websocket_path: string;
  readonly artifact_path: string;
  readonly status: "pending" | "active" | "completed" | "failed";
}

export interface VoiceSessionEventEnvelope {
  readonly type: VoiceEventType;
  readonly payload: Record<string, unknown>;
}

export interface TranscriptEntry {
  readonly index: number;
  readonly role: "user" | "assistant";
  readonly text: string;
  readonly startedAt: string;
  readonly endedAt: string | null;
  readonly isInterim: boolean;
}

export interface ToolTraceEntry {
  readonly index: number;
  readonly toolCallId: string;
  readonly name: string;
  readonly arguments: Record<string, unknown>;
  readonly result: Record<string, unknown> | null;
  readonly startedAt: string;
  readonly endedAt: string | null;
  readonly durationMs: number | null;
}
