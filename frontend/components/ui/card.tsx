import { cn } from "@/lib/format";

export function Card({
  title, subtitle, actions, children, className, bodyClassName, id,
}: {
  title?: React.ReactNode; subtitle?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode;
  className?: string; bodyClassName?: string; id?: string;
}) {
  return (
    <section id={id} className={cn("min-w-0 rounded-lg border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04)]", className)}>
      {(title || actions) && (
        <header className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
          <div className="min-w-0">
            {title && <h2 className="text-[13px] font-semibold uppercase tracking-wide text-slate-600">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
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
      <div>
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-wider text-brand-700">{eyebrow}</div>}
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}

export function StatCard({ label, value, hint, icon, tone = "slate" }: {
  label: string; value: React.ReactNode; hint?: React.ReactNode; icon?: React.ReactNode;
  tone?: "slate" | "brand" | "amber" | "rose" | "sky";
}) {
  const tones = {
    slate: "bg-slate-100 text-slate-600", brand: "bg-brand-50 text-brand-700", amber: "bg-amber-50 text-amber-700",
    rose: "bg-rose-50 text-rose-700", sky: "bg-sky-50 text-sky-700",
  };
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3.5">
      {icon && <div className={cn("flex h-10 w-10 items-center justify-center rounded-md", tones[tone])}>{icon}</div>}
      <div className="min-w-0">
        <div className="text-xs font-medium text-slate-500">{label}</div>
        <div className="text-xl font-semibold tabular-nums text-slate-900">{value}</div>
        {hint && <div className="truncate text-xs text-slate-500">{hint}</div>}
      </div>
    </div>
  );
}

export function KeyValue({ items, columns = 2 }: { items: [string, React.ReactNode][]; columns?: 1 | 2 | 3 }) {
  const grid = { 1: "grid-cols-1", 2: "sm:grid-cols-2", 3: "sm:grid-cols-3" }[columns];
  return (
    <dl className={cn("grid gap-x-6 gap-y-3", grid)}>
      {items.map(([k, v]) => (
        <div key={k} className="min-w-0">
          <dt className="text-xs text-slate-500">{k}</dt>
          <dd className="truncate text-sm text-slate-800">{v ?? "—"}</dd>
        </div>
      ))}
    </dl>
  );
}
