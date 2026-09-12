import { cn } from "@/lib/format";

export function Card({
  title, subtitle, actions, children, className, bodyClassName, id,
}: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
  className?: string; bodyClassName?: string; id?: string;
}) {
  return (
    <section
      id={id}
      className={cn(
        "min-w-0 rounded-xl border border-line bg-surface shadow-e1 transition-shadow duration-200 hover:shadow-e2",
        className,
      )}
    >
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-line/80 px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="truncate text-[13px] font-semibold text-slate-800">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs leading-relaxed text-muted">{subtitle}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      {/* Wide content (tables) scrolls inside the card instead of widening the page. */}
      <div className={cn("scroll-thin overflow-x-auto p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, subtitle, actions, eyebrow }: {
  title: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; eyebrow?: React.ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        {eyebrow && (
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-brand-600">{eyebrow}</div>
        )}
        <h1 className="text-[22px] font-semibold leading-tight text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

const STAT_TONES = {
  slate: "bg-slate-100 text-slate-600 ring-slate-200",
  brand: "bg-brand-50 text-brand-700 ring-brand-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  rose: "bg-rose-50 text-rose-600 ring-rose-200",
  sky: "bg-sky-50 text-sky-700 ring-sky-200",
};

export function StatCard({ label, value, hint, icon, tone = "slate" }: {
  label: string; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode;
  tone?: keyof typeof STAT_TONES;
}) {
  return (
    <div className="group flex items-center gap-3.5 rounded-xl border border-line bg-surface px-4 py-3.5 shadow-e1 transition-shadow duration-200 hover:shadow-e2">
      {icon && (
        <div className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ring-1 ring-inset transition-transform duration-200 group-hover:scale-105", STAT_TONES[tone])}>
          {icon}
        </div>
      )}
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-[0.06em] text-muted">{label}</div>
        <div className="tabular text-[22px] font-semibold leading-tight text-slate-900">{value}</div>
        {hint && <div className="truncate text-xs text-muted">{hint}</div>}
      </div>
    </div>
  );
}

export function KeyValue({ items, columns = 2 }: { items: [string, React.ReactNode][]; columns?: 1 | 2 | 3 }) {
  const grid = { 1: "grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" }[columns];
  return (
    <dl className={cn("grid gap-x-6 gap-y-3.5", grid)}>
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-[11px] font-medium uppercase tracking-[0.06em] text-muted">{k}</dt>
          <dd className="mt-0.5 truncate text-sm text-slate-800">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
