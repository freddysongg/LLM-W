import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  mono?: boolean;
  icon?: React.ReactNode;
  suffix?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, mono = false, icon, suffix, disabled, ...props }, ref) => {
    const fontClasses = mono ? "font-mono text-[11.5px]" : "font-sans text-[13px]";

    if (!icon && !suffix) {
      return (
        <input
          type={type}
          ref={ref}
          disabled={disabled}
          className={cn(
            "flex h-8 w-full rounded-md border border-hairline bg-surface px-3 text-ink-1",
            fontClasses,
            "placeholder:text-ink-4 transition-[border-color,box-shadow] duration-[140ms]",
            "focus-visible:outline-none focus-visible:border-[color:var(--iris-3)] focus-visible:[box-shadow:var(--focus-ring)]",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className,
          )}
          {...props}
        />
      );
    }

    return (
      <div
        className={cn(
          "inline-flex h-8 w-full items-center gap-2 rounded-md border border-hairline bg-surface px-3",
          "transition-[border-color,box-shadow] duration-[140ms]",
          "focus-within:border-[color:var(--iris-3)] focus-within:[box-shadow:var(--focus-ring)]",
          disabled && "cursor-not-allowed opacity-50",
          className,
        )}
      >
        {icon ? (
          <span className="inline-grid shrink-0 place-items-center text-ink-3">{icon}</span>
        ) : null}
        <input
          type={type}
          ref={ref}
          disabled={disabled}
          className={cn(
            "min-w-0 flex-1 border-0 bg-transparent text-ink-1 outline-none",
            fontClasses,
            "placeholder:text-ink-4 disabled:cursor-not-allowed",
          )}
          {...props}
        />
        {suffix ? (
          <span className="shrink-0 font-mono text-[10px] text-ink-3">{suffix}</span>
        ) : null}
      </div>
    );
  },
);
Input.displayName = "Input";

export { Input };
