import * as React from "react";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

interface SliderRowProps {
  readonly label: string;
  readonly value: number;
  readonly min: number;
  readonly max: number;
  readonly step: number;
  readonly formatValue?: (value: number) => string;
  readonly onChange: (value: number) => void;
  readonly disabled?: boolean;
  readonly helpText?: string;
  readonly className?: string;
}

export function SliderRow({
  label,
  value,
  min,
  max,
  step,
  formatValue,
  onChange,
  disabled = false,
  helpText,
  className,
}: SliderRowProps): React.JSX.Element {
  const handleChange = (values: number[]): void => {
    const [next] = values;
    if (typeof next === "number") onChange(next);
  };

  const displayValue = formatValue ? formatValue(value) : String(value);

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-baseline justify-between gap-4">
        <span className="caps text-ink-3">{label}</span>
        <span className="mono text-[13px] tabular-nums text-ink-1">{displayValue}</span>
      </div>
      <Slider
        aria-label={label}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={handleChange}
        disabled={disabled}
      />
      {helpText ? <p className="text-[11px] text-ink-4">{helpText}</p> : null}
    </div>
  );
}
