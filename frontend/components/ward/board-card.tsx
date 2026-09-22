"use client";

import { AlertTriangle, ArrowRight, ClipboardPen, Clock } from "lucide-react";
import Link from "next/link";

import { Avatar } from "@/components/ui/avatar";
import { Badge, type Tone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn, fmtTime } from "@/lib/format";
import type { Risk, VitalSigns, WardPatient } from "@/lib/types";

export const RISK: Record<Risk, { label: string; tone: Tone; rail: string; text: string }> = {
  low: { label: "Low", tone: "success", rail: "bg-ok", text: "text-ok" },
  low_medium: { label: "Low-medium", tone: "warning", rail: "bg-warn", text: "text-warn" },
  medium: { label: "Medium", tone: "warning", rail: "bg-warn", text: "text-warn" },
  high: { label: "High", tone: "danger", rail: "bg-high", text: "text-high" },
};

/** The last dozen scores, so a rising trend is visible before the number alone would say much. */
export function Sparkline({ points, className }: { points: number[]; className?: string }) {
  if (points.length < 2) return null;
  const max = Math.max(4, ...points), w = 68, h = 20;
  const step = w / (points.length - 1);
  const d = points.map((p, i) => `${i * step},${h - (p / max) * (h - 3) - 1.5}`).join(" ");
  const rising = points[points.length - 1] > points[0];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} className={cn("overflow-visible", className)} role="img"
      aria-label={`NEWS2 trend: ${points.join(", ")}`}>
      <polyline points={d} fill="none" strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"
        className={rising ? "stroke-[var(--color-high)]" : "stroke-[var(--color-line-strong)]"} />
      <circle cx={(points.length - 1) * step} cy={h - (points[points.length - 1] / max) * (h - 3) - 1.5} r="2.2"
        className={rising ? "fill-[var(--color-high)]" : "fill-[var(--color-muted)]"} />
    </svg>
  );
}

const PARAMETER: Record<string, string> = {
  respiratory_rate: "Resp", spo2: "SpO₂", air_or_oxygen: "O₂", systolic_bp: "BP", heart_rate: "Pulse",
  consciousness: "ACVPU", temperature: "Temp",
};

/** One observation's values; anything that scored is marked with the points it contributed. */
export function VitalsRow({ v, className }: { v: VitalSigns; className?: string }) {
  const items: [key: string, label: string, value: string][] = [
    ["respiratory_rate", PARAMETER.respiratory_rate, `${v.respiratory_rate}/min`],
    ["spo2", PARAMETER.spo2, `${v.spo2}%${v.spo2_scale === 2 ? " (scale 2)" : ""}`],
    ["air_or_oxygen", PARAMETER.air_or_oxygen, v.on_oxygen ? "oxygen" : "air"],
    ["systolic_bp", PARAMETER.systolic_bp, `${v.systolic_bp}${v.diastolic_bp ? `/${v.diastolic_bp}` : ""}`],
    ["heart_rate", PARAMETER.heart_rate, `${v.heart_rate}/min`],
    ["temperature", PARAMETER.temperature, `${v.temperature.toFixed(1)} °C`],
    ["consciousness", PARAMETER.consciousness, v.consciousness],
  ];
  return (
    <dl className={cn("flex flex-wrap gap-x-4 gap-y-1.5", className)}>
      {items.map(([key, label, value]) => {
        const points = v.news2.parameters[key] ?? 0;
        return (
          <div key={key} className="flex items-baseline gap-1.5">
            <dt className="text-[11px] text-muted">{label}</dt>
            <dd className={cn("tabular text-[13px]", points > 0 ? "font-semibold text-ink" : "text-ink-2")}>
              {value}
              {points > 0 && (
                <span className={cn("ml-1 rounded px-1 text-[10px] font-semibold",
                  points === 3 ? "bg-high-tint text-high" : "bg-warn-tint text-warn")}>+{points}</span>
              )}
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

export function WardCard({ row, onRecord, canRecord, flash }: {
  row: WardPatient; onRecord: () => void; canRecord: boolean; flash?: boolean;
}) {
  const latest = row.latest;
  // NEWS2 is not validated under 16: the values are shown, the risk band is not.
  const risk = latest?.news2.applies ? RISK[latest.news2.risk] : null;
  const overdue = row.overdue_hours !== null;
  return (
    <article className={cn("relative overflow-hidden rounded-xl border bg-panel shadow-e1 transition-[box-shadow,border-color] duration-300",
      latest?.news2.risk === "high" ? "border-high-edge" : "border-line", flash && "ring-2 ring-accent/40")}>
      <span className={cn("absolute inset-y-0 left-0 w-1", risk ? risk.rail : "bg-line-strong")} aria-hidden />
      <div className="flex flex-wrap items-start gap-x-5 gap-y-3 px-5 py-4 pl-6">
        <Avatar name={row.full_name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link href={`/patients/${row.patient_id}`} className="text-[15px] font-semibold text-ink hover:text-accent">
              {row.full_name}
            </Link>
            <span className="rounded bg-raised px-1.5 font-mono text-[11px] leading-5 text-ink-2">{row.mrn}</span>
            <span className="text-xs text-muted">{row.age} y · {row.department}{row.ward ? ` · Ward ${row.ward}` : ""} · Day {row.day_of_stay}</span>
          </div>
          <p className="mt-0.5 truncate text-[13px] text-muted">{row.reason}{row.attending ? ` · ${row.attending}` : ""}</p>
          {latest ? <VitalsRow v={latest} className="mt-2.5" /> : (
            <p className="mt-2 text-[13px] text-muted">No observations recorded yet.</p>
          )}
          {latest && latest.news2.triggers.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {latest.news2.triggers.map((t) => (
                <li key={t}><Badge tone="danger"><AlertTriangle className="h-3 w-3" aria-hidden /> {t}</Badge></li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex items-center gap-4">
          {latest && !latest.news2.applies && (
            <p className="max-w-[190px] text-right text-[11px] leading-snug text-muted" title={latest.news2.note ?? undefined}>
              NEWS2 is not used for this patient (under 16); the paediatric chart applies.
            </p>
          )}
          {latest && risk && (
            <div className="text-right">
              <div className={cn("tabular font-display text-[30px] font-semibold leading-none", risk.text)}>{latest.news2.score}</div>
              <div className="mt-1 text-[11px] font-medium text-muted">NEWS2 · {risk.label}</div>
              <Sparkline points={row.trend.map((t) => t.score)} className="mt-1.5 ml-auto block" />
            </div>
          )}
          <div className="flex flex-col items-end gap-1.5">
            {latest && (
              <span className={cn("flex items-center gap-1 whitespace-nowrap text-[11px]", overdue ? "font-medium text-high" : "text-muted")}>
                <Clock className="h-3 w-3" aria-hidden />
                {overdue ? `Observations overdue by ${row.overdue_hours} h`
                  : `Last ${fmtTime(latest.recorded_at)}${row.due_at ? ` · due ${fmtTime(row.due_at)}` : ""}`}
              </span>
            )}
            {canRecord && (
              <Button size="sm" variant={overdue || (latest?.news2.score ?? 0) >= 5 ? "primary" : "secondary"} onClick={onRecord}>
                <ClipboardPen className="h-3.5 w-3.5" aria-hidden /> Record
              </Button>
            )}
            <Link href={`/patients/${row.patient_id}?tab=observations`}
              className="group flex items-center gap-1 text-[11px] font-medium text-accent hover:text-accent-strong">
              Open record <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </div>
        </div>
      </div>
      {latest && risk && latest.news2.score >= 5 && (
        <p className="border-t border-line bg-sunken/70 px-6 py-2 text-[12px] leading-relaxed text-ink-2">
          <span className="font-medium text-ink">{latest.news2.monitoring}.</span> {latest.news2.response}
        </p>
      )}
    </article>
  );
}
