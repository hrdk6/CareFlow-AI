import { Loader2 } from "lucide-react";

import { cn } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

/* Monitor keys: flat, hard-edged, and lit only by meaning. The primary key is the one lit channel
   on the panel; everything else is a quiet control on the panel face. */
const VARIANTS: Record<Variant, string> = {
  primary: "bg-accent text-on-signal hover:bg-[#62e0ee] active:bg-[#2cc2d3]",
  secondary:
    "bg-raised text-ink ring-1 ring-inset ring-line-strong hover:bg-raised-2 hover:ring-[#3d3d41] active:bg-raised",
  ghost: "text-ink-2 hover:bg-raised hover:text-ink active:bg-raised-2",
  danger: "bg-high-tint text-high ring-1 ring-inset ring-high-edge hover:bg-[#3b2224] active:bg-high-tint",
};

export function Button({
  variant = "primary", size = "md", loading = false, className, children, disabled, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; loading?: boolean }) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(
        "inline-flex select-none items-center justify-center gap-1.5 rounded-md font-medium",
        "transition-[background,color,box-shadow] duration-150 ease-out",
        "disabled:pointer-events-none disabled:opacity-45",
        size === "sm" ? "h-8 px-2.5 text-xs" : "h-9 px-3.5 text-sm",
        VARIANTS[variant],
        className,
      )}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** Square key for a single icon, on the same 32/36px rhythm as Button. */
export function IconButton({
  label, size = "md", className, children, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: "sm" | "md" }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-md text-muted transition-colors duration-150",
        "hover:bg-raised hover:text-ink disabled:pointer-events-none disabled:opacity-45",
        size === "sm" ? "h-8 w-8" : "h-9 w-9",
        className,
      )}
    >
      {children}
    </button>
  );
}
