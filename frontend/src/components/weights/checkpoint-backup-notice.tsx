import * as React from "react";

export function CheckpointBackupNotice(): React.JSX.Element {
  return (
    <div className="flex items-start gap-2 p-3 border border-yellow-500/30 bg-yellow-50/50 dark:bg-yellow-950/20 rounded-md text-xs">
      <span className="mt-0.5">⚠️</span>
      <div className="space-y-1">
        <p className="font-medium text-yellow-800 dark:text-yellow-200">
          Checkpoint backup will be created
        </p>
        <p className="text-yellow-700 dark:text-yellow-300">
          Before any edit is applied, a full checkpoint backup is saved automatically. You can
          revert to the pre-edit state at any time using the revert button.
        </p>
      </div>
    </div>
  );
}
