import { Loader2 } from "lucide-react";

import { cn } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-accent text-on-signal shadow-[0_1px_2px_rgba(9,104,92,0.25),inset_0_1px_0_rgba(255,255,255,0.12)] " +
    "hover:bg-accent-strong active:translate-y-px",
  secondary:
    "bg-panel text-ink shadow-e1 ring-1 ring-inset ring-line-strong hover:bg-sunken hover:ring-[#b9c5cb] active:bg-raised",
  ghost: "text-ink-2 hover:bg-raised hover:text-ink active:bg-raised-2",
  danger: "bg-panel text-high shadow-e1 ring-1 ring-inset ring-high-edge hover:bg-high-tint active:bg-high-tint",
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
        "inline-flex select-none items-center justify-center gap-1.5 rounded-lg font-medium",
        "transition-[background,color,box-shadow,transform] duration-150 ease-out",
        "disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        VARIANTS[variant],
        className,
      )}
    >
      {loading && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

/** Square button for a single icon, on the same 32/36px rhythm as Button. */
export function IconButton({
  label, size = "md", className, children, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: "sm" | "md" }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg text-muted transition-colors duration-150",
        "hover:bg-raised hover:text-ink disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-8 w-8" : "h-9 w-9",
        className,
      )}
    >
      {children}
    </button>
  );
}
