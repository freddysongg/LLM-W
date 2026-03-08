import * as React from "react";
import { Button } from "@/components/ui/button";

interface RequestFullTensorButtonProps {
  readonly snapshotId: string;
  readonly isRequesting: boolean;
  readonly onRequest: (snapshotId: string) => void;
}

export function RequestFullTensorButton({
  snapshotId,
  isRequesting,
  onRequest,
}: RequestFullTensorButtonProps): React.JSX.Element {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={() => onRequest(snapshotId)}
        disabled={isRequesting}
      >
        {isRequesting ? "Requesting…" : "Request Full Tensors (Tier 2)"}
      </Button>
      <p className="text-xs text-muted-foreground">
        Captures full activation tensors to disk. May use significant storage.
      </p>
    </div>
  );
}
