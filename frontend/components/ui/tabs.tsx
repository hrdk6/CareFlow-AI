"use client";

import { cn } from "@/lib/format";

/** Segmented control: the active tab is a raised pill, so the current view is obvious at a glance
 *  even on a dense page where several tab strips can be visible at once. */
export function Tabs<T extends string>({ tabs, active, onChange }: {
  tabs: { id: T; label: string; count?: number | null; hidden?: boolean }[]; active: T; onChange: (id: T) => void;
}) {
  return (
    <div
      role="tablist"
      className="scroll-thin flex gap-1 overflow-x-auto rounded-xl border border-line bg-slate-100/70 p-1"
    >
      {tabs.filter((t) => !t.hidden).map((t) => {
        const selected = active === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.id)}
            className={cn(
              "flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] font-medium",
              "transition-[background,color,box-shadow] duration-150",
              selected
                ? "bg-white text-slate-900 shadow-e1 ring-1 ring-inset ring-line"
                : "text-slate-500 hover:bg-white/60 hover:text-slate-800",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count !== null && (
              <span
                className={cn(
                  "tabular rounded-full px-1.5 text-[10px] leading-4",
                  selected ? "bg-brand-50 text-brand-700" : "bg-slate-200/80 text-slate-500",
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
