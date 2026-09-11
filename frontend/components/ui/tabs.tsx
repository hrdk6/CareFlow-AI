"use client";

import { cn } from "@/lib/format";

export function Tabs<T extends string>({ tabs, active, onChange }: {
  tabs: { id: T; label: string; count?: number | null; hidden?: boolean }[]; active: T; onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="scroll-thin flex gap-1 overflow-x-auto border-b border-slate-200">
      {tabs.filter((t) => !t.hidden).map((t) => (
        <button key={t.id} role="tab" aria-selected={active === t.id} onClick={() => onChange(t.id)}
          className={cn(
            "-mb-px flex items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-sm transition-colors",
            active === t.id ? "border-brand-600 font-medium text-brand-800" : "border-transparent text-slate-500 hover:text-slate-800",
          )}>
          {t.label}
          {t.count !== undefined && t.count !== null && (
            <span className={cn("rounded-full px-1.5 text-[10px] tabular-nums", active === t.id ? "bg-brand-100 text-brand-800" : "bg-slate-100 text-slate-500")}>
              {t.count}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
