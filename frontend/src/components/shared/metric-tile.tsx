import * as React from "react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Counter } from "@/components/shared/counter";
import { Sparkline } from "@/components/shared/sparkline";
import { cn } from "@/lib/utils";

type DeltaDirection = "up" | "down" | "flat";

export interface MetricDelta {
  readonly direction: DeltaDirection;
  readonly percent: number;
  readonly sentimentInverted?: boolean;
}

export interface MetricTileProps {
  readonly label: string;
  readonly value: number;
  readonly decimals?: number;
  readonly suffix?: string;
  readonly delta?: MetricDelta;
  readonly spark?: readonly number[];
  readonly sparkColor?: string;
  readonly className?: string;
}

interface DeltaSentiment {
  readonly colorClass: string;
  readonly Icon: typeof ArrowUp;
}

function resolveDeltaSentiment({ direction, sentimentInverted }: MetricDelta): DeltaSentiment {
  if (direction === "flat") {
    return { colorClass: "text-ink-3", Icon: Minus };
  }
  const isUp = direction === "up";
  const isGood = sentimentInverted ? !isUp : isUp;
  return {
    colorClass: isGood ? "text-[color:var(--success)]" : "text-[color:var(--danger)]",
    Icon: isUp ? ArrowUp : ArrowDown,
  };
}

export function MetricTile({
  label,
  value,
  decimals = 0,
  suffix,
  delta,
  spark,
  sparkColor = "var(--iris-3)",
  className,
}: MetricTileProps): React.JSX.Element {
  const sentiment = delta ? resolveDeltaSentiment(delta) : null;

  return (
    <Card
      className={cn(
        "flex flex-col gap-2.5 p-4",
        "transition-colors duration-[var(--dur-2)] hover:border-hairline-strong",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-ink-3">{label}</span>
        {delta && sentiment ? (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 font-mono text-[10px]",
              sentiment.colorClass,
            )}
          >
            <sentiment.Icon className="size-2.5" aria-hidden="true" />
            {Math.abs(delta.percent)}%
          </span>
        ) : null}
      </div>
      <div
        className={cn(
          "font-mono text-[22px] font-semibold leading-[1.1] tracking-[-0.02em] text-ink-1",
        )}
      >
        <Counter value={value} decimals={decimals} suffix={suffix} />
      </div>
      {spark ? <Sparkline data={spark} color={sparkColor} /> : null}
    </Card>
  );
}
