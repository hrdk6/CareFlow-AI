import { cn } from "@/lib/format";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700 ring-slate-200",
  brand: "bg-brand-50 text-brand-800 ring-brand-200",
  success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  warning: "bg-amber-50 text-amber-800 ring-amber-200",
  danger: "bg-rose-50 text-rose-700 ring-rose-200",
  info: "bg-sky-50 text-sky-700 ring-sky-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
};

export function Badge({ tone = "neutral", children, className, title }: {
  tone?: Tone; children: React.ReactNode; className?: string; title?: string;
}) {
  return (
    <span title={title} className={cn("inline-flex items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium ring-1 ring-inset", TONES[tone], className)}>
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
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{status.replace(/_/g, " ")}</Badge>;
}

const ROUTE_TONES: Record<string, Tone> = { SQL: "info", RAG: "violet", ML: "warning", SIMILARITY: "brand", LLM: "neutral" };

export function RouteBadge({ route }: { route: string }) {
  return <Badge tone={ROUTE_TONES[route] ?? "neutral"}>{route}</Badge>;
}
