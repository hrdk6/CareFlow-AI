"use client";

import { cn } from "@/lib/format";

/** Underlined tabs on the card edge; the selected tab takes the accent. */
export function Tabs<T extends string>({ tabs, active, onChange }: {
  tabs: { id: T; label: string; count?: number | null; hidden?: boolean }[]; active: T; onChange: (id: T) => void;
}) {
  return (
    <div role="tablist" className="scroll-thin flex gap-1 overflow-x-auto border-b border-line">
      {tabs.filter((t) => !t.hidden).map((t) => {
        const selected = active === t.id;
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.id)}
            className={cn(
              "relative -mb-px flex shrink-0 items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-medium",
              "transition-colors duration-150",
              selected ? "border-accent text-ink" : "border-transparent text-muted hover:border-line-strong hover:text-ink",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count !== null && (
              <span
                className={cn(
                  "tabular rounded-full px-1.5 text-[11px] leading-[18px]",
                  selected ? "bg-accent-tint text-accent" : "bg-raised text-muted",
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
