"use client";

import { useState } from "react";

import { UserPlus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { useApi, useDebounced } from "@/lib/hooks";
import { api, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import type { Department, Doctor } from "@/lib/types";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function DoctorsPage() {
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("");
  const [creating, setCreating] = useState(false);
  const term = useDebounced(q, 250);
  const { data, error, loading, reload } = useApi<Doctor[]>(`/doctors${qs({ q: term, department_id: dept })}`);
  const { data: departments } = useApi<Department[]>("/departments");
  return (
    <>
      <PageHeader title="Doctors" subtitle="Clinician directory and weekly availability templates (hospital time, UTC)."
        actions={can(PERMS.users) ? <Button size="sm" onClick={() => setCreating(true)}><UserPlus className="h-3.5 w-3.5" /> New doctor</Button> : null} />
      {creating && <CreateDoctor departments={departments ?? []} onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload(); }} />}
      <div className="mb-4 flex flex-wrap gap-2">
        <Input placeholder="Search name or specialty" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" aria-label="Search doctors" />
        <Select value={dept} onChange={(e) => setDept(e.target.value)} placeholder="All departments" className="max-w-[220px]" aria-label="Department"
          options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} />
      </div>
      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && <Skeleton lines={6} />}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {data?.map((d) => (
          <Card key={d.id}>
            <div className="flex items-start justify-between">
              <div>
                <div className="font-medium text-slate-900">{d.full_name}</div>
                <div className="text-xs text-slate-500">{d.specialty} · {d.department}</div>
              </div>
              <span className="font-mono text-xs text-slate-400">{d.staff_code}</span>
            </div>
            <div className="mt-3 grid grid-cols-7 gap-1 text-center text-[10px]">
              {DAYS.map((day) => {
                const slots = d.availability[day] ?? [];
                return (
                  <div key={day} className={slots.length ? "rounded bg-brand-50 p-1 text-brand-800" : "rounded bg-slate-50 p-1 text-slate-400"}>
                    <div className="font-semibold uppercase">{day}</div>
                    {slots.length ? slots.map(([s, e]) => <div key={s}>{s}–{e}</div>) : <div>—</div>}
                  </div>
                );
              })}
            </div>
            <div className="mt-3 text-xs text-slate-500">{d.email} · {d.phone}</div>
          </Card>
        ))}
      </div>
    </>
  );
}

/** Registering a clinician is administration, not clinical work: only users:manage may do it.
 *  The login account is created separately in Administration and linked to this profile. */
function CreateDoctor({ departments, onClose, onDone }: { departments: Department[]; onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState({ full_name: "", specialty: "", department_id: "", email: "", phone: "" });
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  async function submit() {
    setError(null);
    setSaving(true);
    try {
      await api("/doctors", { method: "POST", json: { ...form, department_id: Number(form.department_id) } });
      onDone();
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Register doctor"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} disabled={saving || !form.full_name || !form.specialty || !form.department_id}>Create</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name"><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Dr. Meera Joshi" /></Field>
        <Field label="Specialty"><Input value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} placeholder="Neurology" /></Field>
        <Field label="Department"><Select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}
          placeholder="Select department" options={departments.map((d) => ({ value: d.id, label: d.name }))} /></Field>
        <Field label="Phone" hint="Optional"><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 20 4000 0123" /></Field>
        <Field label="Email" hint="Optional — generated from the staff code if left empty" className="sm:col-span-2">
          <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      </div>
      <p className="mt-3 text-xs text-slate-500">A staff code and the standard weekday availability are assigned automatically. Create the login account in Administration &rarr; Users.</p>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}
