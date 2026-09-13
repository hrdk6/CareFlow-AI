import { cn } from "@/lib/format";

/** A monitor panel: a flat plane behind a hairline, headed by a channel label. */
export function Card({
  title, subtitle, actions, children, className, bodyClassName, id,
}: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
  className?: string; bodyClassName?: string; id?: string;
}) {
  return (
    <section id={id} className={cn("min-w-0 rounded-lg border border-line bg-panel", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-4 py-2.5">
          <div className="min-w-0">
            {title && (
              <h2 className="truncate font-display text-[13px] font-semibold uppercase tracking-[0.08em] text-ink-2">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {/* Wide content (tables) scrolls inside the panel instead of widening the page. */}
      <div className={cn("scroll-thin overflow-x-auto p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="font-display text-[28px] font-semibold leading-none tracking-[-0.005em] text-ink">{title}</h1>
        {subtitle && <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

/* Tone names are kept for existing callers; each resolves to a clinical channel. */
const CHANNEL = {
  slate: { label: "text-muted", rule: "bg-line-strong" },
  brand: { label: "text-accent", rule: "bg-accent" },
  sky: { label: "text-info", rule: "bg-info" },
  ok: { label: "text-ok", rule: "bg-ok" },
  amber: { label: "text-warn", rule: "bg-warn" },
  rose: { label: "text-high", rule: "bg-high" },
  violet: { label: "text-ai", rule: "bg-ai" },
};

/** A monitor channel: coloured label, monitor-scale numeric, unit or context beneath.
 *  The label and the top rule carry the channel colour; the number stays near-white so it reads first. */
export function StatCard({ label, value, hint, tone = "slate" }: {
  label: string; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode;
  tone?: keyof typeof CHANNEL;
}) {
  const ch = CHANNEL[tone];
  return (
    <div className="relative min-w-0 overflow-hidden rounded-lg border border-line bg-panel px-4 pb-3 pt-3.5">
      <span className={cn("absolute inset-x-0 top-0 h-px", ch.rule)} aria-hidden />
      <div className={cn("truncate font-display text-[12px] font-semibold uppercase tracking-[0.1em]", ch.label)}>{label}</div>
      <div className="tabular mt-1 font-display text-[32px] font-semibold leading-none text-ink">{value}</div>
      {hint && <div className="mt-1.5 truncate text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function KeyValue({ items, columns = 2 }: { items: [string, React.ReactNode][]; columns?: 1 | 2 | 3 }) {
  const grid = { 1: "grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" }[columns];
  return (
    <dl className={cn("grid gap-x-6 gap-y-3.5", grid)}>
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="font-display text-[11px] font-semibold uppercase tracking-[0.1em] text-muted">{k}</dt>
          <dd className="mt-0.5 truncate text-sm text-ink">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
