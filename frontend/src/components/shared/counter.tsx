import * as React from "react";
import { cn } from "@/lib/utils";

export interface CounterProps {
  readonly value: number;
  readonly decimals?: number;
  readonly suffix?: string;
  readonly className?: string;
  readonly animate?: boolean;
}

const ANIMATION_DURATION_MS = 400;

function easeOutCubic(progress: number): number {
  return 1 - Math.pow(1 - progress, 3);
}

export function Counter({
  value,
  decimals = 0,
  suffix = "",
  className,
  animate = true,
}: CounterProps): React.JSX.Element {
  const [displayValue, setDisplayValue] = React.useState<number>(value);
  const previousValueRef = React.useRef<number>(value);

  React.useEffect(() => {
    if (!animate) {
      previousValueRef.current = value;
      setDisplayValue(value);
      return;
    }

    const fromValue = previousValueRef.current;
    const toValue = value;
    if (fromValue === toValue) return;

    const startTimestamp = performance.now();
    let rafId = 0;

    const step = (now: number): void => {
      const progress = Math.min(1, (now - startTimestamp) / ANIMATION_DURATION_MS);
      const eased = easeOutCubic(progress);
      setDisplayValue(fromValue + (toValue - fromValue) * eased);
      if (progress < 1) {
        rafId = requestAnimationFrame(step);
      } else {
        previousValueRef.current = toValue;
      }
    };

    rafId = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafId);
  }, [value, animate]);

  return (
    <span key={value} className={cn("animate-count-tick tabular-nums", className)}>
      {displayValue.toFixed(decimals)}
      {suffix}
    </span>
  );
}
