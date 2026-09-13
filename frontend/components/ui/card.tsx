import { cn } from "@/lib/format";

/** A white card on a hairline border with a soft resting shadow. */
export function Card({
  title, subtitle, actions, children, className, bodyClassName, id,
}: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
  className?: string; bodyClassName?: string; id?: string;
}) {
  return (
    <section id={id} className={cn("min-w-0 rounded-xl border border-line bg-panel shadow-e1", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3.5">
          <div className="min-w-0">
            {title && <h2 className="truncate text-[15px] font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {/* Wide content (tables) scrolls inside the card instead of widening the page. */}
      <div className={cn("scroll-thin overflow-x-auto p-5", bodyClassName)}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-[26px] font-semibold leading-tight text-ink">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const TONE_TEXT = {
  slate: "text-ink", brand: "text-accent", sky: "text-info", ok: "text-ok",
  amber: "text-warn", rose: "text-high", violet: "text-ai",
};

/** A summary figure: label, figure, context. Colour is reserved for figures that carry a status. */
export function StatCard({ label, value, hint, icon, tone = "slate" }: {
  label: string; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode;
  tone?: keyof typeof TONE_TEXT;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-line bg-panel px-5 py-4 shadow-e1">
      <div className="flex items-center gap-2 text-[13px] font-medium text-muted">
        {icon && <span className="shrink-0 text-faint [&>svg]:h-4 [&>svg]:w-4">{icon}</span>}
        <span className="truncate">{label}</span>
      </div>
      <div className={cn("tabular mt-2 font-display text-[28px] font-semibold leading-none", TONE_TEXT[tone])}>{value}</div>
      {hint && <div className="mt-2 truncate text-xs text-muted">{hint}</div>}
    </div>
  );
}

export function KeyValue({ items, columns = 2 }: { items: [string, React.ReactNode][]; columns?: 1 | 2 | 3 }) {
  const grid = { 1: "grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" }[columns];
  return (
    <dl className={cn("grid gap-x-6 gap-y-4", grid)}>
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-xs font-medium text-muted">{k}</dt>
          <dd className="mt-0.5 truncate text-sm text-ink">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
