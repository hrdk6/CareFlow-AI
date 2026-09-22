"use client";

import {
  Activity, AlertTriangle, CalendarClock, FlaskConical, LogIn, LogOut, Pill, ScanLine, Siren, Stethoscope, Tag,
} from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { Segmented } from "@/components/ui/tabs";
import { cn, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { TimelineEvent } from "@/lib/types";

const NEUTRAL = "bg-raised text-ink-2 ring-line";

const META: Record<string, { icon: React.ElementType; label: string; color: string }> = {
  admission: { icon: LogIn, label: "Admission", color: "bg-warn-tint text-warn ring-warn-edge" },
  discharge: { icon: LogOut, label: "Discharge", color: "bg-info-tint text-info ring-info-edge" },
  visit: { icon: Stethoscope, label: "Visit", color: NEUTRAL },
  emergency: { icon: Siren, label: "Emergency", color: "bg-high-tint text-high ring-high-edge" },
  diagnosis: { icon: Tag, label: "Diagnosis", color: "bg-ai-tint text-ai ring-ai-edge" },
  medication_start: { icon: Pill, label: "Medication started", color: "bg-ok-tint text-ok ring-ok-edge" },
  medication_change: { icon: Pill, label: "Medication changed", color: "bg-accent-tint text-accent ring-accent-edge" },
  medication_stop: { icon: Pill, label: "Medication stopped", color: NEUTRAL },
  lab_abnormal: { icon: FlaskConical, label: "Abnormal lab", color: "bg-warn-tint text-warn ring-warn-edge" },
  appointment: { icon: CalendarClock, label: "Upcoming", color: "bg-info-tint text-info ring-info-edge" },
  imaging: { icon: ScanLine, label: "Radiology report", color: "bg-info-tint text-info ring-info-edge" },
};

function dayMonth(iso: string) {
  return new Date(iso).toLocaleDateString("en-GB", { day: "2-digit", month: "short", timeZone: "UTC" });
}

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
    // Keyed by the filter so a new filter replays the list entrance instead of swapping rows in place.
    <ol key={filter ? [...filter].join() : "all"} className={cn("transition-opacity duration-200", loading && "opacity-50")}>
      {events.map((e, i) => {
        const meta = META[e.category] ?? { icon: Activity, label: titleCase(e.category), color: NEUTRAL };
        const Icon = meta.icon;
        const last = i === events.length - 1;
        return (
          <li key={e.id} className="stagger-in grid grid-cols-[28px_minmax(0,1fr)] gap-x-3 pb-5 last:pb-0 sm:grid-cols-[64px_28px_minmax(0,1fr)]"
            style={{ "--i": Math.min(i, 10) } as React.CSSProperties}>
            <time dateTime={e.at} className="hidden pt-1 text-right text-[12px] leading-tight text-ink-2 sm:block">
              {dayMonth(e.at)}
              <span className="block text-faint">{e.at.slice(0, 4)}</span>
            </time>
            <span className="relative flex justify-center">
              {!last && <span className="absolute -bottom-4 left-1/2 top-8 w-px -translate-x-1/2 bg-line" aria-hidden />}
              <span className={cn("relative flex h-7 w-7 items-center justify-center rounded-full ring-1 ring-inset", meta.color)}>
                <Icon className="h-3.5 w-3.5" aria-hidden />
              </span>
            </span>
            <div className="min-w-0 pt-0.5">
              <p className="flex flex-wrap items-center gap-x-1.5">
                <span className={cn("text-sm", e.severity === "critical" ? "font-semibold text-high" : "font-medium text-ink")}>{e.title}</span>
                {e.severity !== "info" && (
                  <AlertTriangle className={cn("h-3.5 w-3.5", e.severity === "critical" ? "text-high" : "text-warn")}
                    aria-label={e.severity === "critical" ? "Critical" : "Needs attention"} />
                )}
              </p>
              {e.detail && <p className="mt-0.5 text-[13px] leading-snug text-muted">{e.detail}</p>}
              <p className="mt-0.5 text-[12px] text-faint">
                <span className="sm:hidden">{dayMonth(e.at)} {e.at.slice(0, 4)} · </span>
                {meta.label} · {titleCase(e.source_type)} #{e.source_id}
              </p>
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
  const [active, setActive] = useState("");
  const [months, setMonths] = useState(36);
  const filter = active ? new Set(FILTERS.find(([l]) => l === active)![1]) : undefined;
  return (
    <Card title="Patient timeline" subtitle="Built in date order from the patient's records. Each event names the record it came from."
      actions={
        <Select value={months} onChange={(e) => setMonths(Number(e.target.value))} className="w-32" aria-label="Period"
          options={[{ value: 12, label: "12 months" }, { value: 36, label: "3 years" }, { value: 120, label: "10 years" }]} />
      }>
      <Segmented label="Event type" className="mb-5 w-fit" value={active} onChange={setActive}
        options={[{ value: "", label: "All" }, ...FILTERS.map(([label]) => ({ value: label, label }))]} />
      <TimelineList patientId={patientId} months={months} filter={filter} />
    </Card>
  );
}
