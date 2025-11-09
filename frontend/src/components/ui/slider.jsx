import * as React from "react"
import * as SliderPrimitive from "@radix-ui/react-slider"

import { cn } from "@/lib/utils"

const Slider = React.forwardRef(({ className, variant = "default", ...props }, ref) => {
  const trackStyles =
    variant === "contrast"
      ? "bg-slate-700/60"
      : "bg-primary/20"
  const rangeStyles =
    variant === "contrast"
      ? "bg-gradient-to-r from-blue-500 via-sky-400 to-cyan-300 shadow-[0_0_12px_rgba(56,189,248,0.45)]"
      : "bg-primary"
  const thumbStyles =
    variant === "contrast"
      ? "border-blue-400/70 bg-slate-950 shadow-[0_0_16px_rgba(56,189,248,0.55)] focus-visible:ring-1 focus-visible:ring-blue-300"
      : "border-primary/50 bg-background"

  return (
  <SliderPrimitive.Root
    ref={ref}
    className={cn("relative flex w-full touch-none select-none items-center", className)}
    {...props}>
    <SliderPrimitive.Track
      className={cn("relative h-1.5 w-full grow overflow-hidden rounded-full transition-colors", trackStyles)}>
      <SliderPrimitive.Range className={cn("absolute h-full transition-all", rangeStyles)} />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      className={cn(
        "block h-4 w-4 rounded-full transition-transform focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
        thumbStyles
      )} />
  </SliderPrimitive.Root>
  )
})
Slider.displayName = SliderPrimitive.Root.displayName

export { Slider }
