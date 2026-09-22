"use client";

import { AlertTriangle, BedDouble, FileSignature, Plus, UserMinus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardLink } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { api } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { AdminUser, Department, Doctor, PatientClinical } from "@/lib/types";

import { LosCard, RiskCard } from "./predictions";
import { TimelineList } from "./timeline";

const DISPOSITIONS = ["home", "home_health", "skilled_nursing", "rehab", "transfer", "ama", "expired"];

function dayOfStay(admittedAt: string): number {
  return Math.max(1, Math.floor((Date.now() - new Date(admittedAt).getTime()) / 86_400_000) + 1);
}

export function OverviewTab({ patient, clinical, onOpen, onChanged }: { patient: PatientClinical; clinical: boolean; onOpen: (tab: string) => void; onChanged: () => void }) {
  const { can } = useAuth();
  const [admitting, setAdmitting] = useState(false);
  const [discharging, setDischarging] = useState(false);
  const [careTeam, setCareTeam] = useState(false);
  if (!clinical) {
    return (
      <Card title="Registration details">
        <p className="text-sm text-ink-2">Your role can view registration and scheduling information only. Clinical data, predictions and the patient-level AI summary are not available to you.</p>
      </Card>
    );
  }
  const adm = patient.current_admission;
  const earlier = patient.admission_count - (adm ? 1 : 0);
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="min-w-0 space-y-4 xl:col-span-2">
        {adm ? (
          <section aria-label="Current admission" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-warn-edge bg-warn-tint px-5 py-3.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-panel text-warn ring-1 ring-inset ring-warn-edge">
              <BedDouble className="h-[18px] w-[18px]" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-ink">
                Admitted to {adm.department}{adm.ward ? ` · Ward ${adm.ward}` : ""} · <span className="tabular">Day {dayOfStay(adm.admitted_at)}</span>
              </p>
              <p className="mt-0.5 text-[13px] text-warn">
                Since {fmtDate(adm.admitted_at)} · {adm.reason}{adm.attending_doctor ? ` · Attending ${adm.attending_doctor}` : ""}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {can(PERMS.admit, PERMS.clinicalWrite) && (
                <Link href={`/patients/${patient.id}/discharge/${adm.id}`} tabIndex={-1}>
                  <Button size="sm"><FileSignature className="h-3.5 w-3.5" aria-hidden /> Prepare discharge</Button>
                </Link>
              )}
              {can(PERMS.admit) && <Button size="sm" variant="secondary" onClick={() => setDischarging(true)}><UserMinus className="h-3.5 w-3.5" /> Discharge</Button>}
            </div>
          </section>
        ) : (
          <section aria-label="Admission" className="flex flex-wrap items-center gap-x-4 gap-y-3 rounded-xl border border-line bg-panel px-5 py-3 shadow-e1">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-raised text-faint">
              <BedDouble className="h-[18px] w-[18px]" aria-hidden />
            </span>
            <p className="min-w-0 flex-1 text-sm text-ink-2">
              Not currently admitted
              <span className="text-muted"> · {earlier === 0 ? "no earlier admissions" : `${earlier} earlier ${earlier === 1 ? "admission" : "admissions"}`}</span>
            </p>
            {can(PERMS.admit) && <Button size="sm" variant="secondary" onClick={() => setAdmitting(true)}><Plus className="h-3.5 w-3.5" /> Admit</Button>}
          </section>
        )}
        {admitting && <AdmitModal patientId={patient.id} onClose={() => setAdmitting(false)} onDone={() => { setAdmitting(false); onChanged(); }} />}
        {discharging && adm && <DischargeModal admissionId={adm.id} onClose={() => setDischarging(false)} onDone={() => { setDischarging(false); onChanged(); }} />}
        {careTeam && <CareTeamModal patientId={patient.id} onClose={() => setCareTeam(false)} onDone={onChanged} />}
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Active problems" subtitle={`${patient.active_diagnoses.length} on the problem list`} bodyClassName="px-5 py-1">
            {patient.active_diagnoses.length === 0 ? <EmptyState title="No active problems" /> : (
              <ul className="divide-y divide-line">
                {patient.active_diagnoses.map((d) => (
                  <li key={d.id} className="flex items-start justify-between gap-3 py-3">
                    <span className="min-w-0">
                      <span className="block text-sm text-ink">{d.description}</span>
                      <span className="block text-[12px] text-muted">Since {d.diagnosed_on.slice(0, 4)}{d.is_chronic ? " · Chronic" : ""}</span>
                    </span>
                    <span className="mt-0.5 shrink-0 rounded-md bg-raised px-1.5 font-mono text-[11px] leading-5 text-ink-2" title="ICD-10 code">{d.icd10_code}</span>
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card title="Current medications" subtitle={`${patient.current_medications.length} active`} bodyClassName="px-5 py-1"
            actions={<CardLink onClick={() => onOpen("prescriptions")}>All</CardLink>}>
            {patient.current_medications.length === 0 ? <EmptyState title="No active prescriptions" /> : (
              <ul className="divide-y divide-line">
                {patient.current_medications.map((m) => (
                  <li key={m.id} className="py-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-ink">{m.medication}</span>
                      {m.is_high_alert && <Badge tone="danger"><AlertTriangle className="h-3 w-3" aria-hidden /> High-alert</Badge>}
                    </div>
                    <div className="text-[12px] text-muted">{m.dosage} · {m.frequency} · {titleCase(m.drug_class)}</div>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
        <Card title="Care team" subtitle="Clinicians assigned to this patient"
          actions={can(PERMS.users) ? <Button size="sm" variant="secondary" onClick={() => setCareTeam(true)}>Manage</Button> : null}>
          {patient.care_team.length === 0 ? <EmptyState title="Nobody is assigned" /> : (
            <ul className="flex flex-wrap gap-2">
              {patient.care_team.map((m) => (
                <li key={m.user_id} className="flex items-center gap-2.5 rounded-full border border-line bg-panel py-1 pl-1 pr-3.5">
                  <Avatar name={m.name} size="sm" />
                  <span className="text-sm text-ink">{m.name}</span>
                  <span className="text-[12px] text-muted">{titleCase(m.care_role)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Recent timeline" subtitle="The last 12 months" actions={<CardLink onClick={() => onOpen("timeline")}>Full timeline</CardLink>}>
          <TimelineList patientId={patient.id} months={12} limit={8} />
        </Card>
      </div>
      {can(PERMS.ml) && (
        // The estimates stay beside the record while its lists scroll.
        <div className="min-w-0 space-y-4 xl:sticky xl:top-[132px] xl:self-start">
          <RiskCard patientId={patient.id} compact />
          <LosCard patientId={patient.id} compact />
        </div>
      )}
    </div>
  );
}

function AdmitModal({ patientId, onClose, onDone }: { patientId: number; onClose: () => void; onDone: () => void }) {
  const { data: departments } = useApi<Department[]>("/departments");
  const { data: doctors } = useApi<Doctor[]>("/doctors");
  const [form, setForm] = useState({ department_id: "", attending_doctor_id: "", admission_type: "elective", admission_source: "physician_referral", reason: "", ward: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  // Only clinicians of the admitting department can be the attending doctor, and retired profiles cannot.
  const attending = (doctors ?? []).filter((d) => d.is_active && (!form.department_id || String(d.department_id) === form.department_id));
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/admissions", { method: "POST", json: {
        patient_id: patientId, department_id: Number(form.department_id),
        attending_doctor_id: Number(form.attending_doctor_id), admission_type: form.admission_type,
        admission_source: form.admission_source, reason: form.reason, ward: form.ward || null } });
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Admit patient"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!form.department_id || !form.attending_doctor_id || form.reason.trim().length < 3}>Admit</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Department"><Select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value, attending_doctor_id: "" })}
          placeholder="Select department" options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} /></Field>
        <Field label="Attending doctor"><Select value={form.attending_doctor_id} onChange={(e) => setForm({ ...form, attending_doctor_id: e.target.value })}
          placeholder="Select clinician" options={attending.map((d) => ({ value: d.id, label: `${d.full_name} · ${d.specialty}` }))} /></Field>
        <Field label="Type"><Select value={form.admission_type} onChange={(e) => setForm({ ...form, admission_type: e.target.value })}
          options={["elective", "urgent", "emergency"].map((t) => ({ value: t, label: titleCase(t) }))} /></Field>
        <Field label="Source"><Select value={form.admission_source} onChange={(e) => setForm({ ...form, admission_source: e.target.value })}
          options={["physician_referral", "emergency_room", "transfer", "clinic"].map((t) => ({ value: t, label: titleCase(t) }))} /></Field>
        <Field label="Reason" className="sm:col-span-2"><Input value={form.reason} onChange={(e) => setForm({ ...form, reason: e.target.value })} placeholder="e.g. Hyperglycaemia with poor control" /></Field>
        <Field label="Ward" hint="Optional"><Input value={form.ward} onChange={(e) => setForm({ ...form, ward: e.target.value })} /></Field>
      </div>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}

function DischargeModal({ admissionId, onClose, onDone }: { admissionId: number; onClose: () => void; onDone: () => void }) {
  const [disposition, setDisposition] = useState("home");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api(`/admissions/${admissionId}/discharge`, { method: "POST", json: { discharge_disposition: disposition } });
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Discharge patient"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy}>Discharge</Button></>}>
      <Field label="Disposition"><Select value={disposition} onChange={(e) => setDisposition(e.target.value)}
        options={DISPOSITIONS.map((d) => ({ value: d, label: titleCase(d) }))} /></Field>
      <p className="mt-3 text-xs text-muted">The discharge is recorded against the current admission and the patient status is updated.</p>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}

interface CareAssignment { id: number; user_id: number; name: string; role: string; care_role: string }

/** Care assignments are how a nurse gets any access at all, so administrators need them in the UI
 *  rather than only through the API. */
function CareTeamModal({ patientId, onClose, onDone }: { patientId: number; onClose: () => void; onDone: () => void }) {
  const { data: assignments, reload } = useApi<CareAssignment[]>(`/admin/care-assignments?patient_id=${patientId}`);
  const { data: users } = useApi<AdminUser[]>("/admin/users");
  const [form, setForm] = useState({ user_id: "", care_role: "nurse" });
  const [error, setError] = useState<unknown>(null);
  const assigned = new Set((assignments ?? []).map((a) => a.user_id));
  const candidates = (users ?? []).filter((u) => u.is_active && (u.role === "NURSE" || u.role === "DOCTOR") && !assigned.has(u.id));
  const selected = candidates.find((u) => String(u.id) === form.user_id);
  const roles = selected?.role === "NURSE" ? ["nurse"] : ["attending", "consulting"];
  async function add() {
    setError(null);
    try {
      await api("/admin/care-assignments", { method: "POST", json: { patient_id: patientId, user_id: Number(form.user_id), care_role: roles.includes(form.care_role) ? form.care_role : roles[0] } });
      setForm({ user_id: "", care_role: "nurse" });
      reload();
      onDone();
    } catch (e) {
      setError(e);
    }
  }
  async function remove(id: number) {
    setError(null);
    try {
      await api(`/admin/care-assignments/${id}`, { method: "DELETE" });
      reload();
      onDone();
    } catch (e) {
      setError(e);
    }
  }
  return (
    <Modal open onClose={onClose} title="Care team" footer={<Button variant="secondary" onClick={onClose}>Close</Button>}>
      <ul className="mb-4 space-y-2">
        {(assignments ?? []).map((a) => (
          <li key={a.id} className="flex items-center justify-between gap-2 rounded border border-line px-2 py-1.5 text-sm">
            <span>{a.name} <span className="text-xs text-muted">· {a.role.toLowerCase()} · {titleCase(a.care_role)}</span></span>
            <button onClick={() => remove(a.id)} className="flex items-center gap-1 text-xs text-high hover:underline"><UserMinus className="h-3.5 w-3.5" /> Remove</button>
          </li>
        ))}
        {assignments?.length === 0 && <li className="text-sm text-muted">Nobody is assigned yet.</li>}
      </ul>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Staff member"><Select value={form.user_id} onChange={(e) => setForm({ ...form, user_id: e.target.value })}
          placeholder="Select clinician" options={candidates.map((u) => ({ value: u.id, label: `${u.full_name} (${u.role.toLowerCase()})` }))} /></Field>
        <Field label="Care role"><Select value={roles.includes(form.care_role) ? form.care_role : roles[0]} onChange={(e) => setForm({ ...form, care_role: e.target.value })}
          options={roles.map((r) => ({ value: r, label: titleCase(r) }))} /></Field>
      </div>
      <div className="mt-3 flex justify-end"><Button size="sm" onClick={add} disabled={!form.user_id}><Plus className="h-3.5 w-3.5" /> Assign</Button></div>
      <p className="mt-3 text-xs text-muted">A nurse can only see patients assigned here; doctors also reach patients through their department and appointments.</p>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}
