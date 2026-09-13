"use client";

import Link from "next/link";

import { BarList } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { pct, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Similarity } from "@/lib/types";

export function SimilarTab({ patientId }: { patientId: number }) {
  const { data, error, loading, reload } = useApi<Similarity>(`/patients/${patientId}/similar?k=8`);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={8} />;
  if (!data) return null;
  const cp = data.cohort_patterns;
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <Card title="Most similar patients" className="xl:col-span-2" bodyClassName="p-0"
        subtitle={`${data.metric} over ${data.representation_version} structured representation · ${data.candidate_scope}`}>
        {data.results.length === 0 ? <EmptyState title="No similar patients within your access" /> : (
          <ul className="divide-y divide-line">
            {data.results.map((s) => (
              <li key={s.patient_id} className="grid gap-2 px-4 py-3 sm:grid-cols-[1fr_140px]">
                <div className="min-w-0">
                  <Link href={`/patients/${s.patient_id}`} className="text-sm font-medium text-ink hover:text-accent">{s.full_name}</Link>
                  <span className="ml-2 font-mono text-xs text-faint">{s.mrn}</span>
                  <span className="ml-2 text-xs text-muted">{Math.round(s.age)}y {s.sex}</span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {s.shared_diagnosis_categories.map((c) => <Badge key={c} tone="violet">{c}</Badge>)}
                    {s.shared_medication_groups.map((g) => <Badge key={g} tone="info">{titleCase(g)}</Badge>)}
                  </div>
                  <div className="mt-1 truncate text-xs text-muted">{s.diagnoses.slice(0, 3).join(" · ")}</div>
                </div>
                <div className="text-right text-xs text-muted">
                  <div className="text-lg font-semibold tabular-nums text-ink">{s.similarity.toFixed(2)}</div>
                  <div>{s.admissions_2y} admissions / 2y</div>
                  <div>HbA1c {s.last_hba1c ?? "—"} · eGFR {s.last_egfr ?? "—"}</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <div className="space-y-4">
        <Card title="Historical patterns in this cohort" subtitle="Descriptive only — not a prediction for this patient">
          {cp.cohort_size ? (
            <div className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded bg-sunken p-2"><div className="text-xs text-muted">30-day readmissions</div><div className="font-semibold">{cp.readmissions_within_30d} of {cp.discharges} ({pct(cp.readmission_rate ?? null, 0)})</div></div>
                <div className="rounded bg-sunken p-2"><div className="text-xs text-muted">Mean stay</div><div className="font-semibold">{cp.mean_length_of_stay_days ?? "—"} days</div></div>
              </div>
              <div>
                <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Common diagnoses</div>
                <BarList items={(cp.common_diagnoses ?? []).map((d) => ({ label: d.description, value: d.patients }))} format={(v) => `${v}`} color="bg-ai" />
              </div>
              <div>
                <div className="mb-1 text-[11px] font-semibold uppercase text-muted">Common active medications</div>
                <BarList items={(cp.common_active_medications ?? []).map((m) => ({ label: m.medication, value: m.patients }))} format={(v) => `${v}`} color="bg-info" />
              </div>
            </div>
          ) : <EmptyState title="No cohort" />}
        </Card>
        <Notice tone="warning">{data.disclaimer}</Notice>
      </div>
    </div>
  );
}
