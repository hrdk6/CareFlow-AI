"use client";

/** Small dependency-free SVG charts (ROC/PR curves, trends, bars, confusion matrix). */
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/format";

/** The rendered width in CSS pixels, so the SVG coordinate system is 1:1 with the screen and text
 *  sizes are real sizes instead of shrinking with a scaled viewBox. */
function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, Math.round(entry.contentRect.width))));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export interface Series { name: string; points: [number, number][]; color: string; dashed?: boolean }

export function LineChart({ series, height = 220, xLabel, yLabel, xDomain, yDomain, diagonal, refLines = [], xFormat, yFormat }: {
  series: Series[]; height?: number; xLabel?: string; yLabel?: string; xDomain?: [number, number];
  yDomain?: [number, number]; diagonal?: boolean; refLines?: { y: number; label: string; color: string }[];
  xFormat?: (v: number) => string; yFormat?: (v: number) => string;
}) {
  const [box, W] = useWidth<HTMLDivElement>(520);
  const H = height, pad = { l: 46, r: 14, t: 10, b: 38 };
  const all = series.flatMap((s) => s.points);
  if (!all.length) return <div ref={box} className="text-xs text-muted">No data</div>;
  const [x0, x1] = xDomain ?? [Math.min(...all.map((p) => p[0])), Math.max(...all.map((p) => p[0]))];
  const [y0, y1] = yDomain ?? [Math.min(...all.map((p) => p[1]), ...refLines.map((r) => r.y)), Math.max(...all.map((p) => p[1]), ...refLines.map((r) => r.y))];
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b);
  const ticks = (a: number, b: number) => Array.from({ length: 5 }, (_, i) => a + ((b - a) * i) / 4);
  const fx = xFormat ?? ((v: number) => v.toFixed(1));
  const fy = yFormat ?? ((v: number) => v.toFixed(1));
  return (
    <div ref={box}>
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="block w-full" role="img" aria-label={yLabel ?? "chart"}>
        {ticks(y0, y1).map((t) => (
          <g key={`y${t}`}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} stroke="var(--color-line)" />
            <text x={pad.l - 6} y={sy(t) + 3} fontSize="11" textAnchor="end" fill="var(--color-muted)">{fy(t)}</text>
          </g>
        ))}
        {ticks(x0, x1).map((t) => (
          <text key={`x${t}`} x={sx(t)} y={H - pad.b + 14} fontSize="11" textAnchor="middle" fill="var(--color-muted)">{fx(t)}</text>
        ))}
        {diagonal && <line x1={sx(x0)} y1={sy(y0)} x2={sx(x1)} y2={sy(y1)} stroke="var(--color-line-strong)" strokeDasharray="4 4" />}
        {refLines.map((r) => (
          <g key={r.label}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(r.y)} y2={sy(r.y)} stroke={r.color} strokeDasharray="3 3" />
            <text x={pad.l + 6} y={sy(r.y) - 4} fontSize="11" textAnchor="start" fill={r.color}>{r.label}</text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.name}>
            <polyline fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? "5 4" : undefined}
              points={s.points.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ")} />
            {s.points.length < 20 && s.points.map(([x, y], i) => <circle key={i} cx={sx(x)} cy={sy(y)} r="2.8" fill={s.color} />)}
          </g>
        ))}
        {xLabel && <text x={(W + pad.l) / 2} y={H - 4} fontSize="12" textAnchor="middle" fill="var(--color-ink-2)">{xLabel}</text>}
        {yLabel && <text x={10} y={H / 2} fontSize="12" textAnchor="middle" fill="var(--color-ink-2)" transform={`rotate(-90 10 ${H / 2})`}>{yLabel}</text>}
      </svg>
      {series.length > 1 && (
        <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-ink-2">
          {series.map((s) => <span key={s.name} className="flex items-center gap-1"><span className="h-0.5 w-4" style={{ background: s.color }} />{s.name}</span>)}
        </div>
      )}
    </div>
  );
}

export function BarList({ items, format = (v) => v.toFixed(3), color = "bg-accent" }: {
  items: { label: string; value: number }[]; format?: (v: number) => string; color?: string;
}) {
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1e-9);
  return (
    <ul className="space-y-1.5">
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[minmax(0,180px)_1fr_56px] items-center gap-2 text-xs">
          <span className="truncate text-ink-2" title={i.label}>{i.label}</span>
          <span className="h-2.5 rounded-sm bg-raised"><span className={cn("block h-full rounded-sm", color)} style={{ width: `${(Math.abs(i.value) / max) * 100}%` }} /></span>
          <span className="text-right font-mono tabular-nums text-muted">{format(i.value)}</span>
        </li>
      ))}
    </ul>
  );
}

/** Signed contributions (e.g. SHAP): bars grow right for "increases", left for "decreases". */
export function DivergingBars({ items, format = (v) => (v >= 0 ? "+" : "") + v.toFixed(3) }: {
  items: { label: string; value: number; detail?: string }[]; format?: (v: number) => string;
}) {
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1e-9);
  return (
    <ul className="space-y-2">
      {items.map((i) => (
        <li key={i.label} className="text-xs">
          <div className="mb-0.5 flex justify-between gap-2">
            <span className="truncate text-ink-2">{i.label}{i.detail && <span className="text-faint"> = {i.detail}</span>}</span>
            <span className={cn("font-mono tabular-nums", i.value >= 0 ? "text-high" : "text-ok")}>{format(i.value)}</span>
          </div>
          <div className="grid grid-cols-2 gap-px">
            <div className="flex h-2 justify-end rounded-l-sm bg-raised">
              {i.value < 0 && <div className="h-full rounded-l-sm bg-ok" style={{ width: `${(Math.abs(i.value) / max) * 100}%` }} />}
            </div>
            <div className="h-2 rounded-r-sm bg-raised">
              {i.value > 0 && <div className="h-full rounded-r-sm bg-high" style={{ width: `${(i.value / max) * 100}%` }} />}
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

export function ConfusionMatrix({ tn, fp, fn, tp }: { tn: number; fp: number; fn: number; tp: number }) {
  const total = tn + fp + fn + tp;
  const cell = (v: number, good: boolean) => (
    // Correct predictions read as advisory cyan; errors stay neutral. Red means a clinical alarm and nothing else.
    <div className={cn("rounded-sm p-3 text-center", good ? "bg-info-tint text-info" : "bg-raised text-ink-2")}>
      <div className="text-lg font-semibold tabular-nums">{v.toLocaleString()}</div>
      <div className="text-[10px] opacity-70">{((v / total) * 100).toFixed(1)}%</div>
    </div>
  );
  return (
    <div className="grid grid-cols-[auto_1fr_1fr] items-center gap-1.5 text-xs">
      <span />
      <span className="text-center text-muted">Predicted no</span>
      <span className="text-center text-muted">Predicted yes</span>
      <span className="pr-2 text-right text-muted">Actual no</span>{cell(tn, true)}{cell(fp, false)}
      <span className="pr-2 text-right text-muted">Actual yes</span>{cell(fn, false)}{cell(tp, true)}
    </div>
  );
}

export function Gauge({ value, markers }: { value: number; markers: { at: number; label: string }[] }) {
  const clamp = Math.min(1, Math.max(0, value));
  const scale = (v: number) => Math.min(100, (v / 0.6) * 100); // readmission probabilities rarely exceed 60%
  return (
    // Markers alternate above and below the scale so neighbouring labels never collide.
    <div className="relative mb-1 mt-5 h-10">
      <div className="absolute inset-x-0 top-4 h-2 rounded-sm bg-gradient-to-r from-ok via-warn to-high" />
      {markers.map((m, i) => (
        <div key={m.label} className="absolute top-2.5 h-5 w-px bg-ink-2" style={{ left: `${scale(m.at)}%` }}>
          <span className={cn("absolute left-1/2 -translate-x-1/2 whitespace-nowrap text-[11px] text-muted", i % 2 ? "top-5" : "-top-4")}>
            {m.label}
          </span>
        </div>
      ))}
      <div className="absolute top-3 h-4 w-1.5 -translate-x-1/2 rounded-sm bg-ink" style={{ left: `${scale(clamp)}%` }} aria-hidden />
    </div>
  );
}
