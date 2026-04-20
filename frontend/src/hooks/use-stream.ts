import * as React from "react";

interface UseStreamParams {
  readonly intervalMs?: number;
  readonly enabled?: boolean;
}

export function useStream({ intervalMs = 1000, enabled = true }: UseStreamParams = {}): number {
  const [tick, setTick] = React.useState<number>(0);

  React.useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => {
      setTick((previous) => previous + 1);
    }, intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);

  return tick;
}
