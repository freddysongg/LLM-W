import type { VoiceSessionEventEnvelope } from "@/types/voice";

type ControlHandler = (envelope: VoiceSessionEventEnvelope) => void;
type AudioHandler = (chunk: ArrayBuffer) => void;
type CloseHandler = (event: { readonly code: number; readonly reason: string }) => void;

interface ConnectParams {
  readonly websocketPath: string;
  readonly onControl: ControlHandler;
  readonly onAudio: AudioHandler;
  readonly onClose: CloseHandler;
}

function buildWsUrl(websocketPath: string): string {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = window.location.host;
  const normalized = websocketPath.startsWith("/") ? websocketPath : `/${websocketPath}`;
  return `${protocol}//${host}${normalized}`;
}

export class VoiceWebSocketClient {
  private socket: WebSocket | null = null;
  private onClose: CloseHandler | null = null;

  async connect({ websocketPath, onControl, onAudio, onClose }: ConnectParams): Promise<void> {
    const socket = new WebSocket(buildWsUrl(websocketPath));
    socket.binaryType = "arraybuffer";
    this.socket = socket;
    this.onClose = onClose;

    await new Promise<void>((resolve, reject) => {
      socket.onopen = () => resolve();
      socket.onerror = () => reject(new Error("Voice WebSocket failed to open"));
    });

    socket.onmessage = (event: MessageEvent<string | ArrayBuffer>) => {
      const { data } = event;
      if (typeof data === "string") {
        try {
          const envelope = JSON.parse(data) as VoiceSessionEventEnvelope;
          onControl(envelope);
        } catch {
          // Malformed control frame — drop silently; the backend is the source of truth
        }
        return;
      }
      onAudio(data);
    };

    socket.onclose = (event: CloseEvent) => {
      this.socket = null;
      this.onClose?.({ code: event.code, reason: event.reason });
    };

    socket.onerror = () => {
      // onerror is always followed by onclose — cleanup happens there
    };
  }

  sendAudio({ chunk }: { chunk: ArrayBuffer }): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    this.socket.send(chunk);
  }

  sendControl({ message }: { message: VoiceSessionEventEnvelope }): void {
    if (this.socket?.readyState !== WebSocket.OPEN) return;
    this.socket.send(JSON.stringify(message));
  }

  close(): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.sendControl({ message: { type: "session_end", payload: {} } });
      this.socket.close(1000, "client_closed");
    }
    this.socket = null;
  }

  get isOpen(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }
}
