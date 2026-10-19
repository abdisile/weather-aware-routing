import * as ToggleGroupPrimitive from "@radix-ui/react-toggle-group";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils.ts";

function ToggleGroup({ className, ...props }: ComponentProps<typeof ToggleGroupPrimitive.Root>) {
  return (
    <ToggleGroupPrimitive.Root className={cn("flex w-full border border-input bg-card", className)} {...props} />
  );
}

function ToggleGroupItem({ className, ...props }: ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      className={cn(
        "h-11 flex-1 border-r border-input text-sm text-muted-foreground transition-colors last:border-r-0 hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring data-[state=on]:bg-primary data-[state=on]:text-primary-foreground data-[state=on]:hover:bg-primary",
        className,
      )}
      {...props}
    />
  );
}

export { ToggleGroup, ToggleGroupItem };
