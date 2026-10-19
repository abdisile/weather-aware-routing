import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils.ts";

const badgeVariants = cva("inline-flex items-center border px-2 py-1 text-[10px] font-semibold tracking-[0.12em]", {
  variants: {
    variant: {
      default: "border-transparent bg-primary text-primary-foreground uppercase",
      outline: "border-border bg-card text-[11px] font-medium tracking-normal text-muted-foreground",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>;

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
