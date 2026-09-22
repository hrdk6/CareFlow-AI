"use client";

import { Activity, BedDouble, Clock, Radio, RefreshCw, Siren } from "lucide-react";
import { useEffect, useState } from "react";

import { CitationChip } from "@/components/assistant/answer";
import { SourceDrawer } from "@/components/assistant/source-drawer";
import { PageHeader, StatCard } from "@/components/ui/card";
import { IconButton } from "@/components/ui/button";
import { EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { WardCard } from "@/components/ward/board-card";
import { RecordObservations } from "@/components/ward/record-observations";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Citation, WardBoard, WardPatient } from "@/lib/types";

interface ObservationEvent { patient_id: number; news2: number; risk: string; recorded_at: string }

export default function WardPage() {
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi<WardBoard>("/ward/board");
  const [recording, setRecording] = useState<WardPatient | null>(null);
  const [live, setLive] = useState(false);
  const [arrived, setArrived] = useState<ObservationEvent | null>(null);
  const [flash, setFlash] = useState<number | null>(null);
  const [citation, setCitation] = useState<Citation | null>(null);

  // Live: one line per new observation, with a periodic refresh so the board is still right where a proxy
  // will not hold a stream open. (`reload` keeps its identity, so the stream is opened once.)
  useEffect(() => {
    const onEvent = (event: MessageEvent) => {
      const detail: ObservationEvent = JSON.parse(event.data);
      setArrived(detail);
      setFlash(detail.patient_id);
      reload();
    };
    const source = new EventSource("/api/vitals/stream");
    source.addEventListener("observation", onEvent);
    source.onopen = () => setLive(true);
    source.onerror = () => setLive(false);
    const timer = setInterval(reload, 30_000);
    return () => {
      source.removeEventListener("observation", onEvent);
      source.close();
      clearInterval(timer);
    };
  }, [reload]);

  useEffect(() => {
    if (flash === null) return;
    const timer = setTimeout(() => setFlash(null), 2_500);
    return () => clearTimeout(timer);
  }, [flash]);

  const counts = data?.counts ?? {};
  const urgent = (counts.medium ?? 0) + (counts.high ?? 0);
  const patients = data?.patients ?? [];
  const canRecord = can(PERMS.clinicalWrite);

  return (
    <div className="space-y-4">
      <PageHeader title="Inpatients"
        subtitle="Everyone currently in hospital whose record you can open, with their latest observations and what the hospital's policies ask for. Worst National Early Warning Score first."
        actions={
          <div className="flex items-center gap-2">
            <span className={cn("flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
              live ? "bg-ok-tint text-ok" : "bg-raised text-muted")}>
              <Radio className={cn("h-3.5 w-3.5", live && "attention-dot")} aria-hidden />
              {live ? "Live" : "Refreshing every 30 s"}
            </span>
            <IconButton label="Refresh now" onClick={reload}><RefreshCw className="h-4 w-4" /></IconButton>
          </div>
        } />

      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {arrived && (
        <Notice tone={arrived.news2 >= 5 ? "warning" : "info"} icon={<Activity className="h-3.5 w-3.5 shrink-0" />}>
          New observations recorded at {fmtTime(arrived.recorded_at)} · NEWS2 {arrived.news2} ({arrived.risk.replace("_", "-")}).
        </Notice>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="In hospital" value={counts.inpatients ?? 0} icon={<BedDouble />} hint="Patients you can open" />
        <StatCard label="Urgent response" value={urgent} tone={urgent ? "rose" : "slate"} icon={<Siren />}
          hint="NEWS2 5 or more" />
        <StatCard label="Observations overdue" value={counts.overdue ?? 0} tone={counts.overdue ? "amber" : "slate"}
          icon={<Clock />} hint="Past the frequency the score asks for" />
        <StatCard label="Rapid response criteria" value={counts.rapid_response ?? 0}
          tone={counts.rapid_response ? "rose" : "slate"} icon={<Activity />} hint="Patient Safety Guidelines, section 6" />
      </div>

      {loading && !data && <div className="rounded-xl border border-line bg-panel p-5 shadow-e1"><Skeleton lines={8} /></div>}
      {data && patients.length === 0 && (
        <div className="rounded-xl border border-line bg-panel shadow-e1">
          <EmptyState title="Nobody is in hospital under your care" message="Inpatients appear here as soon as they are admitted." icon={<BedDouble className="h-5 w-5" />} />
        </div>
      )}
      <div className="space-y-3">
        {patients.map((row, i) => (
          <div key={row.patient_id} className="stagger-in" style={{ "--i": Math.min(i, 8) } as React.CSSProperties}>
            <WardCard row={row} canRecord={canRecord} flash={flash === row.patient_id} onRecord={() => setRecording(row)} />
          </div>
        ))}
      </div>

      {data && data.citations.length > 0 && (
        <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1 px-1 text-[11px] leading-relaxed text-faint">
          {data.note} Escalation follows
          {data.citations.map((c) => (
            <span key={c.id} className="inline-flex items-center gap-1">
              <CitationChip id={c.id} label={`${c.document_title} — ${c.section_path}`} onClick={() => setCitation(c)} />
              <span>{c.document_title}, {c.section_path.replace(/^\d+\.\s*/, "")}</span>
            </span>
          ))}
        </p>
      )}

      <SourceDrawer citation={citation} onClose={() => setCitation(null)} />
      {recording && (
        <RecordObservations patientId={recording.patient_id} patientName={recording.full_name}
          onClose={() => setRecording(null)} onSaved={() => { setRecording(null); reload(); }} />
      )}
    </div>
  );
}
