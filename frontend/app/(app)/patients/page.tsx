"use client";

import { Search, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, PageHeader } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { DataTable, Pagination } from "@/components/ui/table";
import { Segmented } from "@/components/ui/tabs";
import { api, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useApi, useDebounced } from "@/lib/hooks";
import type { Department, Page, PatientDemographics, PatientListItem } from "@/lib/types";

const LIMIT = 25;

const STATUSES = [
  { value: "", label: "All" }, { value: "admitted", label: "Admitted" }, { value: "active", label: "Active" },
  { value: "discharged", label: "Discharged" }, { value: "inactive", label: "Inactive" },
];

const SEX = { F: "Female", M: "Male" } as Record<string, string>;

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
  const filtered = Boolean(term || status || department);

  return (
    <>
      <PageHeader title="Patients" subtitle="Search, filter and open patient records."
        actions={can(PERMS.patientsWrite) && <Button onClick={() => setRegistering(true)}><UserPlus className="h-4 w-4" /> Register patient</Button>} />
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2.5 border-b border-line px-4 py-3">
          <div className="relative w-full sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" aria-hidden />
            <Input type="search" placeholder="Search name or MRN" value={q} onChange={(e) => { setQ(e.target.value); setOffset(0); }}
              className="pl-9" aria-label="Search patients" />
          </div>
          <Segmented label="Status" options={STATUSES} value={status} onChange={(v) => { setStatus(v); setOffset(0); }} />
          <Select value={department} onChange={(e) => { setDepartment(e.target.value); setOffset(0); }} placeholder="All departments" className="w-full sm:w-52" aria-label="Department"
            options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} />
          {data && (
            <p className="tabular text-[13px] text-muted lg:ml-auto" aria-live="polite">
              {data.total} {data.total === 1 ? "patient" : "patients"}{filtered ? " match" : ""}
            </p>
          )}
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload}
          empty={filtered ? "No patients match these filters" : "No patients yet"}
          onRowClick={(p) => router.push(`/patients/${p.id}`)}
          columns={[
            { key: "patient", header: "Patient", className: "pl-5", render: (p) => (
              <span className="flex min-w-[200px] items-center gap-3">
                <Avatar name={p.full_name} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-medium text-ink">{p.full_name}</span>
                  <span className="block text-[12px] text-faint">
                    <span className="font-mono text-[11px]">{p.mrn}</span>
                    <span className="sm:hidden"> · {p.age} {SEX[p.sex] ?? "Other"}</span>
                  </span>
                </span>
              </span>
            ) },
            { key: "age", header: "Age", className: "hidden sm:table-cell", render: (p) => (
              <span className="whitespace-nowrap">{p.age} <span className="text-muted">· {SEX[p.sex] ?? "Other"}</span></span>
            ) },
            { key: "dob", header: "Date of birth", className: "hidden md:table-cell whitespace-nowrap", render: (p) => fmtDate(p.date_of_birth) },
            { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
            { key: "dept", header: "Department", className: "hidden lg:table-cell", render: (p) => p.primary_department ?? <span className="text-faint">None</span> },
            { key: "phone", header: "Phone", className: "hidden xl:table-cell whitespace-nowrap", render: (p) => <span className="text-muted">{p.phone ?? "—"}</span> },
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
        <Field label="Phone"><Input value={form.phone} onChange={set("phone")} placeholder="+91 98765 43210" /></Field>
        <Field label="Email"><Input type="email" value={form.email} onChange={set("email")} /></Field>
        <Field label="Emergency contact"><Input value={form.emergency_contact_name} onChange={set("emergency_contact_name")} /></Field>
        <Field label="Emergency contact phone"><Input value={form.emergency_contact_phone} onChange={set("emergency_contact_phone")} /></Field>
        <Field label="Primary department" className="sm:col-span-2">
          <Select value={form.primary_department_id} onChange={set("primary_department_id")} placeholder="None"
            options={departments.map((d) => ({ value: d.id, label: d.name }))} />
        </Field>
      </div>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
      <p className="mt-3 text-[11px] text-muted">A new MRN is allocated automatically. Records created in this demo are marked synthetic.</p>
    </Modal>
  );
}
