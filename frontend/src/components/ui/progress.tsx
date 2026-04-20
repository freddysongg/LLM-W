import * as React from "react";
import * as ProgressPrimitive from "@radix-ui/react-progress";
import { cn } from "@/lib/utils";

const STRIPE_BACKGROUND =
  "repeating-linear-gradient(45deg, rgba(255,255,255,0.22) 0 6px, transparent 6px 14px)";

export interface ProgressProps extends React.ComponentPropsWithoutRef<
  typeof ProgressPrimitive.Root
> {
  striped?: boolean;
  paused?: boolean;
}

const Progress = React.forwardRef<React.ElementRef<typeof ProgressPrimitive.Root>, ProgressProps>(
  ({ className, value, striped = false, paused = false, ...props }, ref) => {
    const stripeStyle: React.CSSProperties | undefined =
      striped && !paused
        ? {
            backgroundImage: STRIPE_BACKGROUND,
            backgroundSize: "20px 20px",
          }
        : undefined;

    return (
      <ProgressPrimitive.Root
        ref={ref}
        className={cn("relative h-2 w-full overflow-hidden rounded-full bg-surface-3", className)}
        {...props}
      >
        <ProgressPrimitive.Indicator
          className={cn(
            "relative h-full rounded-full",
            "bg-[linear-gradient(90deg,var(--iris-2),var(--iris-3))]",
            "transition-transform duration-[460ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
          )}
          style={{ transform: `translateX(-${100 - (value ?? 0)}%)` }}
        >
          {striped ? (
            <span
              aria-hidden="true"
              className={cn(
                "pointer-events-none absolute inset-0",
                !paused && "animate-progress-stripe",
              )}
              style={stripeStyle}
            />
          ) : null}
        </ProgressPrimitive.Indicator>
      </ProgressPrimitive.Root>
    );
  },
);
Progress.displayName = ProgressPrimitive.Root.displayName;

export { Progress };
