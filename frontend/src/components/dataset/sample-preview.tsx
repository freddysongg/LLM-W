import * as React from "react";
import type { DatasetSample } from "@/types/dataset";
import { ChatSample, type ChatMessage } from "@/components/dataset/chat-sample";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ScrollArea } from "@/components/ui/scroll-area";

interface SamplePreviewProps {
  readonly samples: ReadonlyArray<DatasetSample>;
  readonly detectedFields: ReadonlyArray<string>;
}

const CHAT_ROLES = new Set(["system", "user", "assistant", "tool", "function"]);

function isChatMessage(candidate: unknown): candidate is ChatMessage {
  if (!candidate || typeof candidate !== "object") return false;
  const record = candidate as Record<string, unknown>;
  return (
    typeof record.role === "string" &&
    typeof record.content === "string" &&
    CHAT_ROLES.has(record.role)
  );
}

function extractChatMessages(row: Record<string, unknown>): ReadonlyArray<ChatMessage> | null {
  const candidate = row.messages;
  if (!Array.isArray(candidate)) return null;
  const messages: ChatMessage[] = [];
  for (const entry of candidate) {
    if (!isChatMessage(entry)) return null;
    messages.push(entry);
  }
  return messages.length > 0 ? messages : null;
}

function truncate(value: unknown, maxLength = 120): string {
  const serialized = typeof value === "string" ? value : JSON.stringify(value);
  return serialized.length > maxLength ? serialized.slice(0, maxLength) + "…" : serialized;
}

export function SamplePreview({ samples, detectedFields }: SamplePreviewProps): React.JSX.Element {
  if (samples.length === 0) {
    return (
      <div className="flex h-24 items-center justify-center rounded-md border border-hairline font-mono text-[11px] text-ink-3">
        No samples available.
      </div>
    );
  }

  const chatRenderedSamples = samples
    .map((sample) => ({ sample, messages: extractChatMessages(sample.row) }))
    .filter(
      (
        entry,
      ): entry is {
        readonly sample: DatasetSample;
        readonly messages: ReadonlyArray<ChatMessage>;
      } => entry.messages !== null,
    );

  if (chatRenderedSamples.length === samples.length && chatRenderedSamples.length > 0) {
    return (
      <div className="flex flex-col gap-2.5">
        {chatRenderedSamples.map(({ sample, messages }) => (
          <ChatSample key={sample.index} messages={messages} />
        ))}
      </div>
    );
  }

  const columns = detectedFields.length > 0 ? detectedFields : Object.keys(samples[0]?.row ?? {});

  return (
    <ScrollArea className="h-64 rounded-md border border-hairline">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-12 text-xs">#</TableHead>
            {columns.map((col) => (
              <TableHead key={col} className="text-xs">
                {col}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {samples.map(({ index, row }) => (
            <TableRow key={index}>
              <TableCell className="text-xs text-muted-foreground">{index}</TableCell>
              {columns.map((col) => (
                <TableCell key={col} className="max-w-xs text-xs">
                  <span
                    title={
                      typeof row[col] === "string" ? (row[col] as string) : JSON.stringify(row[col])
                    }
                  >
                    {truncate(row[col])}
                  </span>
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </ScrollArea>
  );
}
