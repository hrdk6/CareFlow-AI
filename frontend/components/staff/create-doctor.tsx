"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { api } from "@/lib/api";
import type { Department, Doctor } from "@/lib/types";

/** Registering a clinician is administration, not clinical work: only users:manage may do it.
 *  The login account is separate - created in Administration and linked to this profile. */
export function CreateDoctor({ departments, onClose, onDone }: {
  departments: Department[]; onClose: () => void; onDone: (doctor: Doctor) => void;
}) {
  const [form, setForm] = useState({ full_name: "", specialty: "", department_id: "", email: "", phone: "" });
  const [error, setError] = useState<unknown>(null);
  const [saving, setSaving] = useState(false);
  async function submit() {
    setError(null);
    setSaving(true);
    try {
      const created = await api<Doctor>("/doctors", { method: "POST", json: { ...form, department_id: Number(form.department_id), email: form.email || null } });
      onDone(created);
    } catch (e) {
      setError(e);
    } finally {
      setSaving(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Register clinician"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={saving} disabled={!form.full_name || !form.specialty || !form.department_id}>Create</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name"><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Dr. Meera Joshi" /></Field>
        <Field label="Specialty"><Input value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} placeholder="Neurology" /></Field>
        <Field label="Department"><Select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}
          placeholder="Select department" options={departments.map((d) => ({ value: d.id, label: d.name }))} /></Field>
        <Field label="Phone" hint="Optional"><Input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+91 20 4000 0123" /></Field>
        <Field label="Email" hint="Optional — generated from the staff code if left empty" className="sm:col-span-2">
          <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
      </div>
      <p className="mt-3 text-xs text-muted">A staff code and the standard weekday availability are assigned automatically. The clinician&apos;s department decides which patients their login can see.</p>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}
