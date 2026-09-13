"use client";

import { UserPlus } from "lucide-react";
import { useState } from "react";

import { Badge, RouteBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CreateDoctor } from "@/components/staff/create-doctor";
import { Card, PageHeader, StatCard } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { DataTable, Pagination } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { api, errorMessage, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDateTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { AdminUser, AITrace, AuditLog, Department, Doctor, Page } from "@/lib/types";

type Tab = "users" | "roles" | "audit" | "traces" | "metrics";

export default function AdminPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState<Tab>(can(PERMS.users) ? "users" : "audit");
  return (
    <>
      <PageHeader title="Administration" subtitle="Users and roles, audit trail, AI traces and system metrics." />
      <Tabs active={tab} onChange={setTab} tabs={[
        { id: "users", label: "Users", hidden: !can(PERMS.users) }, { id: "roles", label: "Roles & permissions", hidden: !can(PERMS.users) },
        { id: "audit", label: "Audit log", hidden: !can(PERMS.audit) }, { id: "traces", label: "AI traces", hidden: !can(PERMS.observe) },
        { id: "metrics", label: "Metrics", hidden: !can(PERMS.observe) },
      ]} />
      <div className="mt-4">
        {tab === "users" && <Users />}
        {tab === "roles" && <Roles />}
        {tab === "audit" && <Audit />}
        {tab === "traces" && <Traces />}
        {tab === "metrics" && <Metrics />}
      </div>
    </>
  );
}

const ROLES = ["ADMIN", "DOCTOR", "NURSE", "RECEPTIONIST"];

function Users() {
  const { user: me } = useAuth();
  const { data, error, loading, reload } = useApi<AdminUser[]>("/admin/users");
  const [creating, setCreating] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  async function update(u: AdminUser, body: Partial<AdminUser>) {
    setMsg(null);
    try {
      await api(`/admin/users/${u.id}`, { method: "PATCH", json: body });
      reload();
    } catch (e) {
      setMsg(errorMessage(e));
    }
  }
  return (
    <Card bodyClassName="p-0" title="User accounts" subtitle="Role changes are recorded in the audit log" actions={<Button size="sm" onClick={() => setCreating(true)}><UserPlus className="h-3.5 w-3.5" /> New user</Button>}>
      {msg && <div className="p-3"><ErrorState error={new Error(msg)} compact /></div>}
      <DataTable rows={data} loading={loading} error={error} onRetry={reload}
        columns={[
          { key: "name", header: "User", render: (u) => <div><div className="font-medium text-ink">{u.full_name}</div><div className="text-xs text-muted">{u.email}</div></div> },
          { key: "role", header: "Role", render: (u) => (
            <select value={u.role} disabled={u.id === me?.id || u.role === "DOCTOR"}
              title={u.role === "DOCTOR" ? "Change the linked doctor profile first" : undefined} onChange={(e) => update(u, { role: e.target.value as AdminUser["role"] })} className="rounded border border-line-strong px-1.5 py-1 text-xs" aria-label={`Role for ${u.email}`}>
              {ROLES.map((r) => <option key={r}>{r}</option>)}
            </select>) },
          { key: "active", header: "Status", render: (u) => <StatusBadge status={u.is_active ? "active" : "inactive"} /> },
          { key: "login", header: "Last sign-in", render: (u) => <span className="text-xs text-muted">{fmtDateTime(u.last_login_at)}</span> },
          { key: "act", header: "", render: (u) => u.id !== me?.id && (
            <button className="text-xs text-accent hover:underline" onClick={() => update(u, { is_active: !u.is_active })}>{u.is_active ? "Deactivate" : "Activate"}</button>) },
        ]} />
      {creating && <CreateUser onClose={() => setCreating(false)} onDone={() => { setCreating(false); reload(); }} />}
    </Card>
  );
}

function CreateUser({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "NURSE", doctor_id: "" });
  const [error, setError] = useState<unknown>(null);
  const [registering, setRegistering] = useState(false);
  const { data: departments } = useApi<Department[]>("/departments");
  const { data: doctors, reload: reloadDoctors } = useApi<Doctor[]>("/doctors");
  const { data: existing } = useApi<AdminUser[]>("/admin/users");
  // A doctor profile belongs to exactly one login, so profiles already linked are not offered.
  const linked = new Set((existing ?? []).map((u) => u.doctor_id).filter(Boolean));
  const freeDoctors = (doctors ?? []).filter((d) => !linked.has(d.id));
  const profile = freeDoctors.find((d) => String(d.id) === form.doctor_id);
  async function submit() {
    setError(null);
    try {
      await api("/admin/users", { method: "POST", json: {
        email: form.email, full_name: form.full_name, password: form.password, role: form.role,
        doctor_id: form.doctor_id ? Number(form.doctor_id) : null } });
      onDone();
    } catch (e) {
      setError(e);
    }
  }
  return (
    <Modal open onClose={onClose} title="Create user" footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit}>Create</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name"><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
        <Field label="Email"><Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
        <Field label="Initial password" hint="≥ 12 characters"><Input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <Field label="Role"><Select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })} options={ROLES.map((r) => ({ value: r, label: r }))} /></Field>
        {form.role === "DOCTOR" && (
          <>
            <Field label="Doctor profile" hint="The clinician this login signs in as — appointments and records are recorded under it">
              <div className="flex gap-2">
                <Select className="min-w-0 flex-1" value={form.doctor_id} onChange={(e) => setForm({ ...form, doctor_id: e.target.value })}
                  placeholder={freeDoctors.length ? "Select clinician" : "No unlinked profiles"}
                  options={freeDoctors.map((d) => ({ value: d.id, label: `${d.full_name} · ${d.department}` }))} />
                <Button size="sm" variant="secondary" onClick={() => setRegistering(true)}>New</Button>
              </div>
            </Field>
            <Field label="Department" hint="Taken from the doctor profile — it decides which patients this login can see">
              <div className="flex h-9 items-center rounded border border-line bg-sunken px-2 text-sm text-ink-2">
                {profile ? profile.department : "Select a clinician first"}
              </div>
            </Field>
          </>
        )}
      </div>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
      {registering && (
        <CreateDoctor departments={departments ?? []} onClose={() => setRegistering(false)}
          onDone={(doctor) => { setRegistering(false); reloadDoctors(); setForm({ ...form, doctor_id: String(doctor.id) }); }} />
      )}
    </Modal>
  );
}

function Roles() {
  const { data } = useApi<{ name: string; description: string; permissions: string[] }[]>("/admin/roles");
  const { data: perms } = useApi<{ code: string; description: string }[]>("/admin/permissions");
  if (!data || !perms) return <Skeleton lines={8} />;
  return (
    <Card bodyClassName="p-0" title="Permission matrix" subtitle="Row-level access (which patients) is enforced separately by the access policy">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-[11px] uppercase text-muted"><th className="px-3 py-2">Permission</th>{data.map((r) => <th key={r.name} className="px-3 text-center">{r.name}</th>)}</tr></thead>
          <tbody className="divide-y divide-line">
            {perms.map((p) => (
              <tr key={p.code}><td className="px-3 py-1.5"><div className="font-mono text-xs">{p.code}</div><div className="text-[11px] text-muted">{p.description}</div></td>
                {data.map((r) => <td key={r.name} className="text-center">{r.permissions.includes(p.code) ? <span className="text-accent">●</span> : <span className="text-faint">○</span>}</td>)}</tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function Audit() {
  const [action, setAction] = useState("");
  const [outcome, setOutcome] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Page<AuditLog>>(`/admin/audit-logs${qs({ action, outcome, limit: 50, offset })}`);
  return (
    <Card bodyClassName="p-0" title="Audit trail" subtitle="Identifiers and counts only — no clinical text or query content is stored">
      <div className="flex flex-wrap gap-2 border-b border-line p-3">
        <Input placeholder="Action prefix (e.g. patient., ai., document.)" value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }} className="max-w-xs" aria-label="Action" />
        <Select value={outcome} onChange={(e) => { setOutcome(e.target.value); setOffset(0); }} placeholder="Any outcome" className="max-w-[160px]" aria-label="Outcome"
          options={["success", "denied", "error"].map((o) => ({ value: o, label: o }))} />
      </div>
      <DataTable dense rows={data?.items} loading={loading} error={error} onRetry={reload}
        columns={[
          { key: "at", header: "Time", render: (l) => <span className="whitespace-nowrap text-xs">{fmtDateTime(l.occurred_at)}</span> },
          { key: "user", header: "User", render: (l) => <span className="text-xs">#{l.user_id ?? "—"} {l.user_role && <Badge>{l.user_role}</Badge>}</span> },
          { key: "action", header: "Action", render: (l) => <span className="font-mono text-xs">{l.action}</span> },
          { key: "res", header: "Resource", render: (l) => <span className="text-xs text-muted">{l.resource_type ? `${l.resource_type} #${l.resource_id}` : "—"}{l.patient_id ? ` · patient #${l.patient_id}` : ""}</span> },
          { key: "outcome", header: "Outcome", render: (l) => <StatusBadge status={l.outcome} /> },
          { key: "details", header: "Details", render: (l) => <span className="line-clamp-1 max-w-xs font-mono text-[10px] text-faint" title={JSON.stringify(l.details)}>{JSON.stringify(l.details)}</span> },
        ]} />
      {data && <Pagination total={data.total} limit={50} offset={offset} onChange={setOffset} />}
    </Card>
  );
}

function Traces() {
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Page<AITrace>>(`/admin/ai-traces${qs({ limit: 30, offset })}`);
  return (
    <Card bodyClassName="p-0" title="AI query traces" subtitle="Per-request routing, latency by stage, retrieved/cited source ids, tools and tokens (query text is never stored, only its hash)">
      <DataTable dense rows={data?.items} loading={loading} error={error} onRetry={reload}
        columns={[
          { key: "at", header: "Time", render: (t) => <span className="whitespace-nowrap text-xs">{fmtDateTime(t.created_at)}</span> },
          { key: "route", header: "Route", render: (t) => <div className="flex flex-wrap gap-0.5">{t.route.split(" + ").map((r) => <RouteBadge key={r} route={r} />)}</div> },
          { key: "method", header: "Routing", render: (t) => <span className="text-xs">{t.routing_method}</span> },
          { key: "provider", header: "Provider", render: (t) => <span className="font-mono text-xs">{t.provider}{t.llm_model ? `/${t.llm_model}` : ""}</span> },
          { key: "status", header: "Status", render: (t) => <StatusBadge status={t.status} /> },
          { key: "ms", header: "Total", render: (t) => <span className="tabular-nums">{(t.total_ms / 1000).toFixed(2)}s</span> },
          { key: "stages", header: "Stages (ms)", render: (t) => <span className="font-mono text-[10px] text-muted">{Object.entries(t.stage_ms).map(([k, v]) => `${k}:${Math.round(v)}`).join(" ")}</span> },
          { key: "src", header: "Sources", render: (t) => <span className="text-xs">{t.cited_source_ids.length}/{t.retrieved_chunk_ids.length}</span> },
          { key: "tok", header: "Tokens", render: (t) => <span className="text-xs tabular-nums">{t.prompt_tokens ?? "—"}/{t.completion_tokens ?? "—"}</span> },
        ]} />
      {data && <Pagination total={data.total} limit={30} offset={offset} onChange={setOffset} />}
    </Card>
  );
}

interface MetricsSummary {
  window_hours: number; ai_queries: number; ai_errors_or_degraded: number; latency_ms: Record<string, { n: number; p50?: number; p95?: number; max?: number }>;
  routes: Record<string, number>; routing_methods: Record<string, number>; tokens: { prompt: number; completion: number };
  avg_retrieved_chunks: number; documents: Record<string, number>; denied_events: number;
}

function Metrics() {
  const { data, error, reload } = useApi<MetricsSummary>("/admin/metrics/summary");
  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (!data) return <Skeleton lines={6} />;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label={`AI queries (${data.window_hours / 24} days)`} value={data.ai_queries} hint={`${data.ai_errors_or_degraded} degraded/errored`} />
        <StatCard label="Median AI latency" value={`${((data.latency_ms.total?.p50 ?? 0) / 1000).toFixed(2)}s`} hint={`p95 ${((data.latency_ms.total?.p95 ?? 0) / 1000).toFixed(2)}s`} />
        <StatCard label="LLM tokens" value={(data.tokens.prompt + data.tokens.completion).toLocaleString()} hint={`${data.tokens.prompt.toLocaleString()} prompt`} />
        <StatCard label="Denied access events" value={data.denied_events} hint={`avg ${data.avg_retrieved_chunks} chunks/query`} />
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Latency by stage (ms)" bodyClassName="p-0">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-[11px] uppercase text-muted"><th className="px-3 py-2">Stage</th><th>n</th><th>p50</th><th>p95</th><th>max</th></tr></thead>
            <tbody className="divide-y divide-line">
              {Object.entries(data.latency_ms).map(([k, v]) => <tr key={k}><td className="px-3 py-1.5">{titleCase(k)}</td><td>{v.n}</td><td className="tabular-nums">{v.p50 ?? "—"}</td><td className="tabular-nums">{v.p95 ?? "—"}</td><td className="tabular-nums">{v.max ?? "—"}</td></tr>)}
            </tbody>
          </table>
        </Card>
        <Card title="Routes">
          <ul className="space-y-1 text-sm">{Object.entries(data.routes).map(([r, n]) => <li key={r} className="flex justify-between"><span className="flex flex-wrap gap-0.5">{r.split(" + ").map((x) => <RouteBadge key={x} route={x} />)}</span><span className="tabular-nums text-ink-2">{n}</span></li>)}</ul>
          <div className="mt-3 text-xs text-muted">Routing methods: {Object.entries(data.routing_methods).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>
          <div className="mt-1 text-xs text-muted">Documents: {Object.entries(data.documents).map(([k, v]) => `${k} ${v}`).join(" · ")}</div>
          <p className="mt-3 text-xs text-muted">Prometheus metrics are exposed at <code>/metrics</code> on the API.</p>
        </Card>
      </div>
    </div>
  );
}
