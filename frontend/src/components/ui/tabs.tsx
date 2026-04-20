import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { cn } from "@/lib/utils";

const Tabs = TabsPrimitive.Root;

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("relative flex items-center gap-0.5 border-b border-hairline", className)}
    {...props}
  />
));
TabsList.displayName = TabsPrimitive.List.displayName;

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, children, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn(
      "relative inline-flex items-center gap-1.5 whitespace-nowrap",
      "px-3.5 py-2.5 font-mono text-[12px] font-medium leading-none",
      "text-ink-3 transition-colors duration-[140ms]",
      "hover:text-ink-2",
      "focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
      "data-[state=active]:text-ink-1",
      "after:pointer-events-none after:absolute after:inset-x-0 after:bottom-[-1px] after:h-[2px]",
      "after:rounded-[2px] after:bg-ink-1 after:opacity-0",
      "after:transition-opacity after:duration-[260ms] after:ease-[cubic-bezier(0.22,1,0.36,1)]",
      "data-[state=active]:after:opacity-100",
      "disabled:pointer-events-none disabled:opacity-50",
      className,
    )}
    {...props}
  >
    {children}
  </TabsPrimitive.Trigger>
));
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName;

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn(
      "mt-4 focus-visible:outline-none focus-visible:[box-shadow:var(--focus-ring)]",
      className,
    )}
    {...props}
  />
));
TabsContent.displayName = TabsPrimitive.Content.displayName;

export { Tabs, TabsList, TabsTrigger, TabsContent };
