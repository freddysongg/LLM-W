import * as React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root>
>(({ className, ...props }, ref) => (
  <SliderPrimitive.Root
    ref={ref}
    className={cn("relative flex w-full touch-none select-none items-center", className)}
    {...props}
  >
    <SliderPrimitive.Track className="relative h-[2px] w-full grow overflow-hidden rounded-full bg-hairline">
      <SliderPrimitive.Range className="absolute h-full bg-[color:var(--hairline-strong)]" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      className={cn(
        "block h-2 w-2 rounded-full bg-[color:var(--ink-1)]",
        "shadow-[0_0_0_3px_var(--surface),0_0_0_4px_var(--hairline-strong)]",
        "transition-[box-shadow] duration-[140ms] ease-[cubic-bezier(0.22,1,0.36,1)]",
        "hover:shadow-[0_0_0_3px_var(--surface),0_0_0_5px_var(--hairline-strong)]",
        "focus-visible:outline-none",
        "focus-visible:shadow-[0_0_0_3px_var(--surface),0_0_0_4px_var(--hairline-strong),var(--focus-ring)]",
        "disabled:pointer-events-none disabled:opacity-50",
      )}
    />
  </SliderPrimitive.Root>
));
Slider.displayName = SliderPrimitive.Root.displayName;

export { Slider };
