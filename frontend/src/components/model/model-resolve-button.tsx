import * as React from "react";
import { Button } from "@/components/ui/button";

interface ModelResolveButtonProps {
  readonly onResolve: () => void;
  readonly isResolving: boolean;
  readonly isDisabled: boolean;
}

export function ModelResolveButton({
  onResolve,
  isResolving,
  isDisabled,
}: ModelResolveButtonProps): React.JSX.Element {
  return (
    <Button onClick={onResolve} disabled={isDisabled || isResolving}>
      {isResolving ? "Resolving..." : "Resolve Model"}
    </Button>
  );
}
