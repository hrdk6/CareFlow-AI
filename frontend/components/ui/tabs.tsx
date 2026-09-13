"use client";

import { cn } from "@/lib/format";

/** Monitor view keys: a flat strip of labelled keys; the selected one is lit from below by the
 *  navigable channel, the way a monitor marks its active screen. */
export function Tabs<T extends string>({ tabs, active, onChange }: {
  tabs: { id: T; label: string; count?: number | null; hidden?: boolean }[]; active: T; onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="scroll-thin flex overflow-x-auto rounded-lg border border-line bg-sunken">
      {tabs.filter((t) => !t.hidden).map((t) => {
        const selected = active === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.id)}
            className={cn(
              "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap border-r border-line px-3.5 py-2",
              "font-display text-[13px] font-semibold uppercase tracking-[0.06em] transition-colors duration-150 last:border-r-0",
              selected ? "bg-raised text-ink" : "text-muted hover:bg-panel hover:text-ink",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count !== null && (
              <span className={cn("tabular text-[11px]", selected ? "text-accent" : "text-faint")}>{t.count}</span>
            )}
            <span
              className={cn("absolute inset-x-0 bottom-0 h-0.5 bg-accent transition-opacity duration-150", selected ? "opacity-100" : "opacity-0")}
              aria-hidden
            />
          </button>
        );
      })}
    </div>
  );
}
