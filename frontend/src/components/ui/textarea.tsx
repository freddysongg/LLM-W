import * as React from "react";
import { cn } from "@/lib/utils";

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  readonly mono?: boolean;
}

const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, mono = false, ...props }, ref) => {
    const fontClasses = mono ? "font-mono text-[12px]" : "font-sans text-[13px]";
    return (
      <textarea
        ref={ref}
        className={cn(
          "flex min-h-[80px] w-full rounded-md border border-hairline bg-surface px-3 py-2 text-ink-1",
          fontClasses,
          "placeholder:text-ink-4 transition-[border-color,box-shadow] duration-[140ms]",
          "focus-visible:outline-none focus-visible:border-[color:var(--iris-3)] focus-visible:[box-shadow:var(--focus-ring)]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "resize-y",
          className,
        )}
        {...props}
      />
    );
  },
);
Textarea.displayName = "Textarea";

export { Textarea };
