"use client";

import { CalendarPlus, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { DataTable } from "@/components/ui/table";
import { api, errorMessage, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Appointment, Doctor, Page, PatientListItem, Slot } from "@/lib/types";

const iso = (d: Date) => d.toISOString().slice(0, 10);
const addDays = (d: string, n: number) => iso(new Date(new Date(`${d}T00:00:00Z`).getTime() + n * 86400000));

function AppointmentsView() {
  const params = useSearchParams();
  const { can } = useAuth();
  const [day, setDay] = useState(iso(new Date()));
  const [doctor, setDoctor] = useState("");
  const [booking, setBooking] = useState(!!params.get("patient"));
  const [actionError, setActionError] = useState<string | null>(null);
  const { data: doctors } = useApi<Doctor[]>("/doctors");
  const { data, error, loading, reload } = useApi<Page<Appointment>>(
    `/appointments${qs({ date_from: `${day}T00:00:00Z`, date_to: `${addDays(day, 1)}T00:00:00Z`, doctor_id: doctor, limit: 200 })}`);

  async function act(a: Appointment, status: "checked_in" | "completed" | "no_show" | "cancel") {
    setActionError(null);
    try {
      if (status === "cancel") {
        const reason = window.prompt("Cancellation reason?");
        if (!reason) return;
        await api(`/appointments/${a.id}/cancel`, { method: "POST", json: { reason } });
      } else {
        await api(`/appointments/${a.id}`, { method: "PATCH", json: { status } });
      }
      reload();
    } catch (e) {
      setActionError(errorMessage(e));
    }
  }

  return (
    <>
      <PageHeader title="Appointments" subtitle="Daily schedule across the clinicians and patients you can access."
        actions={can(PERMS.appointmentsWrite) && <Button onClick={() => setBooking(true)}><CalendarPlus className="h-4 w-4" /> Book appointment</Button>} />
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
          <Button size="sm" variant="secondary" onClick={() => setDay(addDays(day, -1))} aria-label="Previous day"><ChevronLeft className="h-4 w-4" /></Button>
          <Input type="date" value={day} onChange={(e) => setDay(e.target.value)} className="w-40" aria-label="Day" />
          <Button size="sm" variant="secondary" onClick={() => setDay(addDays(day, 1))} aria-label="Next day"><ChevronRight className="h-4 w-4" /></Button>
          <Button size="sm" variant="ghost" onClick={() => setDay(iso(new Date()))}>Today</Button>
          <Select value={doctor} onChange={(e) => setDoctor(e.target.value)} placeholder="All clinicians" className="ml-auto max-w-[240px]" aria-label="Clinician"
            options={(doctors ?? []).map((d) => ({ value: d.id, label: `${d.full_name} · ${d.specialty}` }))} />
        </div>
        {actionError && <div className="p-3"><ErrorState error={new Error(actionError)} compact /></div>}
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} empty="No appointments on this day"
          columns={[
            { key: "time", header: "Time", render: (a) => <span className="font-mono tabular-nums">{fmtTime(a.scheduled_start)}</span> },
            { key: "patient", header: "Patient", render: (a) => <Link href={`/patients/${a.patient_id}`} className="font-medium text-ink hover:text-accent">{a.patient_name} <span className="font-mono text-xs font-normal text-faint">{a.patient_mrn}</span></Link> },
            { key: "doctor", header: "Clinician", render: (a) => a.doctor_name },
            { key: "type", header: "Type", render: (a) => titleCase(a.appointment_type) },
            { key: "reason", header: "Reason", render: (a) => <span className="text-xs">{a.reason}</span> },
            { key: "status", header: "Status", render: (a) => <StatusBadge status={a.status} /> },
            { key: "act", header: "", render: (a) => can(PERMS.appointmentsWrite) && ["scheduled", "checked_in"].includes(a.status) ? (
              <div className="flex gap-2 text-xs">
                {a.status === "scheduled" && <button className="text-accent hover:underline" onClick={() => act(a, "checked_in")}>Check in</button>}
                {a.status === "checked_in" && <button className="text-accent hover:underline" onClick={() => act(a, "completed")}>Complete</button>}
                <button className="text-high hover:underline" onClick={() => act(a, "cancel")}>Cancel</button>
              </div>) : null },
          ]} />
      </Card>
      {booking && <BookModal initialPatient={params.get("patient")} doctors={doctors ?? []} onClose={() => setBooking(false)}
        onBooked={(d) => { setBooking(false); setDay(d); reload(); }} />}
    </>
  );
}

function BookModal({ initialPatient, doctors, onClose, onBooked }: {
  initialPatient: string | null; doctors: Doctor[]; onClose: () => void; onBooked: (day: string) => void;
}) {
  const [patientId, setPatientId] = useState(initialPatient ?? "");
  const [doctorId, setDoctorId] = useState("");
  const [day, setDay] = useState(addDays(iso(new Date()), 1));
  const [slot, setSlot] = useState<string | null>(null);
  const [type, setType] = useState("follow_up");
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const { data: patients } = useApi<Page<PatientListItem>>("/patients?limit=200");
  const { data: slots, loading } = useApi<Slot[]>(doctorId ? `/doctors/${doctorId}/availability?day=${day}` : null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      await api("/appointments", { method: "POST", json: {
        patient_id: Number(patientId), doctor_id: Number(doctorId), scheduled_start: slot, appointment_type: type, reason, duration_minutes: 30 } });
      onBooked(day);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Book appointment" wide
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!patientId || !slot || reason.length < 3}>Book</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Patient"><Select value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="Select patient"
          options={(patients?.items ?? []).map((p) => ({ value: p.id, label: `${p.full_name} (${p.mrn})` }))} /></Field>
        <Field label="Clinician"><Select value={doctorId} onChange={(e) => { setDoctorId(e.target.value); setSlot(null); }} placeholder="Select clinician"
          options={doctors.map((d) => ({ value: d.id, label: `${d.full_name} · ${d.specialty}` }))} /></Field>
        <Field label="Date"><Input type="date" value={day} min={iso(new Date())} onChange={(e) => { setDay(e.target.value); setSlot(null); }} /></Field>
        <Field label="Type"><Select value={type} onChange={(e) => setType(e.target.value)} options={["outpatient", "follow_up", "telehealth"].map((t) => ({ value: t, label: titleCase(t) }))} /></Field>
      </div>
      <div className="mt-3">
        <div className="mb-1 text-xs font-medium text-ink-2">Available 30-minute slots (UTC)</div>
        {!doctorId ? <p className="text-xs text-faint">Choose a clinician to see availability.</p> : loading ? <p className="text-xs text-faint">Loading…</p> :
          slots?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {slots.map((s) => (
                <button key={s.start} onClick={() => setSlot(s.start)}
                  className={cn("rounded border px-2 py-1 font-mono text-xs", slot === s.start ? "border-accent bg-accent text-ink" : "border-line-strong hover:border-accent")}>
                  {fmtTime(s.start)}
                </button>
              ))}
            </div>) : <p className="text-xs text-muted">No free slots on this day.</p>}
      </div>
      <Field label="Reason" className="mt-3"><Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Post-discharge diabetes follow-up" /></Field>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}

export default function AppointmentsPage() {
  return <Suspense fallback={null}><AppointmentsView /></Suspense>;
}
