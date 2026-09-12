import { cn } from "@/lib/format";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

const TONES: Record<Tone, string> = {
  neutral: "bg-slate-50 text-slate-600 ring-slate-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-700 ring-amber-200",
  danger: "bg-rose-50 text-rose-600 ring-rose-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-slate-400", brand: "bg-brand-500", success: "bg-emerald-500", warning: "bg-amber-500",
  danger: "bg-rose-500", info: "bg-sky-500", violet: "bg-violet-500",
};

export function Badge({ tone = "neutral", children, className, title, dot }: {
  tone?: Tone; children: React.ReactNode; className?: string; title?: string; dot?: boolean;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-medium leading-5",
        "ring-1 ring-inset",
        TONES[tone],
        className,
      )}
    >
      {dot && <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOTS[tone])} aria-hidden />}
      {children}
    </span>
  );
}

const STATUS_TONES: Record<string, Tone> = {
  active: "success", admitted: "warning", discharged: "info", inactive: "neutral", deceased: "neutral",
  scheduled: "info", checked_in: "brand", completed: "success", cancelled: "neutral", no_show: "danger",
  indexed: "success", processing: "warning", uploading: "info", failed: "danger", discontinued: "neutral",
  normal: "neutral", low: "info", high: "warning", critical: "danger", success: "success", denied: "danger",
  error: "danger", ok: "success", not_found: "warning", degraded: "warning",
};

export function StatusBadge({ status }: { status: string }) {
  const tone = STATUS_TONES[status] ?? "neutral";
  return <Badge tone={tone} dot={tone !== "neutral"}>{status.replace(/_/g, " ")}</Badge>;
}

const ROUTE_TONES: Record<string, Tone> = { SQL: "info", RAG: "violet", ML: "warning", SIMILARITY: "brand", LLM: "neutral" };

export function RouteBadge({ route }: { route: string }) {
  return <Badge tone={ROUTE_TONES[route] ?? "neutral"} className="font-mono text-[10px] tracking-wide">{route}</Badge>;
}
