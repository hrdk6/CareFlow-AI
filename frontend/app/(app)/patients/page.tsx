"use client";

import { UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { DataTable, Pagination } from "@/components/ui/table";
import { api, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Department, Page, PatientDemographics, PatientListItem } from "@/lib/types";

const LIMIT = 25;

export default function PatientsPage() {
  const router = useRouter();
  const { can } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [offset, setOffset] = useState(0);
  const [registering, setRegistering] = useState(false);
  const term = useDebounced(q.trim(), 300);
  const { data, error, loading, reload } = useApi<Page<PatientListItem>>(
    `/patients${qs({ q: term, status, department_id: department, limit: LIMIT, offset })}`);
  const { data: departments } = useApi<Department[]>("/departments");

  return (
    <>
      <PageHeader title="Patients" subtitle="Only patients within your access policy are listed."
        actions={can(PERMS.patientsWrite) && <Button onClick={() => setRegistering(true)}><UserPlus className="h-4 w-4" /> Register patient</Button>} />
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap gap-2 border-b border-slate-100 p-3">
          <Input placeholder="Search name or MRN" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }} className="max-w-xs" aria-label="Search patients" />
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} placeholder="All statuses" className="max-w-[160px]" aria-label="Status"
            options={["active", "admitted", "discharged", "inactive"].map((s) => ({ value: s, label: s }))} />
          <Select value={department} onChange={(e) => { setDepartment(e.target.value); setOffset(0); }} placeholder="All departments" className="max-w-[200px]" aria-label="Department"
            options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} />
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} empty="No patients match these filters"
          onRowClick={(p) => router.push(`/patients/${p.id}`)}
          columns={[
            { key: "mrn", header: "MRN", render: (p) => <span className="font-mono text-xs text-slate-600">{p.mrn}</span> },
            { key: "full_name", header: "Name", render: (p) => <span className="font-medium text-slate-800">{p.full_name}</span> },
            { key: "age", header: "Age / sex", render: (p) => `${p.age} · ${p.sex}` },
            { key: "dob", header: "Date of birth", render: (p) => fmtDate(p.date_of_birth) },
            { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
            { key: "dept", header: "Department", render: (p) => p.primary_department ?? "—" },
            { key: "phone", header: "Phone", render: (p) => <span className="text-xs text-slate-500">{p.phone ?? "—"}</span> },
          ]} />
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
      <RegisterPatient open={registering} onClose={() => setRegistering(false)} departments={departments ?? []}
        onCreated={(p) => router.push(`/patients/${p.id}`)} />
    </>
  );
}

function RegisterPatient({ open, onClose, departments, onCreated }: {
  open: boolean; onClose: () => void; departments: Department[]; onCreated: (p: PatientDemographics) => void;
}) {
  const [form, setForm] = useState({ first_name: "", last_name: "", date_of_birth: "", sex: "F", phone: "",
    email: "", emergency_contact_name: "", emergency_contact_phone: "", primary_department_id: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const body = Object.fromEntries(Object.entries(form).filter(([, v]) => v !== "")) as Record<string, unknown>;
      if (body.primary_department_id) body.primary_department_id = Number(body.primary_department_id);
      onCreated(await api<PatientDemographics>("/patients", { method: "POST", json: body }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Register patient"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy}>Register</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="First name"><Input value={form.first_name} onChange={set("first_name")} /></Field>
        <Field label="Last name"><Input value={form.last_name} onChange={set("last_name")} /></Field>
        <Field label="Date of birth"><Input type="date" value={form.date_of_birth} onChange={set("date_of_birth")} /></Field>
        <Field label="Sex"><Select value={form.sex} onChange={set("sex")} options={[{ value: "F", label: "Female" }, { value: "M", label: "Male" }, { value: "X", label: "Other / unspecified" }]} /></Field>
        <Field label="Phone"><Input value={form.phone} onChange={set("phone")} placeholder="+1 555 0100" /></Field>
        <Field label="Email"><Input type="email" value={form.email} onChange={set("email")} /></Field>
        <Field label="Emergency contact"><Input value={form.emergency_contact_name} onChange={set("emergency_contact_name")} /></Field>
        <Field label="Emergency contact phone"><Input value={form.emergency_contact_phone} onChange={set("emergency_contact_phone")} /></Field>
        <Field label="Primary department" className="sm:col-span-2">
          <Select value={form.primary_department_id} onChange={set("primary_department_id")} placeholder="None"
            options={departments.map((d) => ({ value: d.id, label: d.name }))} />
        </Field>
      </div>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
      <p className="mt-3 text-[11px] text-slate-500">A new MRN is allocated automatically. Records created in this demo are marked synthetic.</p>
    </Modal>
  );
}
