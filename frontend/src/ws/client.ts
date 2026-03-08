import type { ClientMessage, WebSocketChannel, WebSocketEnvelope } from "@/types/websocket";

const WS_BASE_URL = `ws://${window.location.hostname}:8000/ws`;
const RECONNECT_BASE_DELAY_MS = 1000;
const RECONNECT_MAX_DELAY_MS = 30000;
const PING_INTERVAL_MS = 20000;

type MessageHandler = (envelope: WebSocketEnvelope) => void;

interface ConnectionState {
  readonly isConnected: boolean;
  readonly projectId: string | null;
}

type ConnectionListener = (state: ConnectionState) => void;

export class RunWebSocketClient {
  private socket: WebSocket | null = null;
  private projectId: string | null = null;
  private readonly messageHandlers = new Set<MessageHandler>();
  private readonly connectionListeners = new Set<ConnectionListener>();
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private isManuallyClosed = false;
  private subscribedChannels: ReadonlyArray<WebSocketChannel> = [];

  connect({
    projectId,
    channels,
  }: {
    projectId: string;
    channels: ReadonlyArray<WebSocketChannel>;
  }): void {
    if (this.socket?.readyState === WebSocket.OPEN && this.projectId === projectId) {
      return;
    }
    this.isManuallyClosed = false;
    this.projectId = projectId;
    this.subscribedChannels = channels;
    this.openSocket();
  }

  disconnect(): void {
    this.isManuallyClosed = true;
    this.clearTimers();
    this.socket?.close();
    this.socket = null;
    this.projectId = null;
    this.notifyConnectionListeners(false);
  }

  subscribe({ channels }: { channels: ReadonlyArray<WebSocketChannel> }): void {
    this.subscribedChannels = channels;
    this.send({ type: "subscribe", payload: { channels } });
  }

  unsubscribe({ channels }: { channels: ReadonlyArray<WebSocketChannel> }): void {
    this.subscribedChannels = this.subscribedChannels.filter((c) => !channels.includes(c));
    this.send({ type: "unsubscribe", payload: { channels } });
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.add(handler);
    return () => {
      this.messageHandlers.delete(handler);
    };
  }

  onConnectionChange(listener: ConnectionListener): () => void {
    this.connectionListeners.add(listener);
    return () => {
      this.connectionListeners.delete(listener);
    };
  }

  get isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private openSocket(): void {
    if (!this.projectId) return;

    const url = `${WS_BASE_URL}/${this.projectId}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.notifyConnectionListeners(true);
      if (this.subscribedChannels.length > 0) {
        this.send({ type: "subscribe", payload: { channels: this.subscribedChannels } });
      }
      this.startPing();
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const envelope = JSON.parse(event.data) as WebSocketEnvelope;
        for (const handler of this.messageHandlers) {
          handler(envelope);
        }
      } catch {
        // Malformed frame — ignore
      }
    };

    socket.onclose = () => {
      this.clearPingTimer();
      this.notifyConnectionListeners(false);
      if (!this.isManuallyClosed) {
        this.scheduleReconnect();
      }
    };

    socket.onerror = () => {
      // onerror always followed by onclose — reconnect handled there
    };
  }

  private send(message: ClientMessage): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify(message));
    }
  }

  private scheduleReconnect(): void {
    const delay = Math.min(
      RECONNECT_BASE_DELAY_MS * Math.pow(2, this.reconnectAttempt),
      RECONNECT_MAX_DELAY_MS,
    );
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.openSocket();
    }, delay);
  }

  private startPing(): void {
    this.pingTimer = setInterval(() => {
      this.send({ type: "ping", payload: {} });
    }, PING_INTERVAL_MS);
  }

  private clearPingTimer(): void {
    if (this.pingTimer !== null) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private clearTimers(): void {
    this.clearPingTimer();
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private notifyConnectionListeners(isConnected: boolean): void {
    const state: ConnectionState = { isConnected, projectId: this.projectId };
    for (const listener of this.connectionListeners) {
      listener(state);
    }
  }
}

export const wsClient = new RunWebSocketClient();
