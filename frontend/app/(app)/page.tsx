"use client";

import { AlertOctagon, BedDouble, Bot, CalendarDays, FileText, LogOut as Discharge, Users } from "lucide-react";
import Link from "next/link";

import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, PageHeader, StatCard } from "@/components/ui/card";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate, fmtTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";

interface Dashboard {
  role: string; role_label: string; patients_visible: number;
  appointments_today?: { id: number; time: string; patient: string; patient_id: number; mrn: string; doctor: string; reason: string; status: string }[];
  appointments_today_count?: number; inpatients?: number; discharges_7d?: number; documents_indexed?: number;
  ai_queries_24h?: number; denied_events_24h?: number;
  census?: { patient_id: number; mrn: string; name: string; reason: string; admitted_at: string; department: string; ward: string | null }[];
  recent_discharges?: { patient_id: number; mrn: string; name: string; reason: string; discharged_at: string; disposition: string }[];
}

export default function DashboardPage() {
  const { user, can } = useAuth();
  const { data, error, loading, reload } = useApi<Dashboard>("/dashboard");
  const firstName = user?.full_name.replace(/^Dr\.\s*/, "").split(" ")[0];

  return (
    <>
      <PageHeader eyebrow={data?.role_label} title={`Good day, ${firstName ?? ""}`}
        subtitle="Your workspace summary. Every figure below is limited to the patients and records you are authorized to see."
        actions={can(PERMS.ai) && <Link href="/assistant"><Button><Bot className="h-4 w-4" /> Ask the assistant</Button></Link>} />
      {error && <ErrorState error={error} onRetry={reload} />}
      {loading && !data && <Skeleton lines={4} />}
      {data && (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Patients you can access" value={data.patients_visible} icon={<Users className="h-5 w-5" />} tone="brand" />
            {data.appointments_today_count !== undefined && (
              <StatCard label="Appointments today" value={data.appointments_today_count} icon={<CalendarDays className="h-5 w-5" />} tone="sky" />
            )}
            {data.inpatients !== undefined && (
              <StatCard label="Current inpatients" value={data.inpatients} hint={`${data.discharges_7d} discharged in 7 days`} icon={<BedDouble className="h-5 w-5" />} tone="amber" />
            )}
            {data.ai_queries_24h !== undefined ? (
              <StatCard label="AI queries (24h)" value={data.ai_queries_24h} hint={`${data.denied_events_24h} denied access events`} icon={<AlertOctagon className="h-5 w-5" />} tone="rose" />
            ) : data.documents_indexed !== undefined && (
              <StatCard label="Knowledge base documents" value={data.documents_indexed} icon={<FileText className="h-5 w-5" />} />
            )}
          </div>

          <div className="grid gap-5 xl:grid-cols-3">
            {data.appointments_today && (
              <Card title="Today's appointments" className="xl:col-span-2" bodyClassName="p-0"
                actions={<Link href="/appointments" className="text-xs font-medium text-brand-700 hover:text-brand-800 hover:underline">View schedule</Link>}>
                {data.appointments_today.length === 0 ? <EmptyState title="No appointments today" /> : (
                  <ul className="divide-y divide-line/70">
                    {data.appointments_today.map((a) => (
                      <li key={a.id} className="flex items-center gap-4 px-4 py-2.5 transition-colors hover:bg-slate-50/80">
                        <span className="w-12 font-mono text-sm tabular-nums text-slate-600">{fmtTime(a.time)}</span>
                        <div className="min-w-0 flex-1">
                          <Link href={`/patients/${a.patient_id}`} className="text-sm font-medium text-slate-800 hover:text-brand-700">{a.patient}</Link>
                          <span className="ml-2 font-mono text-xs text-slate-400">{a.mrn}</span>
                          <div className="truncate text-xs text-slate-500">{a.reason} · {a.doctor}</div>
                        </div>
                        <StatusBadge status={a.status} />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}
            {data.recent_discharges && (
              <Card title="Recent discharges (30 days)" bodyClassName="p-0"
                subtitle="Candidates for readmission-risk review">
                {data.recent_discharges.length === 0 ? <EmptyState title="No recent discharges" /> : (
                  <ul className="divide-y divide-line/70">
                    {data.recent_discharges.map((d) => (
                      <li key={`${d.patient_id}-${d.discharged_at}`} className="px-4 py-2.5 transition-colors hover:bg-slate-50/80">
                        <Link href={`/patients/${d.patient_id}`} className="flex items-center gap-2 text-sm font-medium text-slate-800 hover:text-brand-700">
                          <Discharge className="h-3.5 w-3.5 text-slate-400" /> {d.name}
                          <span className="font-mono text-xs font-normal text-slate-400">{d.mrn}</span>
                        </Link>
                        <div className="text-xs text-slate-500">{d.reason} · {fmtDate(d.discharged_at)} · to {titleCase(d.disposition)}</div>
                      </li>
                    ))}
                  </ul>
                )}
              </Card>
            )}
          </div>

          {data.census && (
            <Card title="Inpatient census" bodyClassName="p-0" subtitle="Currently admitted patients within your access">
              {data.census.length === 0 ? <EmptyState title="No current inpatients" /> : (
                <div className="grid divide-y divide-line/70 sm:grid-cols-2 sm:divide-y-0">
                  {data.census.map((c) => (
                    <Link key={c.patient_id} href={`/patients/${c.patient_id}`} className="flex items-center justify-between gap-3 border-line/70 px-4 py-2.5 transition-colors hover:bg-brand-50/40 sm:border-b">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-slate-800">{c.name} <span className="font-mono text-xs font-normal text-slate-400">{c.mrn}</span></div>
                        <div className="truncate text-xs text-slate-500">{c.reason}</div>
                      </div>
                      <div className="shrink-0 text-right text-xs text-slate-500">
                        <div>{c.department}{c.ward ? ` · ${c.ward}` : ""}</div>
                        <div>since {fmtDate(c.admitted_at)}</div>
                      </div>
                    </Link>
                  ))}
                </div>
              )}
            </Card>
          )}
        </div>
      )}
    </>
  );
}
