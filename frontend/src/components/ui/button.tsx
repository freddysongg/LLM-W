import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "relative inline-flex items-center justify-center gap-1.5 whitespace-nowrap select-none",
    "font-sans font-medium leading-none tracking-tight",
    "rounded-md border transition-[background-color,border-color,color,transform,box-shadow]",
    "duration-[140ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
    "hover:-translate-y-px active:translate-y-0",
    "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
    "disabled:pointer-events-none disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  ].join(" "),
  {
    variants: {
      variant: {
        default: [
          "bg-ink-1 text-[color:var(--surface)] border-ink-1",
          "hover:bg-ink-2 hover:border-ink-2",
        ].join(" "),
        primary: [
          "btn-primary-shimmer overflow-hidden",
          "bg-ink-1 text-[color:var(--surface)] border-ink-1",
          "hover:bg-ink-2 hover:border-ink-2 hover:shadow-token-sm",
        ].join(" "),
        secondary: "bg-surface-2 text-ink-1 border-hairline hover:bg-surface-3",
        outline:
          "bg-transparent text-ink-1 border-hairline hover:bg-surface-2 hover:border-hairline-strong",
        ghost: "bg-transparent text-ink-2 border-transparent hover:bg-surface-2 hover:text-ink-1",
        link: "bg-transparent text-ink-1 border-transparent underline-offset-4 hover:underline hover:-translate-y-0",
        destructive: [
          "bg-[color:var(--danger)] text-[color:var(--surface)] border-[color:var(--danger)]",
          "hover:bg-[color-mix(in_oklch,var(--danger)_88%,black)] hover:border-[color-mix(in_oklch,var(--danger)_88%,black)]",
        ].join(" "),
      },
      size: {
        default: "h-8 px-3 text-[12px]",
        sm: "h-7 px-2.5 text-[11px]",
        lg: "h-[38px] px-3.5 text-[13px]",
        icon: "h-8 w-8 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { Button, buttonVariants };
