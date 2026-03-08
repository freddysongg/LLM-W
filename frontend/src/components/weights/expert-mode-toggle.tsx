import * as React from "react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

interface ExpertModeToggleProps {
  readonly isEnabled: boolean;
  readonly onToggle: (enabled: boolean) => void;
}

export function ExpertModeToggle({
  isEnabled,
  onToggle,
}: ExpertModeToggleProps): React.JSX.Element {
  return (
    <div className="flex items-start gap-3 p-3 border rounded-md bg-muted/30">
      <Switch id="expert-mode" checked={isEnabled} onCheckedChange={onToggle} className="mt-0.5" />
      <div>
        <Label htmlFor="expert-mode" className="text-sm font-medium cursor-pointer">
          Expert Edit Mode
        </Label>
        <p className="text-xs text-muted-foreground mt-0.5">
          Enables bounded tensor editing. A checkpoint backup is created automatically before any
          edit. Use with caution — edits may destabilize training.
        </p>
      </div>
    </div>
  );
}
