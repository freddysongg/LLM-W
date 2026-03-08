import * as React from "react";
import { Button } from "@/components/ui/button";

interface DatasetResolveButtonProps {
  readonly isPending: boolean;
  readonly isDisabled: boolean;
  readonly onResolve: () => void;
}

export function DatasetResolveButton({
  isPending,
  isDisabled,
  onResolve,
}: DatasetResolveButtonProps): React.JSX.Element {
  return (
    <Button type="button" onClick={onResolve} disabled={isDisabled || isPending} className="w-full">
      {isPending ? "Resolving…" : "Resolve & Profile Dataset"}
    </Button>
  );
}
