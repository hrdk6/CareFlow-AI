import { cn } from "@/lib/format";

export function initials(name: string): string {
  return name.replace(/^Dr\.\s*/, "").split(/[\s,]+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? "").join("");
}

const SIZES = {
  sm: "h-7 w-7 text-[11px]",
  md: "h-9 w-9 text-[12px]",
  lg: "h-14 w-14 text-[18px]",
};

/** Round initials. Rose only when the person has a result that needs review. */
export function Avatar({ name, tone = "neutral", size = "md", className }: {
  name: string; tone?: "neutral" | "alert"; size?: keyof typeof SIZES; className?: string;
}) {
  return (
    <span
      className={cn(
        "flex shrink-0 select-none items-center justify-center rounded-full font-semibold",
        SIZES[size],
        tone === "alert" ? "bg-high-tint text-high ring-1 ring-inset ring-high-edge" : "bg-accent-tint text-accent",
        className,
      )}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}
