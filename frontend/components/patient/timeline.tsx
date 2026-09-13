"use client";

import { Activity, AlertTriangle, CalendarClock, FlaskConical, LogIn, LogOut, Pill, Siren, Stethoscope, Tag } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { cn, fmtDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { TimelineEvent } from "@/lib/types";

const META: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  admission: { icon: LogIn, label: "Admission", color: "bg-warn-tint text-warn" },
  discharge: { icon: LogOut, label: "Discharge", color: "bg-info-tint text-info" },
  visit: { icon: Stethoscope, label: "Visit", color: "bg-raised text-ink-2" },
  emergency: { icon: Siren, label: "Emergency", color: "bg-high-tint text-high" },
  diagnosis: { icon: Tag, label: "Diagnosis", color: "bg-ai-tint text-ai" },
  medication_start: { icon: Pill, label: "Medication started", color: "bg-ok-tint text-ok" },
  medication_change: { icon: Pill, label: "Medication changed", color: "bg-accent-tint text-accent" },
  medication_stop: { icon: Pill, label: "Medication stopped", color: "bg-raised-2 text-ink-2" },
  lab_abnormal: { icon: FlaskConical, label: "Abnormal lab", color: "bg-warn-tint text-warn" },
  appointment: { icon: CalendarClock, label: "Upcoming", color: "bg-info-tint text-info" },
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
        const meta = META[e.category] ?? { icon: Activity, label: e.category, color: "bg-raised text-ink-2" };
        const Icon = meta.icon;
        const year = e.at.slice(0, 4);
        const showYear = !limit && (i === 0 || events[i - 1].at.slice(0, 4) !== year);
        return (
          <li key={e.id}>
            {showYear && <div className="mb-1 mt-3 text-xs font-semibold text-faint">{year}</div>}
            <div className="flex gap-3 border-l border-line pb-5 pl-4 last:pb-0">
              <span className={cn("-ml-[29px] mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-4 ring-line", meta.color)}>
                <Icon className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className={cn("text-sm", e.severity === "critical" ? "font-semibold text-high" : "text-ink")}>{e.title}</span>
                  {e.severity !== "info" && <AlertTriangle className={cn("h-3.5 w-3.5", e.severity === "critical" ? "text-high" : "text-warn")} />}
                </div>
                {e.detail && <p className="text-xs text-muted">{e.detail}</p>}
                <p className="text-[11px] text-faint">{fmtDate(e.at)} · {meta.label} · {e.source_type.replace(/_/g, " ")} #{e.source_id}</p>
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
        <select value={months} onChange={(e) => setMonths(Number(e.target.value))} className="rounded-lg border border-line-strong bg-panel px-2 py-1 text-xs" aria-label="Period">
          <option value={12}>12 months</option><option value={36}>3 years</option><option value={120}>10 years</option>
        </select>
      }>
      <div className="mb-3 flex flex-wrap gap-1.5">
        <button onClick={() => setActive(null)} className={cn("rounded-full px-2.5 py-1 text-xs font-medium transition-colors", !active ? "bg-accent text-white" : "bg-panel text-ink-2 ring-1 ring-inset ring-line hover:bg-sunken")}>All</button>
        {FILTERS.map(([label]) => (
          <button key={label} onClick={() => setActive(label)} className={cn("rounded-full px-2.5 py-1 text-xs font-medium transition-colors", active === label ? "bg-accent text-white" : "bg-panel text-ink-2 ring-1 ring-inset ring-line hover:bg-sunken")}>{label}</button>
        ))}
      </div>
      <TimelineList patientId={patientId} months={months} filter={filter} />
    </Card>
  );
}
