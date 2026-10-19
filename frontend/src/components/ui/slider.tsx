import * as SliderPrimitive from "@radix-ui/react-slider";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils.ts";

function Slider({ className, ...props }: ComponentProps<typeof SliderPrimitive.Root>) {
  return (
    <SliderPrimitive.Root
      className={cn(
        "relative flex h-5 w-full touch-none items-center select-none data-[disabled]:opacity-40",
        className,
      )}
      {...props}
    >
      <SliderPrimitive.Track className="relative h-px w-full grow bg-border">
        <SliderPrimitive.Range className="absolute h-full bg-primary" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb className="block size-3.5 border-2 border-primary bg-card focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none" />
    </SliderPrimitive.Root>
  );
}

export { Slider };
