import * as React from "react";
import type { LogEntry } from "@/types/run";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface LogStreamProps {
  readonly logs: ReadonlyArray<LogEntry>;
}

type LogSeverity = LogEntry["severity"];
type SeverityFilter = "all" | LogSeverity;

const SEVERITY_ORDER: Record<LogSeverity, number> = {
  debug: 0,
  info: 1,
  warning: 2,
  error: 3,
  critical: 4,
};

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

function severityVariant(severity: LogSeverity): BadgeVariant {
  switch (severity) {
    case "critical":
    case "error":
      return "destructive";
    case "warning":
      return "outline";
    case "info":
      return "secondary";
    case "debug":
      return "outline";
    default: {
      const _exhaustive: never = severity;
      return _exhaustive;
    }
  }
}

function severityTextClass(severity: LogSeverity): string {
  switch (severity) {
    case "critical":
    case "error":
      return "text-destructive";
    case "warning":
      return "text-yellow-600";
    case "info":
      return "text-foreground";
    case "debug":
      return "text-muted-foreground";
    default: {
      const _exhaustive: never = severity;
      return _exhaustive;
    }
  }
}

export function LogStream({ logs }: LogStreamProps): React.JSX.Element {
  const [severityFilter, setSeverityFilter] = React.useState<SeverityFilter>("info");
  const [stageFilter, setStageFilter] = React.useState("all");
  const scrollRef = React.useRef<HTMLDivElement>(null);
  const [isAutoScroll, setIsAutoScroll] = React.useState(true);

  const stages = React.useMemo(() => {
    const seen = new Set<string>();
    for (const log of logs) {
      if (log.stage) seen.add(log.stage);
    }
    return Array.from(seen);
  }, [logs]);

  const filtered = React.useMemo(() => {
    const minSeverity =
      severityFilter === "all" ? -1 : SEVERITY_ORDER[severityFilter as LogSeverity];
    return logs.filter((log) => {
      const severityOk = severityFilter === "all" || SEVERITY_ORDER[log.severity] >= minSeverity;
      const stageOk = stageFilter === "all" || log.stage === stageFilter;
      return severityOk && stageOk;
    });
  }, [logs, severityFilter, stageFilter]);

  React.useEffect(() => {
    if (isAutoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [filtered, isAutoScroll]);

  const handleScroll = (): void => {
    if (!scrollRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
    setIsAutoScroll(scrollHeight - scrollTop - clientHeight < 40);
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      <div className="flex items-center gap-3 mb-2 shrink-0">
        <Select
          value={severityFilter}
          onValueChange={(val) => setSeverityFilter(val as SeverityFilter)}
        >
          <SelectTrigger className="h-7 text-xs w-28">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All levels</SelectItem>
            <SelectItem value="debug">Debug+</SelectItem>
            <SelectItem value="info">Info+</SelectItem>
            <SelectItem value="warning">Warning+</SelectItem>
            <SelectItem value="error">Error+</SelectItem>
            <SelectItem value="critical">Critical</SelectItem>
          </SelectContent>
        </Select>

        {stages.length > 0 && (
          <Select value={stageFilter} onValueChange={setStageFilter}>
            <SelectTrigger className="h-7 text-xs w-40">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All stages</SelectItem>
              {stages.map((stage) => (
                <SelectItem key={stage} value={stage}>
                  {stage.replace(/_/g, " ")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        <span className="text-xs text-muted-foreground ml-auto">
          {filtered.length} lines
          {!isAutoScroll && (
            <button type="button" className="ml-2 underline" onClick={() => setIsAutoScroll(true)}>
              scroll to bottom
            </button>
          )}
        </span>
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto font-mono text-xs bg-muted/30 rounded-md border p-2 space-y-0.5"
      >
        {filtered.length === 0 && (
          <div className="py-4 text-center text-muted-foreground">No log entries.</div>
        )}
        {filtered.map((log, idx) => (
          <div key={idx} className="flex items-start gap-2">
            <Badge
              variant={severityVariant(log.severity)}
              className="text-[10px] px-1 py-0 shrink-0"
            >
              {log.severity.slice(0, 4).toUpperCase()}
            </Badge>
            {log.stage && (
              <span className="text-[10px] text-muted-foreground shrink-0">
                [{log.stage.replace(/_/g, ".")}]
              </span>
            )}
            <span className={`break-all ${severityTextClass(log.severity)}`}>{log.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
