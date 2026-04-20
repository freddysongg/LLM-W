import * as React from "react";
import type { LogEntry } from "@/types/run";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { LogStream as SharedLogStream, LogStreamToolbar } from "@/components/shared/log-stream";
import type { LogLevel, LogLine } from "@/components/shared/log-stream";

interface LogStreamProps {
  readonly logs: ReadonlyArray<LogEntry>;
}

const ALL_LEVELS: ReadonlyArray<LogLevel> = ["info", "warn", "err", "debug", "ok"];

function mapSeverity(severity: LogEntry["severity"]): LogLevel {
  switch (severity) {
    case "critical":
    case "error":
      return "err";
    case "warning":
      return "warn";
    case "info":
      return "info";
    case "debug":
      return "debug";
    default: {
      const _exhaustive: never = severity;
      return _exhaustive;
    }
  }
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function composeMessage(entry: LogEntry): string {
  if (!entry.stage) return entry.message;
  return `[${entry.stage}] ${entry.message}`;
}

export function LogStream({ logs }: LogStreamProps): React.JSX.Element {
  const [activeLevels, setActiveLevels] = React.useState<ReadonlyArray<LogLevel>>(ALL_LEVELS);

  const lines = React.useMemo<ReadonlyArray<LogLine>>(() => {
    return logs.map<LogLine>((entry) => ({
      ts: formatTimestamp(entry.timestamp),
      level: mapSeverity(entry.severity),
      msg: composeMessage(entry),
    }));
  }, [logs]);

  return (
    <Card className="flex min-h-[320px] flex-col">
      <CardHeader>
        <CardTitle>Log stream</CardTitle>
        <div className="flex items-center gap-2">
          <Badge variant="running">streaming</Badge>
          <LogStreamToolbar value={activeLevels} onChange={setActiveLevels} />
        </div>
      </CardHeader>
      <div className="p-[18px]">
        <SharedLogStream lines={lines} filter={activeLevels} height={320} />
      </div>
    </Card>
  );
}
