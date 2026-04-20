import * as React from "react";
import * as ToastPrimitives from "@radix-ui/react-toast";
import { cva, type VariantProps } from "class-variance-authority";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastVariant = "default" | "destructive" | "info" | "success" | "warn" | "danger";

const ToastProvider = ToastPrimitives.Provider;

const ToastViewport = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Viewport>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Viewport
    ref={ref}
    className={cn(
      "fixed top-0 z-[300] flex max-h-screen w-full flex-col-reverse gap-2 p-4",
      "sm:bottom-5 sm:right-5 sm:top-auto sm:flex-col md:max-w-[420px]",
      className,
    )}
    {...props}
  />
));
ToastViewport.displayName = ToastPrimitives.Viewport.displayName;

const toastVariants = cva(
  [
    "pointer-events-auto relative flex w-full items-center gap-3",
    "min-w-[240px] max-w-[360px] rounded-md border px-4 py-3",
    "bg-surface text-ink-1 border-hairline shadow-token-md",
    "font-sans text-[12.5px]",
    "transition-all",
    "data-[swipe=cancel]:translate-x-0",
    "data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)]",
    "data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)]",
    "data-[swipe=move]:transition-none",
    "data-[state=open]:animate-fade-up",
    "data-[state=closed]:animate-out data-[state=closed]:fade-out-80",
    "data-[state=closed]:slide-out-to-right-full",
    "data-[swipe=end]:animate-out",
  ].join(" "),
  {
    variants: {
      variant: {
        default: "",
        info: "",
        success: "",
        warn: "",
        danger: "",
        destructive: "",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

const DOT_COLOR_BY_VARIANT: Record<ToastVariant, string> = {
  default: "bg-ink-3",
  info: "bg-[color:var(--info)]",
  success: "bg-[color:var(--success)]",
  warn: "bg-[color:var(--warn)]",
  danger: "bg-[color:var(--danger)]",
  destructive: "bg-[color:var(--danger)]",
};

const Toast = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Root>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Root> & VariantProps<typeof toastVariants>
>(({ className, variant, children, ...props }, ref) => {
  const dotClass = DOT_COLOR_BY_VARIANT[(variant ?? "default") as ToastVariant];
  return (
    <ToastPrimitives.Root
      ref={ref}
      className={cn(toastVariants({ variant }), className)}
      {...props}
    >
      <span aria-hidden="true" className={cn("h-1.5 w-1.5 shrink-0 rounded-full", dotClass)} />
      <div className="flex min-w-0 flex-1 items-center gap-3">{children}</div>
    </ToastPrimitives.Root>
  );
});
Toast.displayName = ToastPrimitives.Root.displayName;

const ToastAction = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Action>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Action>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Action
    ref={ref}
    className={cn(
      "inline-flex h-7 shrink-0 items-center justify-center rounded-sm border border-hairline",
      "bg-transparent px-2.5 font-mono text-[11px] font-medium text-ink-1",
      "transition-colors hover:bg-surface-2",
      "focus:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
      "disabled:pointer-events-none disabled:opacity-50",
      className,
    )}
    {...props}
  />
));
ToastAction.displayName = ToastPrimitives.Action.displayName;

const ToastClose = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Close>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Close>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Close
    ref={ref}
    className={cn(
      "absolute right-2 top-2 inline-grid h-6 w-6 place-items-center rounded-sm",
      "text-ink-3 opacity-0 transition-opacity hover:text-ink-1",
      "focus:opacity-100 focus:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
      "group-hover:opacity-100",
      className,
    )}
    toast-close=""
    {...props}
  >
    <X className="h-3.5 w-3.5" />
  </ToastPrimitives.Close>
));
ToastClose.displayName = ToastPrimitives.Close.displayName;

const ToastTitle = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Title>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Title>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Title
    ref={ref}
    className={cn("text-[13px] font-semibold leading-tight text-ink-1", className)}
    {...props}
  />
));
ToastTitle.displayName = ToastPrimitives.Title.displayName;

const ToastDescription = React.forwardRef<
  React.ElementRef<typeof ToastPrimitives.Description>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitives.Description>
>(({ className, ...props }, ref) => (
  <ToastPrimitives.Description
    ref={ref}
    className={cn("text-[12px] leading-snug text-ink-2", className)}
    {...props}
  />
));
ToastDescription.displayName = ToastPrimitives.Description.displayName;

type ToastProps = React.ComponentPropsWithoutRef<typeof Toast>;
type ToastActionElement = React.ReactElement<typeof ToastAction>;

export {
  type ToastProps,
  type ToastActionElement,
  ToastProvider,
  ToastViewport,
  Toast,
  ToastTitle,
  ToastDescription,
  ToastClose,
  ToastAction,
};
