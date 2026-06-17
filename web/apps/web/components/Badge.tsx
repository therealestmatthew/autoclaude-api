import { cn } from "@/lib/cn";
import { statusColor } from "@/lib/format";

export function Badge({
  children,
  variant,
  className,
}: {
  children: React.ReactNode;
  variant?: "status" | "kind" | "tag" | "issue";
  className?: string;
}) {
  let base =
    "inline-flex items-center px-2 py-0.5 rounded text-xs font-medium";
  if (variant === "status" && typeof children === "string") {
    base = cn(base, statusColor(children));
  } else if (variant === "issue") {
    base = cn(
      base,
      "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
    );
  } else if (variant === "kind") {
    base = cn(
      base,
      "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-200",
    );
  } else {
    base = cn(
      base,
      "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
    );
  }
  return <span className={cn(base, className)}>{children}</span>;
}
