"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge, StatusBadge } from "@/components/ui/badge";
import { Card, PageHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { DataTable, Pagination } from "@/components/ui/table";
import { qs } from "@/lib/api";
import { fmtDate, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Page, Prescription } from "@/lib/types";

const LIMIT = 30;

export default function PrescriptionsPage() {
  const router = useRouter();
  const [status, setStatus] = useState("active");
  const [highAlert, setHighAlert] = useState(false);
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Page<Prescription>>(
    `/prescriptions${qs({ status, high_alert: highAlert ? "true" : undefined, limit: LIMIT, offset })}`);
  return (
    <>
      <PageHeader title="Prescriptions" subtitle="Outpatient medication orders for your accessible patients." />
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
          <Select value={status} onChange={(e) => { setStatus(e.target.value); setOffset(0); }} placeholder="Any status" className="max-w-[180px]" aria-label="Status"
            options={["active", "completed", "discontinued"].map((s) => ({ value: s, label: titleCase(s) }))} />
          <label className="flex items-center gap-1.5 text-xs text-ink-2"><input type="checkbox" checked={highAlert} onChange={(e) => { setHighAlert(e.target.checked); setOffset(0); }} /> High-alert only (MED-POL-004)</label>
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} onRowClick={(p) => router.push(`/patients/${p.patient_id}`)}
          columns={[
            { key: "mrn", header: "Patient", render: (p) => <span className="font-mono text-xs">{p.patient_mrn}</span> },
            { key: "med", header: "Medication", render: (p) => <span className="font-medium text-ink">{p.medication} {p.is_high_alert && <Badge tone="danger">High-alert</Badge>}</span> },
            { key: "dose", header: "Dose", render: (p) => `${p.dosage} · ${p.frequency}` },
            { key: "start", header: "Started", render: (p) => fmtDate(p.start_date) },
            { key: "status", header: "Status", render: (p) => <StatusBadge status={p.status} /> },
            { key: "reason", header: "Change reason", render: (p) => <span className="text-xs text-muted">{p.change_reason ?? "—"}</span> },
          ]} />
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
    </>
  );
}
