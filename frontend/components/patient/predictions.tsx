"use client";

import { ChevronRight, Gauge as GaugeIcon, Hourglass, Info } from "lucide-react";

import { DivergingBars, Gauge } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card, KeyValue } from "@/components/ui/card";
import { ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { fmtDate, fmtDateTime, pct } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Prediction } from "@/lib/types";

const BAND_TONE = { low: "success", moderate: "warning", high: "danger" } as const;

/** Engineering provenance, folded away so the card reads as a clinical estimate first. */
function ModelMeta({ p, children }: { p: Prediction; children?: React.ReactNode }) {
  return (
    <details className="group mt-4 border-t border-line pt-3 text-xs text-muted">
      <summary className="flex cursor-pointer list-none items-center gap-1 font-medium text-ink-2 hover:text-ink [&::-webkit-details-marker]:hidden">
        <ChevronRight className="h-3.5 w-3.5 transition-transform group-open:rotate-90" aria-hidden /> Model details
      </summary>
      <div className="mt-2 space-y-1.5 pl-[18px] leading-relaxed">
        {children}
        <p>Model <span className="font-mono text-ink-2">{p.model_name}@{p.model_version}</span> · {p.model_algorithm}</p>
        <p>Trained {p.trained_at?.slice(0, 10)} · predicted {fmtDateTime(p.predicted_at)}</p>
      </div>
    </details>
  );
}

const riskWords = (v: number) => (v >= 0 ? "Raises risk" : "Lowers risk");

export function RiskCard({ patientId, compact }: { patientId: number; compact?: boolean }) {
  const { data: p, error, loading, reload } = useApi<Prediction>(`/patients/${patientId}/risk`);
  return (
    <Card title={<span className="flex items-center gap-1.5"><GaugeIcon className="h-4 w-4" /> 30-day readmission risk</span>} subtitle="Model estimate · decision support">
      {error ? <ErrorState error={error} onRetry={reload} compact /> : null}
      {loading && !p && <Skeleton lines={4} />}
      {p && p.status !== "ok" && <p className="text-sm text-muted">{p.reason}</p>}
      {p && p.status === "ok" && p.value !== null && (
        <>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-semibold tabular-nums text-ink">{pct(p.value)}</div>
              <div className="text-xs text-muted">{(p.value / p.context.base_rate).toFixed(1)}× the training base rate ({pct(p.context.base_rate)})</div>
            </div>
            <div className="text-right">
              <Badge tone={BAND_TONE[p.label as keyof typeof BAND_TONE] ?? "neutral"}>{p.label} risk</Badge>
              <div className="mt-1 text-[11px] text-muted">{p.flagged ? "Above" : "Below"} alert threshold {pct(p.threshold)}</div>
            </div>
          </div>
          <Gauge value={p.value} markers={[{ at: p.context.base_rate, label: "base" }, { at: p.threshold ?? 0, label: "alert" }, { at: p.context.high_risk_cutoff, label: "high" }]} />
          <p className="mt-4 text-[11px] text-muted">Scored for the admission of {fmtDate(p.reference?.admitted_at)} ({p.reference?.reason}).</p>
          <div className="mt-3">
            <div className="mb-1.5 text-xs font-medium text-muted">What moved this estimate</div>
            <DivergingBars plain format={riskWords} items={p.factors.slice(0, compact ? 4 : 8).map((f) => ({ label: f.label, detail: f.value, value: f.contribution }))} />
            <p className="mt-2 text-xs text-muted">These describe how the model reached its estimate, not what caused the risk.</p>
          </div>
          {!p.in_training_population && <div className="mt-2"><Notice tone="warning">Outside the model&apos;s training population (diabetic inpatients).</Notice></div>}
          {!compact && p.notes.map((n) => <div key={n} className="mt-2"><Notice tone="info" icon={<Info className="h-3.5 w-3.5" />}>{n}</Notice></div>)}
          <ModelMeta p={p}>
            <p>Factor sizes are SHAP contributions on the {p.explanation_space?.replace("_", " ")} scale.</p>
          </ModelMeta>
        </>
      )}
    </Card>
  );
}

export function LosCard({ patientId, compact }: { patientId: number; compact?: boolean }) {
  const { data: p, error, loading, reload } = useApi<Prediction>(`/patients/${patientId}/length-of-stay`);
  return (
    <Card title={<span className="flex items-center gap-1.5"><Hourglass className="h-4 w-4" /> Estimated length of stay</span>} subtitle="Predicted at admission time · estimate only">
      {error ? <ErrorState error={error} onRetry={reload} compact /> : null}
      {loading && !p && <Skeleton lines={3} />}
      {p && p.status !== "ok" && <p className="text-sm text-muted">{p.reason}</p>}
      {p && p.status === "ok" && p.value !== null && (
        <>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-semibold tabular-nums text-ink">{p.value.toFixed(1)} <span className="text-base font-normal text-muted">days</span></div>
              <div className="text-xs text-muted">80% interval {p.interval?.[0]}–{p.interval?.[1]} days</div>
            </div>
            {p.reference?.actual_length_of_stay_days != null && (
              <div className="text-right text-xs text-muted">Actual stay<div className="text-lg font-semibold tabular-nums text-ink">{p.reference.actual_length_of_stay_days} d</div></div>
            )}
          </div>
          {!compact && (
            <div className="mt-3">
              <div className="mb-1.5 text-xs font-medium text-muted">What moved this estimate</div>
              <DivergingBars plain items={p.factors.map((f) => ({ label: f.label, detail: f.value, value: f.contribution }))} format={(v) => `${v >= 0 ? "Adds" : "Shortens by"} ${Math.abs(v).toFixed(1)} d`} />
            </div>
          )}
          <p className="mt-3 text-xs text-muted">Usually within ±{p.context.test_mae_days?.toFixed(1)} days. Details known at admission explain only a small part of how long stays last.</p>
          <ModelMeta p={p}>
            <p>Test MAE {p.context.test_mae_days?.toFixed(2)} days · R² {p.context.test_r2?.toFixed(2)}</p>
          </ModelMeta>
        </>
      )}
    </Card>
  );
}

export function PredictionsTab({ patientId }: { patientId: number }) {
  const { data: history } = useApi<{ id: number; type: string; value: number; label: string | null; created_at: string; version: string }[]>(`/patients/${patientId}/predictions`);
  const { data: risk } = useApi<Prediction>(`/patients/${patientId}/risk`);
  return (
    <div className="space-y-4">
      <Notice tone="info" icon={<Info className="h-3.5 w-3.5 shrink-0" />}>
        Predictions are statistical estimates from models trained on the public, de-identified UCI Diabetes 130-US hospitals dataset. They support — never replace — clinical judgement and do not diagnose.
      </Notice>
      <div className="grid gap-4 lg:grid-cols-2">
        <RiskCard patientId={patientId} />
        <LosCard patientId={patientId} />
      </div>
      {risk?.status === "ok" && (
        <Card title="Model inputs for this prediction" subtitle="Derived from the database; missing values are imputed by the model pipeline">
          <KeyValue columns={3} items={Object.entries(risk.features).map(([k, v]) => [k.replace(/_/g, " "), String(v ?? "missing")])} />
          <div className="mt-3 space-y-1 text-[11px] text-muted">{risk.limitations.map((l) => <p key={l}>• {l}</p>)}</div>
        </Card>
      )}
      <Card title="Prediction history" subtitle="Every served prediction is persisted with its model version" bodyClassName="p-0">
        <ul className="divide-y divide-line text-sm">
          {(history ?? []).map((h) => (
            <li key={h.id} className="flex items-center justify-between px-4 py-2">
              <span className="text-ink-2">{h.type === "readmission_30d" ? `Readmission ${pct(h.value)}` : `LOS ${h.value.toFixed(1)} days`}</span>
              <span className="text-xs text-muted">v{h.version} · {fmtDateTime(h.created_at)}</span>
            </li>
          ))}
          {history?.length === 0 && <li className="px-4 py-3 text-xs text-muted">No predictions stored yet.</li>}
        </ul>
      </Card>
    </div>
  );
}
