"use client";

import { useLayoutEffect, useRef, useState } from "react";

import { cn } from "@/lib/format";

interface Indicator { x: number; width: number; track: number; visible: boolean; animate: boolean }

const EASE = "340ms var(--ease-out-expo)";

/** Measures the element whose data-id matches the active key, so one indicator can move to it. The first
 *  placement is instant so nothing sweeps in from the left edge. Callers move the indicator with transform
 *  or clip-path only: animating width would re-run layout on every frame. */
function useSlidingIndicator(container: React.RefObject<HTMLElement | null>, activeKey: string): Indicator {
  const [indicator, setIndicator] = useState<Indicator>({ x: 0, width: 0, track: 0, visible: false, animate: false });
  const placed = useRef(false);

  useLayoutEffect(() => {
    const el = container.current;
    if (!el) return;
    const measure = () => {
      const target = [...el.querySelectorAll<HTMLElement>("[data-id]")].find((n) => n.dataset.id === activeKey);
      if (!target) {
        setIndicator((i) => ({ ...i, visible: false }));
        return;
      }
      setIndicator({ x: target.offsetLeft, width: target.offsetWidth, track: el.scrollWidth, visible: true, animate: placed.current });
      placed.current = true;
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    // Web fonts and wrapping change label widths after the first paint.
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    el.querySelectorAll("[data-id]").forEach((n) => observer.observe(n));
    return () => observer.disconnect();
  }, [container, activeKey]);

  return indicator;
}

/** Arrow keys move between options, as they do in native tab and radio groups. */
function arrowNavigation<T extends string>(ids: T[], active: T, onChange: (id: T) => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const index = ids.indexOf(active);
    const next = ids[(index + (e.key === "ArrowRight" ? 1 : -1) + ids.length) % ids.length];
    onChange(next);
    [...e.currentTarget.querySelectorAll<HTMLElement>("[data-id]")].find((n) => n.dataset.id === next)?.focus();
  };
}

/** Underlined tabs; a single teal indicator slides to the selected tab. */
export function Tabs<T extends string>({ tabs, active, onChange, className }: {
  tabs: { id: T; label: string; count?: number | null; hidden?: boolean }[]; active: T; onChange: (id: T) => void;
  className?: string;
}) {
  const list = useRef<HTMLDivElement>(null);
  const visible = tabs.filter((t) => !t.hidden);
  const indicator = useSlidingIndicator(list, active);
  return (
    <div
      role="tablist"
      ref={list}
      onKeyDown={arrowNavigation(visible.map((t) => t.id), active, onChange)}
      className={cn("scroll-thin relative flex gap-1 overflow-x-auto shadow-[inset_0_-1px_0_var(--color-line)]", className)}
    >
      {visible.map((t) => {
        const selected = active === t.id;
        return (
          <button
            key={t.id}
            data-id={t.id}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={cn(
              "relative flex shrink-0 items-center gap-2 whitespace-nowrap rounded-t-md px-3 py-3 text-sm font-medium",
              "transition-colors duration-150 focus-visible:outline-offset-[-2px]",
              selected ? "text-ink" : "text-muted hover:text-ink",
            )}
          >
            {t.label}
            {t.count !== undefined && t.count !== null && (
              <span
                className={cn(
                  "tabular rounded-full px-1.5 text-[11px] leading-[18px] transition-colors",
                  selected ? "bg-accent-tint text-accent" : "bg-raised text-muted",
                )}
              >
                {t.count}
              </span>
            )}
          </button>
        );
      })}
      <span aria-hidden className="pointer-events-none absolute bottom-0 left-0 h-0.5 w-px origin-left bg-accent"
        style={{
          opacity: indicator.visible ? 1 : 0,
          transform: `translateX(${indicator.x}px) scaleX(${indicator.width})`,
          transition: indicator.animate ? `transform ${EASE}` : "none",
        }} />
    </div>
  );
}

/** A compact single-choice filter. The white selection pill slides between options. */
export function Segmented<T extends string>({ options, value, onChange, label, className }: {
  options: { value: T; label: string }[]; value: T; onChange: (value: T) => void; label: string; className?: string;
}) {
  const group = useRef<HTMLDivElement>(null);
  const indicator = useSlidingIndicator(group, value);
  return (
    <div
      ref={group}
      role="radiogroup"
      aria-label={label}
      onKeyDown={arrowNavigation(options.map((o) => o.value), value, onChange)}
      className={cn("scroll-thin relative flex max-w-full overflow-x-auto rounded-lg bg-raised p-0.5", className)}
    >
      <span aria-hidden className="pointer-events-none absolute bottom-0.5 left-0 top-0.5 [filter:drop-shadow(0_0_0.5px_rgba(16,34,42,0.28))_drop-shadow(0_1px_1.5px_rgba(16,34,42,0.1))]"
        style={{ width: indicator.track, opacity: indicator.visible ? 1 : 0 }}>
        <span className="block h-full bg-panel"
          style={{
            clipPath: `inset(0 ${Math.max(0, indicator.track - indicator.x - indicator.width)}px 0 ${indicator.x}px round 6px)`,
            transition: indicator.animate ? `clip-path ${EASE}` : "none",
          }} />
      </span>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            data-id={o.value}
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(o.value)}
            className={cn(
              "relative h-8 shrink-0 whitespace-nowrap rounded-md px-3 text-[13px] font-medium transition-colors duration-150",
              selected ? "text-ink" : "text-muted hover:text-ink",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
