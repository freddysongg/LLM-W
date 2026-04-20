import * as React from "react";
import { cn } from "@/lib/utils";

type KbdProps = React.HTMLAttributes<HTMLElement>;

export const Kbd = React.forwardRef<HTMLElement, KbdProps>(
  ({ className, ...props }, ref): React.JSX.Element => (
    <kbd
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center min-w-[22px] h-[22px] px-1",
        "rounded-sm bg-surface-2 border border-hairline",
        "text-[10px] font-mono text-ink-3 leading-none",
        className,
      )}
      {...props}
    />
  ),
);
Kbd.displayName = "Kbd";
