import * as React from "react";
import type { QualityWarning } from "@/types/dataset";

interface QualityWarningsProps {
  readonly warnings: ReadonlyArray<QualityWarning>;
  readonly duplicateCount: number;
  readonly malformedCount: number;
}

interface WarningRowProps {
  readonly code: string;
  readonly message: string;
  readonly count: number | null;
}

function WarningRow({ code, message, count }: WarningRowProps): React.JSX.Element {
  return (
    <div className="flex items-start gap-3 rounded-md border border-yellow-200 bg-yellow-50 dark:border-yellow-900/40 dark:bg-yellow-900/10 px-3 py-2">
      <span className="mt-0.5 text-yellow-600 dark:text-yellow-400 text-xs">⚠</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-yellow-800 dark:text-yellow-300 font-mono">
            {code}
          </span>
          {count !== null && (
            <span className="text-xs text-yellow-600 dark:text-yellow-400">
              ({count.toLocaleString()} affected)
            </span>
          )}
        </div>
        <p className="text-xs text-yellow-700 dark:text-yellow-400 mt-0.5">{message}</p>
      </div>
    </div>
  );
}

export function QualityWarnings({
  warnings,
  duplicateCount,
  malformedCount,
}: QualityWarningsProps): React.JSX.Element {
  const hasIssues = warnings.length > 0 || duplicateCount > 0 || malformedCount > 0;

  if (!hasIssues) {
    return (
      <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 dark:border-green-900/40 dark:bg-green-900/10 px-3 py-2">
        <span className="text-green-600 dark:text-green-400 text-xs">✓</span>
        <span className="text-xs text-green-700 dark:text-green-400">
          No quality issues detected.
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {duplicateCount > 0 && (
        <WarningRow
          code="DUPLICATES"
          message="Exact duplicate rows detected in the dataset."
          count={duplicateCount}
        />
      )}
      {malformedCount > 0 && (
        <WarningRow
          code="MALFORMED"
          message="Rows with missing fields or empty values detected."
          count={malformedCount}
        />
      )}
      {warnings.map((w, i) => (
        <WarningRow key={`${w.code}-${i}`} code={w.code} message={w.message} count={w.count} />
      ))}
    </div>
  );
}
