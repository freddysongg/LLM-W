import * as React from "react";

export interface ChatMessage {
  readonly role: string;
  readonly content: string;
}

interface ChatSampleProps {
  readonly messages: ReadonlyArray<ChatMessage>;
}

export function ChatSample({ messages }: ChatSampleProps): React.JSX.Element {
  return (
    <div className="grid grid-cols-[80px_1fr] gap-x-[14px] gap-y-2.5 rounded-md border border-hairline bg-surface-2 px-3 py-2.5">
      {messages.map((message, index) => (
        <React.Fragment key={index}>
          <div className="pt-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">
            {message.role}
          </div>
          <div className="text-[13px] leading-[1.5] text-ink-1">{message.content}</div>
        </React.Fragment>
      ))}
    </div>
  );
}
