import { cn } from "@/lib/format";

export type Tone = "neutral" | "brand" | "success" | "warning" | "danger" | "info" | "violet";

const TONES: Record<Tone, string> = {
  neutral: "bg-raised text-ink-2 ring-line",
  brand: "bg-accent-tint text-accent ring-accent-edge",
  success: "bg-ok-tint text-ok ring-ok-edge",
  warning: "bg-warn-tint text-warn ring-warn-edge",
  danger: "bg-high-tint text-high ring-high-edge",
  info: "bg-info-tint text-info ring-info-edge",
  violet: "bg-ai-tint text-ai ring-ai-edge",
};

const DOTS: Record<Tone, string> = {
  neutral: "bg-faint", brand: "bg-accent", success: "bg-ok", warning: "bg-warn",
  danger: "bg-high", info: "bg-info", violet: "bg-ai",
};

export function Badge({ tone = "neutral", children, className, title, dot }: {
  tone?: Tone; children: React.ReactNode; className?: string; title?: string; dot?: boolean;
}) {
  return (
    <span
      title={title}
      className={cn(
        "inline-flex items-center gap-1.5 whitespace-nowrap rounded-full px-2 py-px text-[11px] font-medium leading-5",
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
  const label = status.replace(/_/g, " ");
  return <Badge tone={tone} dot={tone !== "neutral"}>{label.charAt(0).toUpperCase() + label.slice(1)}</Badge>;
}

const ROUTE_TONES: Record<string, Tone> = { SQL: "info", RAG: "violet", ML: "warning", SIMILARITY: "brand", LLM: "neutral" };

export function RouteBadge({ route }: { route: string }) {
  return <Badge tone={ROUTE_TONES[route] ?? "neutral"} className="font-mono text-[10px]">{route}</Badge>;
}
