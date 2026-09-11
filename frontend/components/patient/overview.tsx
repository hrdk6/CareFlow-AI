"use client";

import { BedDouble } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate, titleCase } from "@/lib/format";
import type { PatientClinical } from "@/lib/types";

import { LosCard, RiskCard } from "./predictions";
import { TimelineList } from "./timeline";

export function OverviewTab({ patient, clinical, onOpen }: { patient: PatientClinical; clinical: boolean; onOpen: (tab: string) => void }) {
  const { can } = useAuth();
  if (!clinical) {
    return (
      <Card title="Registration details">
        <p className="text-sm text-slate-600">Your role can view registration and scheduling information only. Clinical data, predictions and the patient-level AI summary are not available to you.</p>
      </Card>
    );
  }
  const adm = patient.current_admission;
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        {adm && (
          <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
            <BedDouble className="mt-0.5 h-4 w-4" />
            <div>Currently admitted to <b>{adm.department}</b>{adm.ward ? ` (${adm.ward})` : ""} since {fmtDate(adm.admitted_at)} — {adm.reason}. Attending: {adm.attending_doctor ?? "—"}.</div>
          </div>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Active problems" subtitle={`${patient.admission_count} admissions on record`}>
            {patient.active_diagnoses.length === 0 ? <EmptyState title="No active problems" /> : (
              <ul className="space-y-2">
                {patient.active_diagnoses.map((d) => (
                  <li key={d.id} className="flex items-start justify-between gap-2 text-sm">
                    <span className="text-slate-800">{d.description}</span>
                    <span className="shrink-0 text-right">
                      <span className="font-mono text-[11px] text-slate-500">{d.icd10_code}</span>
                      <span className="block text-[11px] text-slate-400">since {d.diagnosed_on.slice(0, 4)}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Current medications" actions={<button onClick={() => onOpen("prescriptions")} className="text-xs text-brand-700 hover:underline">All</button>}>
            {patient.current_medications.length === 0 ? <EmptyState title="No active prescriptions" /> : (
              <ul className="space-y-2">
                {patient.current_medications.map((m) => (
                  <li key={m.id} className="text-sm">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-slate-800">{m.medication}</span>
                      {m.is_high_alert && <Badge tone="danger">High-alert</Badge>}
                    </div>
                    <div className="text-xs text-slate-500">{m.dosage} · {m.frequency} · {titleCase(m.drug_class)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <Card title="Recent timeline" actions={<button onClick={() => onOpen("timeline")} className="text-xs text-brand-700 hover:underline">Full timeline</button>}>
          <TimelineList patientId={patient.id} months={12} limit={8} />
        </Card>
      </div>
      {can(PERMS.ml) && (
        <div className="space-y-4">
          <RiskCard patientId={patient.id} compact />
          <LosCard patientId={patient.id} compact />
        </div>
      )}
    </div>
  );
}
