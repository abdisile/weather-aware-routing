import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils.ts";

function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("border border-border bg-card text-card-foreground", className)} {...props} />;
}

export { Card };
