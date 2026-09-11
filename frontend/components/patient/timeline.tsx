"use client";

import { Activity, AlertTriangle, CalendarClock, FlaskConical, LogIn, LogOut, Pill, Siren, Stethoscope, Tag } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { cn, fmtDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { TimelineEvent } from "@/lib/types";

const META: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  admission: { icon: LogIn, label: "Admission", color: "bg-amber-100 text-amber-700" },
  discharge: { icon: LogOut, label: "Discharge", color: "bg-sky-100 text-sky-700" },
  visit: { icon: Stethoscope, label: "Visit", color: "bg-slate-100 text-slate-600" },
  emergency: { icon: Siren, label: "Emergency", color: "bg-rose-100 text-rose-700" },
  diagnosis: { icon: Tag, label: "Diagnosis", color: "bg-violet-100 text-violet-700" },
  medication_start: { icon: Pill, label: "Medication started", color: "bg-emerald-100 text-emerald-700" },
  medication_change: { icon: Pill, label: "Medication changed", color: "bg-brand-100 text-brand-800" },
  medication_stop: { icon: Pill, label: "Medication stopped", color: "bg-slate-200 text-slate-700" },
  lab_abnormal: { icon: FlaskConical, label: "Abnormal lab", color: "bg-orange-100 text-orange-700" },
  appointment: { icon: CalendarClock, label: "Upcoming", color: "bg-sky-100 text-sky-700" },
};

export function TimelineList({ patientId, months = 36, limit, filter }: {
  patientId: number; months?: number; limit?: number; filter?: Set<string>;
}) {
  const { data, error, loading, reload } = useApi<{ events: TimelineEvent[] }>(`/patients/${patientId}/timeline?months=${months}`);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={6} />;
  let events = data?.events ?? [];
  if (filter?.size) events = events.filter((e) => filter.has(e.category));
  if (limit) events = events.slice(0, limit);
  if (!events.length) return <EmptyState title="No events in this period" />;
  return (
    <ol className="relative space-y-0">
      {events.map((e, i) => {
        const meta = META[e.category] ?? { icon: Activity, label: e.category, color: "bg-slate-100 text-slate-600" };
        const Icon = meta.icon;
        const year = e.at.slice(0, 4);
        const showYear = !limit && (i === 0 || events[i - 1].at.slice(0, 4) !== year);
        return (
          <li key={e.id}>
            {showYear && <div className="mb-1 mt-3 text-xs font-semibold text-slate-400">{year}</div>}
            <div className="flex gap-3 border-l border-slate-200 pb-3 pl-4 last:pb-0">
              <span className={cn("-ml-[29px] mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-4 ring-white", meta.color)}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className={cn("text-sm", e.severity === "critical" ? "font-semibold text-rose-700" : "text-slate-800")}>{e.title}</span>
                  {e.severity !== "info" && <AlertTriangle className={cn("h-3.5 w-3.5", e.severity === "critical" ? "text-rose-500" : "text-amber-500")} />}
                </div>
                {e.detail && <p className="text-xs text-slate-500">{e.detail}</p>}
                <p className="text-[11px] text-slate-400">{fmtDate(e.at)} · {meta.label} · {e.source_type.replace(/_/g, " ")} #{e.source_id}</p>
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

const FILTERS: [string, string[]][] = [
  ["Admissions", ["admission", "discharge"]], ["Visits", ["visit", "emergency"]], ["Medications", ["medication_start", "medication_change", "medication_stop"]],
  ["Labs", ["lab_abnormal"]], ["Diagnoses", ["diagnosis"]],
];

export function TimelineTab({ patientId }: { patientId: number }) {
  const [active, setActive] = useState<string | null>(null);
  const [months, setMonths] = useState(36);
  const filter = active ? new Set(FILTERS.find(([l]) => l === active)![1]) : undefined;
  return (
    <Card title="Patient timeline" subtitle="Generated chronologically from structured records; every event links to its source row."
      actions={
        <select value={months} onChange={(e) => setMonths(Number(e.target.value))} className="rounded border border-slate-300 px-2 py-1 text-xs" aria-label="Period">
          <option value={12}>12 months</option><option value={36}>3 years</option><option value={120}>10 years</option>
        </select>
      }>
      <div className="mb-3 flex flex-wrap gap-1.5">
        <button onClick={() => setActive(null)} className={cn("rounded-full px-2.5 py-1 text-xs", !active ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600")}>All</button>
        {FILTERS.map(([label]) => (
          <button key={label} onClick={() => setActive(label)} className={cn("rounded-full px-2.5 py-1 text-xs", active === label ? "bg-slate-800 text-white" : "bg-slate-100 text-slate-600")}>{label}</button>
        ))}
      </div>
      <TimelineList patientId={patientId} months={months} filter={filter} />
    </Card>
  );
}
