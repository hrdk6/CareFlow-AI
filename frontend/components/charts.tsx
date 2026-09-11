/** Small dependency-free SVG charts (ROC/PR curves, trends, bars, confusion matrix). */
import { cn } from "@/lib/format";

export interface Series { name: string; points: [number, number][]; color: string; dashed?: boolean }

export function LineChart({ series, height = 220, xLabel, yLabel, xDomain, yDomain, diagonal, refLines = [], xFormat, yFormat }: {
  series: Series[]; height?: number; xLabel?: string; yLabel?: string; xDomain?: [number, number];
  yDomain?: [number, number]; diagonal?: boolean; refLines?: { y: number; label: string; color: string }[];
  xFormat?: (v: number) => string; yFormat?: (v: number) => string;
}) {
  const W = 520, H = height, pad = { l: 44, r: 12, t: 10, b: 34 };
  const all = series.flatMap((s) => s.points);
  if (!all.length) return <div className="text-xs text-slate-500">No data</div>;
  const [x0, x1] = xDomain ?? [Math.min(...all.map((p) => p[0])), Math.max(...all.map((p) => p[0]))];
  const [y0, y1] = yDomain ?? [Math.min(...all.map((p) => p[1]), ...refLines.map((r) => r.y)), Math.max(...all.map((p) => p[1]), ...refLines.map((r) => r.y))];
  const sx = (x: number) => pad.l + ((x - x0) / (x1 - x0 || 1)) * (W - pad.l - pad.r);
  const sy = (y: number) => H - pad.b - ((y - y0) / (y1 - y0 || 1)) * (H - pad.t - pad.b);
  const ticks = (a: number, b: number) => Array.from({ length: 5 }, (_, i) => a + ((b - a) * i) / 4);
  const fx = xFormat ?? ((v: number) => v.toFixed(1));
  const fy = yFormat ?? ((v: number) => v.toFixed(1));
  return (
    <div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={yLabel ?? "chart"}>
        {ticks(y0, y1).map((t) => (
          <g key={`y${t}`}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(t)} y2={sy(t)} stroke="#e2e8f0" />
            <text x={pad.l - 6} y={sy(t) + 3} fontSize="10" textAnchor="end" fill="#64748b">{fy(t)}</text>
          </g>
        ))}
        {ticks(x0, x1).map((t) => (
          <text key={`x${t}`} x={sx(t)} y={H - pad.b + 14} fontSize="10" textAnchor="middle" fill="#64748b">{fx(t)}</text>
        ))}
        {diagonal && <line x1={sx(x0)} y1={sy(y0)} x2={sx(x1)} y2={sy(y1)} stroke="#cbd5e1" strokeDasharray="4 4" />}
        {refLines.map((r) => (
          <g key={r.label}>
            <line x1={pad.l} x2={W - pad.r} y1={sy(r.y)} y2={sy(r.y)} stroke={r.color} strokeDasharray="3 3" />
            <text x={W - pad.r} y={sy(r.y) - 3} fontSize="9" textAnchor="end" fill={r.color}>{r.label}</text>
          </g>
        ))}
        {series.map((s) => (
          <g key={s.name}>
            <polyline fill="none" stroke={s.color} strokeWidth="2" strokeDasharray={s.dashed ? "5 4" : undefined}
              points={s.points.map(([x, y]) => `${sx(x)},${sy(y)}`).join(" ")} />
            {s.points.length < 20 && s.points.map(([x, y], i) => <circle key={i} cx={sx(x)} cy={sy(y)} r="2.8" fill={s.color} />)}
          </g>
        ))}
        {xLabel && <text x={(W + pad.l) / 2} y={H - 4} fontSize="10" textAnchor="middle" fill="#475569">{xLabel}</text>}
        {yLabel && <text x={10} y={H / 2} fontSize="10" textAnchor="middle" fill="#475569" transform={`rotate(-90 10 ${H / 2})`}>{yLabel}</text>}
      </svg>
      {series.length > 1 && (
        <div className="mt-1 flex flex-wrap gap-3 text-[11px] text-slate-600">
          {series.map((s) => <span key={s.name} className="flex items-center gap-1"><span className="h-0.5 w-4" style={{ background: s.color }} />{s.name}</span>)}
        </div>
      )}
    </div>
  );
}

export function BarList({ items, format = (v) => v.toFixed(3), color = "bg-brand-500" }: {
  items: { label: string; value: number }[]; format?: (v: number) => string; color?: string;
}) {
  const max = Math.max(...items.map((i) => Math.abs(i.value)), 1e-9);
  return (
    <ul className="space-y-1.5">
      {items.map((i) => (
        <li key={i.label} className="grid grid-cols-[minmax(0,180px)_1fr_56px] items-center gap-2 text-xs">
          <span className="truncate text-slate-600" title={i.label}>{i.label}</span>
          <span className="h-2.5 rounded-sm bg-slate-100"><span className={cn("block h-full rounded-sm", color)} style={{ width: `${(Math.abs(i.value) / max) * 100}%` }} /></span>
          <span className="text-right font-mono tabular-nums text-slate-500">{format(i.value)}</span>
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
            <span className="truncate text-slate-700">{i.label}{i.detail && <span className="text-slate-400"> = {i.detail}</span>}</span>
            <span className={cn("font-mono tabular-nums", i.value >= 0 ? "text-rose-600" : "text-emerald-600")}>{format(i.value)}</span>
          </div>
          <div className="grid grid-cols-2 gap-px">
            <div className="flex h-2 justify-end rounded-l-sm bg-slate-100">
              {i.value < 0 && <div className="h-full rounded-l-sm bg-emerald-500" style={{ width: `${(Math.abs(i.value) / max) * 100}%` }} />}
            </div>
            <div className="h-2 rounded-r-sm bg-slate-100">
              {i.value > 0 && <div className="h-full rounded-r-sm bg-rose-500" style={{ width: `${(i.value / max) * 100}%` }} />}
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
    <div className={cn("rounded p-3 text-center", good ? "bg-brand-50 text-brand-900" : "bg-rose-50 text-rose-900")}>
      <div className="text-lg font-semibold tabular-nums">{v.toLocaleString()}</div>
      <div className="text-[10px] opacity-70">{((v / total) * 100).toFixed(1)}%</div>
    </div>
  );
  return (
    <div className="grid grid-cols-[auto_1fr_1fr] items-center gap-1.5 text-xs">
      <span />
      <span className="text-center text-slate-500">Predicted no</span>
      <span className="text-center text-slate-500">Predicted yes</span>
      <span className="pr-2 text-right text-slate-500">Actual no</span>{cell(tn, true)}{cell(fp, false)}
      <span className="pr-2 text-right text-slate-500">Actual yes</span>{cell(fn, false)}{cell(tp, true)}
    </div>
  );
}

export function Gauge({ value, markers }: { value: number; markers: { at: number; label: string }[] }) {
  const clamp = Math.min(1, Math.max(0, value));
  const scale = (v: number) => Math.min(100, (v / 0.6) * 100); // readmission probabilities rarely exceed 60%
  return (
    <div className="relative mt-2 h-8">
      <div className="absolute inset-x-0 top-3 h-2 rounded-full bg-gradient-to-r from-emerald-200 via-amber-200 to-rose-300" />
      {markers.map((m) => (
        <div key={m.label} className="absolute top-1 h-6 w-px bg-slate-500" style={{ left: `${scale(m.at)}%` }}>
          <span className="absolute left-1 top-5 whitespace-nowrap text-[9px] text-slate-500">{m.label}</span>
        </div>
      ))}
      <div className="absolute top-1.5 h-5 w-1.5 -translate-x-1/2 rounded bg-slate-900" style={{ left: `${scale(clamp)}%` }} aria-hidden />
    </div>
  );
}
