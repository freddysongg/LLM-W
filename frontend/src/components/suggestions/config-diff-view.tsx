import type { SuggestionConfigDiff } from "@/types/suggestion";

interface ConfigDiffViewProps {
  readonly configDiff: SuggestionConfigDiff;
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

export function ConfigDiffView({ configDiff }: ConfigDiffViewProps): React.JSX.Element {
  const entries = Object.entries(configDiff);

  if (entries.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">No configuration changes suggested.</p>
    );
  }

  return (
    <div className="rounded-md border overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-muted/50">
          <tr>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Parameter</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Current</th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Suggested</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([path, change]) => (
            <tr key={path} className="border-t">
              <td className="px-3 py-2 font-mono text-xs">{path}</td>
              <td className="px-3 py-2 text-muted-foreground">{formatValue(change.current)}</td>
              <td className="px-3 py-2 font-semibold text-foreground">
                {formatValue(change.suggested)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
