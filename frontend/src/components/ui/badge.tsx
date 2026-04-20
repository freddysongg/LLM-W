import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  [
    "inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5",
    "font-mono text-[10px] font-medium uppercase leading-none tracking-[0.08em]",
    "transition-colors",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "border-hairline bg-surface-2 text-ink-2",
        secondary: "border-hairline bg-surface-2 text-ink-2",
        outline: "border-hairline bg-transparent text-ink-2",
        running: [
          "text-[color:var(--info)]",
          "border-[color-mix(in_oklch,var(--info)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--info)_8%,var(--surface))]",
        ].join(" "),
        success: [
          "text-[color:var(--success)]",
          "border-[color-mix(in_oklch,var(--success)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--success)_8%,var(--surface))]",
        ].join(" "),
        warn: [
          "text-[color:var(--warn)]",
          "border-[color-mix(in_oklch,var(--warn)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--warn)_8%,var(--surface))]",
        ].join(" "),
        danger: [
          "text-[color:var(--danger)]",
          "border-[color-mix(in_oklch,var(--danger)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--danger)_8%,var(--surface))]",
        ].join(" "),
        destructive: [
          "text-[color:var(--danger)]",
          "border-[color-mix(in_oklch,var(--danger)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--danger)_8%,var(--surface))]",
        ].join(" "),
        iris: [
          "text-[color:var(--blue-ink)]",
          "border-[color-mix(in_oklch,var(--iris-3)_30%,transparent)]",
          "bg-[color-mix(in_oklch,var(--iris-3)_8%,var(--surface))]",
        ].join(" "),
        neutral: "border-hairline bg-surface-2 text-ink-2",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {
  dot?: boolean;
}

function Badge({ className, variant, dot, children, ...props }: BadgeProps): React.JSX.Element {
  const isRunning = variant === "running";
  const shouldShowDot = dot ?? isRunning;
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props}>
      {shouldShowDot ? (
        <span
          aria-hidden="true"
          className={cn(
            "h-1.5 w-1.5 rounded-full bg-[currentColor]",
            isRunning && "animate-pulse-dot",
          )}
        />
      ) : null}
      {children}
    </div>
  );
}

export { Badge, badgeVariants };
