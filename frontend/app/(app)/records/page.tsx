"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, PageHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { DataTable, Pagination } from "@/components/ui/table";
import { qs } from "@/lib/api";
import { fmtDate, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { MedicalRecord, Page } from "@/lib/types";

const LIMIT = 30;

export default function RecordsPage() {
  const router = useRouter();
  const [type, setType] = useState("");
  const [offset, setOffset] = useState(0);
  const { data, error, loading, reload } = useApi<Page<MedicalRecord>>(`/records${qs({ record_type: type, limit: LIMIT, offset })}`);
  return (
    <>
      <PageHeader title="Medical records" subtitle="Visit notes, diagnoses and treatment plans." />
      <Card bodyClassName="p-0">
        <div className="border-b border-line p-3">
          <Select value={type} onChange={(e) => { setType(e.target.value); setOffset(0); }} placeholder="All record types" className="max-w-[220px]" aria-label="Record type"
            options={["consultation", "follow_up", "progress_note", "emergency", "discharge_summary"].map((t) => ({ value: t, label: titleCase(t) }))} />
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} onRowClick={(r) => router.push(`/patients/${r.patient_id}`)}
          columns={[
            { key: "date", header: "Date", render: (r) => fmtDate(r.visit_date) },
            { key: "mrn", header: "Patient", render: (r) => <span className="font-mono text-xs">{r.patient_mrn}</span> },
            { key: "type", header: "Type", render: (r) => <Badge tone={r.record_type === "emergency" ? "danger" : "neutral"}>{titleCase(r.record_type)}</Badge> },
            { key: "cc", header: "Chief complaint", render: (r) => <span className="text-ink">{r.chief_complaint}</span> },
            { key: "plan", header: "Plan", render: (r) => <span className="line-clamp-2 text-xs text-muted">{r.treatment_plan}</span> },
            { key: "by", header: "Clinician", render: (r) => <span className="text-xs">{r.doctor_name ?? "—"}</span> },
          ]} />
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
    </>
  );
}
