"use client";

import { Activity, AlertTriangle, ClipboardPen } from "lucide-react";
import { useState } from "react";

import { LineChart } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { DataTable } from "@/components/ui/table";
import { RISK, VitalsRow } from "@/components/ward/board-card";
import { RecordObservations } from "@/components/ward/record-observations";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDateTime, fmtTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { VitalSigns } from "@/lib/types";

export function ObservationsTab({ patientId, patientName }: { patientId: number; patientName: string }) {
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi<VitalSigns[]>(`/patients/${patientId}/vitals?hours=336`);
  const [recording, setRecording] = useState(false);
  const button = can(PERMS.clinicalWrite)
    ? <Button size="sm" onClick={() => setRecording(true)}><ClipboardPen className="h-3.5 w-3.5" aria-hidden /> Record observations</Button>
    : null;
  const modal = recording
    ? <RecordObservations patientId={patientId} patientName={patientName} onClose={() => setRecording(false)}
        onSaved={() => { setRecording(false); reload(); }} />
    : null;

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={8} />;
  if (!data?.length) {
    return (
      <Card title="Bedside observations" actions={button}>
        <EmptyState title="No observations in the last two weeks"
          message="Observations are recorded at the bedside and scored with NEWS2." icon={<Activity className="h-5 w-5" />} />
        {modal}
      </Card>
    );
  }
  const latest = data[0];
  const risk = latest.news2.applies ? RISK[latest.news2.risk] : null;
  const series = [...data].reverse().map((v) => [new Date(v.recorded_at).getTime(), v.news2_score] as [number, number]);

  return (
    <div className="space-y-4">
      <Card title="Latest observations" subtitle={`Recorded ${fmtDateTime(latest.recorded_at)} UTC${latest.recorded_by ? ` by ${latest.recorded_by}` : ""}`}
        actions={button}>
        <div className="flex flex-wrap items-start gap-x-8 gap-y-4">
          {risk ? (
            <div>
              <div className={cn("tabular font-display text-[40px] font-semibold leading-none", risk.text)}>{latest.news2.score}</div>
              <Badge tone={risk.tone} className="mt-2">NEWS2 · {risk.label}</Badge>
            </div>
          ) : null}
          <div className="min-w-0 flex-1">
            <VitalsRow v={latest} />
            <p className="mt-3 text-[13px] leading-relaxed text-ink-2">
              {latest.news2.applies
                ? <><span className="font-medium text-ink">{latest.news2.monitoring}.</span> {latest.news2.response}</>
                : latest.news2.note}
            </p>
            {latest.news2.triggers.length > 0 && (
              <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-high-tint px-2.5 py-1.5 text-[13px] font-medium text-high">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                <span>Rapid response criteria (Patient Safety Guidelines, section 6): {latest.news2.triggers.join("; ")}.</span>
              </p>
            )}
          </div>
        </div>
      </Card>

      <Card title="NEWS2 over time" subtitle={`${data.length} sets of observations, most recent first`}>
        <LineChart height={200} series={[{ name: "NEWS2", color: "var(--color-accent)", points: series }]}
          yDomain={[0, Math.max(8, ...series.map((p) => p[1]))]}
          refLines={[{ y: 5, label: "urgent response", color: "var(--color-warn)" },
                     { y: 7, label: "emergency response", color: "var(--color-high)" }]}
          xFormat={(v) => fmtTime(new Date(v).toISOString())} yFormat={(v) => v.toFixed(0)} />
      </Card>

      <Card bodyClassName="p-0" title="All observations">
        {modal}
        <DataTable dense rows={data}
          columns={[
            { key: "at", header: "Recorded", render: (v) => <span className="whitespace-nowrap">{fmtDateTime(v.recorded_at)}</span> },
            { key: "rr", header: "Resp", render: (v) => <span className="tabular">{v.respiratory_rate}</span> },
            { key: "spo2", header: "SpO₂", render: (v) => <span className="tabular">{v.spo2}%{v.spo2_scale === 2 ? " (s2)" : ""}</span> },
            { key: "o2", header: "O₂", render: (v) => v.on_oxygen ? <Badge tone="warning">oxygen</Badge> : <span className="text-muted">air</span> },
            { key: "bp", header: "BP", render: (v) => <span className="tabular">{v.systolic_bp}{v.diastolic_bp ? `/${v.diastolic_bp}` : ""}</span> },
            { key: "hr", header: "Pulse", render: (v) => <span className="tabular">{v.heart_rate}</span> },
            { key: "temp", header: "Temp", render: (v) => <span className="tabular">{v.temperature.toFixed(1)}</span> },
            { key: "acvpu", header: "ACVPU", render: (v) => v.consciousness },
            { key: "news2", header: "NEWS2", render: (v) => v.news2.applies
              ? <Badge tone={RISK[v.news2_risk].tone}>{v.news2_score}</Badge>
              : <span className="text-xs text-muted" title={v.news2.note ?? undefined}>not used</span> },
            { key: "by", header: "Recorded by", render: (v) => <span className="text-xs text-muted">{v.recorded_by ?? (v.source === "seed" ? "ward staff" : "—")}</span> },
          ]} />
      </Card>
    </div>
  );
}
