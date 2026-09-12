import { Loader2 } from "lucide-react";

import { cn } from "@/lib/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

const VARIANTS: Record<Variant, string> = {
  // A one-stop gradient reads as a raised surface without the heaviness of a drop shadow.
  primary:
    "bg-gradient-to-b from-brand-600 to-brand-700 text-white shadow-e1 ring-1 ring-inset ring-brand-800/40 " +
    "hover:from-brand-500 hover:to-brand-600 active:from-brand-700 active:to-brand-800",
  secondary:
    "bg-white text-slate-700 ring-1 ring-inset ring-line-strong shadow-e1 hover:bg-slate-50 hover:text-slate-900 " +
    "active:bg-slate-100",
  ghost: "text-slate-600 hover:bg-slate-100 hover:text-slate-900 active:bg-slate-200/70",
  danger:
    "bg-gradient-to-b from-rose-500 to-rose-600 text-white shadow-e1 ring-1 ring-inset ring-rose-700/40 " +
    "hover:from-rose-400 hover:to-rose-500 active:from-rose-600 active:to-rose-700",
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
        "transition-[background,color,box-shadow,transform] duration-150 ease-out active:translate-y-px",
        "disabled:pointer-events-none disabled:opacity-55 disabled:shadow-none",
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

/** Square button for a single icon — keeps toolbars on the same 32/36px rhythm as Button. */
export function IconButton({
  label, size = "md", className, children, ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string; size?: "sm" | "md" }) {
  return (
    <button
      {...props}
      aria-label={label}
      title={label}
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-lg text-slate-500 transition-colors duration-150",
        "hover:bg-slate-100 hover:text-slate-800 disabled:pointer-events-none disabled:opacity-50",
        size === "sm" ? "h-8 w-8" : "h-9 w-9",
        className,
      )}
    >
      {children}
    </button>
  );
}
