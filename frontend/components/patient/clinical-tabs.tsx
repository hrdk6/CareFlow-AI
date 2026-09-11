"use client";

import { ChevronDown, Plus, XCircle } from "lucide-react";
import { useMemo, useState } from "react";

import { LineChart } from "@/components/charts";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { DataTable } from "@/components/ui/table";
import { api } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDate, fmtDateTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Appointment, LabReport, MedicalRecord, Medication, Prescription } from "@/lib/types";

export function RecordsTab({ patientId }: { patientId: number }) {
  const { data, error, loading, reload } = useApi<MedicalRecord[]>(`/patients/${patientId}/records`);
  const [open, setOpen] = useState<number | null>(null);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={8} />;
  if (!data?.length) return <EmptyState title="No medical records" />;
  return (
    <Card bodyClassName="p-0" title="Medical records" subtitle={`${data.length} notes, newest first`}>
      <ul className="divide-y divide-slate-100">
        {data.map((r) => (
          <li key={r.id}>
            <button onClick={() => setOpen(open === r.id ? null : r.id)} className="flex w-full items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-50">
              <span className="w-24 shrink-0 text-xs tabular-nums text-slate-500">{fmtDate(r.visit_date)}</span>
              <Badge tone={r.record_type === "emergency" ? "danger" : r.record_type === "discharge_summary" ? "info" : "neutral"}>{titleCase(r.record_type)}</Badge>
              <span className="min-w-0 flex-1 truncate text-sm text-slate-800">{r.chief_complaint}</span>
              <span className="hidden text-xs text-slate-400 sm:inline">{r.doctor_name}</span>
              <ChevronDown className={cn("h-4 w-4 text-slate-400 transition-transform", open === r.id && "rotate-180")} />
            </button>
            {open === r.id && (
              <div className="grid gap-3 bg-slate-50/60 px-4 pb-4 pt-1 text-sm sm:grid-cols-2">
                {([["Symptoms", r.symptoms], ["Assessment", r.diagnosis_summary], ["Notes", r.notes], ["Plan", r.treatment_plan]] as const).map(([k, v]) => (
                  <div key={k}><div className="text-[11px] font-semibold uppercase text-slate-500">{k}</div><p className="text-slate-700">{v || "—"}</p></div>
                ))}
                <div className="text-[11px] text-slate-400 sm:col-span-2">Record #{r.id}{r.admission_id ? ` · admission #${r.admission_id}` : ""}</div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function PrescriptionsTab({ patientId }: { patientId: number }) {
  const { can } = useAuth();
  const [all, setAll] = useState(false);
  const [prescribing, setPrescribing] = useState(false);
  const { data, error, loading, reload } = useApi<Prescription[]>(`/patients/${patientId}/prescriptions`);
  const rows = (data ?? []).filter((p) => all || p.status === "active");

  async function discontinue(rx: Prescription) {
    const reason = window.prompt(`Reason for discontinuing ${rx.medication}?`);
    if (!reason) return;
    try {
      await api(`/prescriptions/${rx.id}/discontinue`, { method: "POST", json: { reason } });
      reload();
    } catch (e) {
      window.alert((e as Error).message);
    }
  }

  return (
    <Card bodyClassName="p-0" title="Prescriptions" subtitle="Outpatient medication orders with change history"
      actions={<>
        <label className="flex items-center gap-1.5 text-xs text-slate-600"><input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} /> Include history</label>
        {can(PERMS.prescribe) && <Button size="sm" onClick={() => setPrescribing(true)}><Plus className="h-3.5 w-3.5" /> Prescribe</Button>}
      </>}>
      <DataTable rows={rows} loading={loading} error={error} onRetry={reload} empty="No prescriptions"
        columns={[
          { key: "medication", header: "Medication", render: (p) => (
            <div><span className="font-medium text-slate-800">{p.medication}</span> {p.is_high_alert && <Badge tone="danger">High-alert</Badge>}
              <div className="text-xs text-slate-500">{titleCase(p.drug_class)} · {p.route}</div></div>) },
          { key: "dose", header: "Dose", render: (p) => `${p.dosage} · ${p.frequency}` },
          { key: "dates", header: "Period", render: (p) => <span className="text-xs">{fmtDate(p.start_date)} → {p.end_date ? fmtDate(p.end_date) : "ongoing"}</span> },
          { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
          { key: "reason", header: "Change reason", render: (p) => <span className="text-xs text-slate-500">{p.change_reason ?? "—"}</span> },
          { key: "by", header: "Prescriber", render: (p) => <span className="text-xs">{p.doctor_name}</span> },
          { key: "act", header: "", render: (p) => can(PERMS.prescribe) && p.status === "active" ? (
            <button onClick={() => discontinue(p)} className="flex items-center gap-1 text-xs text-rose-600 hover:underline"><XCircle className="h-3.5 w-3.5" /> Stop</button>) : null },
        ]} />
      {prescribing && <PrescribeModal patientId={patientId} onClose={() => setPrescribing(false)} onDone={() => { setPrescribing(false); reload(); }} />}
    </Card>
  );
}

function PrescribeModal({ patientId, onClose, onDone }: { patientId: number; onClose: () => void; onDone: () => void }) {
  const { data: meds } = useApi<Medication[]>("/medications");
  const [form, setForm] = useState({ medication_id: "", dosage: "", frequency: "once daily", start_date: new Date().toISOString().slice(0, 10), duration_days: "", instructions: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const med = meds?.find((m) => String(m.id) === form.medication_id);
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/prescriptions", { method: "POST", json: {
        patient_id: patientId, medication_id: Number(form.medication_id), dosage: form.dosage, frequency: form.frequency,
        start_date: form.start_date, duration_days: form.duration_days ? Number(form.duration_days) : null, instructions: form.instructions || null } });
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="New prescription"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!form.medication_id || !form.dosage}>Prescribe</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Medication" className="sm:col-span-2">
          <Select value={form.medication_id} onChange={(e) => setForm({ ...form, medication_id: e.target.value })} placeholder="Select from formulary"
            options={(meds ?? []).map((m) => ({ value: m.id, label: `${m.name} (${titleCase(m.drug_class)})${m.is_high_alert ? " — HIGH-ALERT" : ""}` }))} />
        </Field>
        <Field label="Dose"><Input value={form.dosage} onChange={(e) => setForm({ ...form, dosage: e.target.value })} placeholder="e.g. 500 mg" /></Field>
        <Field label="Frequency"><Input value={form.frequency} onChange={(e) => setForm({ ...form, frequency: e.target.value })} /></Field>
        <Field label="Start date"><Input type="date" value={form.start_date} onChange={(e) => setForm({ ...form, start_date: e.target.value })} /></Field>
        <Field label="Duration (days)" hint="Leave empty for ongoing"><Input type="number" min={1} value={form.duration_days} onChange={(e) => setForm({ ...form, duration_days: e.target.value })} /></Field>
        <Field label="Instructions" className="sm:col-span-2"><Textarea value={form.instructions} onChange={(e) => setForm({ ...form, instructions: e.target.value })} /></Field>
      </div>
      {med?.is_high_alert && <p className="mt-2 rounded bg-rose-50 px-2 py-1 text-xs text-rose-700">High-alert medication: an independent double check is required (MED-POL-004).</p>}
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}

export function LabsTab({ patientId }: { patientId: number }) {
  const { data, error, loading, reload } = useApi<LabReport[]>(`/patients/${patientId}/labs?limit=1000`);
  const tests = useMemo(() => {
    const m = new Map<string, LabReport[]>();
    for (const l of data ?? []) m.set(l.test_code, [...(m.get(l.test_code) ?? []), l]);
    return m;
  }, [data]);
  const [code, setCode] = useState<string | null>(null);
  const selected = code ?? (tests.has("HBA1C") ? "HBA1C" : tests.keys().next().value ?? null);
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={8} />;
  if (!tests.size || !selected) return <EmptyState title="No laboratory results" />;
  const series = [...(tests.get(selected) ?? [])].filter((l) => l.value !== null).reverse();
  const first = series[0];
  const refLines = [
    first?.reference_low != null ? { y: first.reference_low, label: `low ${first.reference_low}`, color: "#0284c7" } : null,
    first?.reference_high != null ? { y: first.reference_high, label: `high ${first.reference_high}`, color: "#e11d48" } : null,
  ].filter(Boolean) as { y: number; label: string; color: string }[];
  return (
    <div className="grid gap-4 xl:grid-cols-[220px_1fr]">
      <Card bodyClassName="p-1.5" title="Tests">
        <ul>
          {[...tests.entries()].map(([c, rows]) => {
            const latest = rows[0];
            return (
              <li key={c}>
                <button onClick={() => setCode(c)} className={cn("flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm", c === selected ? "bg-brand-50 text-brand-900" : "hover:bg-slate-50")}>
                  <span className="truncate">{latest.test_name}</span>
                  <span className={cn("ml-2 font-mono text-xs", latest.flag === "critical" ? "text-rose-600" : latest.flag !== "normal" ? "text-amber-600" : "text-slate-500")}>{latest.value ?? latest.value_text}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>
      <div className="space-y-4">
        <Card title={`${first?.test_name ?? selected} trend`} subtitle={`${series.length} results · ${first?.unit ?? ""}`}>
          <LineChart series={[{ name: selected, color: "#0d8170", points: series.map((l) => [new Date(l.collected_at).getTime(), l.value as number]) }]}
            refLines={refLines} xFormat={(v) => new Date(v).toISOString().slice(2, 7)} yFormat={(v) => v.toFixed(v < 10 ? 1 : 0)} />
        </Card>
        <Card bodyClassName="p-0" title="Results">
          <DataTable dense rows={[...(tests.get(selected) ?? [])]}
            columns={[
              { key: "at", header: "Collected", render: (l) => fmtDateTime(l.collected_at) },
              { key: "value", header: "Value", render: (l) => <span className="font-mono">{l.value ?? l.value_text} {l.unit}</span> },
              { key: "range", header: "Reference", render: (l) => <span className="text-xs text-slate-500">{l.reference_low ?? ""}–{l.reference_high ?? ""}</span> },
              { key: "flag", header: "Flag", render: (l) => <StatusBadge status={l.flag} /> },
              { key: "ctx", header: "Context", render: (l) => <span className="text-xs text-slate-500">{l.admission_id ? `Inpatient #${l.admission_id}` : "Outpatient"}</span> },
            ]} />
        </Card>
      </div>
    </div>
  );
}

export function AppointmentsTab({ patientId }: { patientId: number }) {
  const { data, error, loading, reload } = useApi<Appointment[]>(`/patients/${patientId}/appointments`);
  return (
    <Card bodyClassName="p-0" title="Appointments">
      <DataTable rows={data} loading={loading} error={error} onRetry={reload} empty="No appointments"
        columns={[
          { key: "when", header: "When", render: (a) => fmtDateTime(a.scheduled_start) },
          { key: "doctor", header: "Clinician", render: (a) => a.doctor_name },
          { key: "type", header: "Type", render: (a) => titleCase(a.appointment_type) },
          { key: "reason", header: "Reason", render: (a) => a.reason },
          { key: "status", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
        ]} />
    </Card>
  );
}
