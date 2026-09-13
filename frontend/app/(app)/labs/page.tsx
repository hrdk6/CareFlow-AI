"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { StatusBadge } from "@/components/ui/badge";
import { Card, PageHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { DataTable, Pagination } from "@/components/ui/table";
import { qs } from "@/lib/api";
import { fmtDateTime } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { LabReport, Page } from "@/lib/types";

const LIMIT = 30;

export default function LabsPage() {
  const router = useRouter();
  const [flag, setFlag] = useState("critical");
  const [test, setTest] = useState("");
  const [offset, setOffset] = useState(0);
  const { data: catalog } = useApi<{ code: string; name: string }[]>("/labs/catalog");
  const { data, error, loading, reload } = useApi<Page<LabReport>>(`/labs${qs({ flag, test_code: test, limit: LIMIT, offset })}`);
  return (
    <>
      <PageHeader title="Laboratory reports" subtitle="Lab results with their normal ranges. Critical values are highlighted." />
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap gap-2 border-b border-line p-3">
          <Select value={flag} onChange={(e) => { setFlag(e.target.value); setOffset(0); }} placeholder="Any flag" className="max-w-[160px]" aria-label="Flag"
            options={["critical", "high", "low", "normal"].map((f) => ({ value: f, label: f }))} />
          <Select value={test} onChange={(e) => { setTest(e.target.value); setOffset(0); }} placeholder="All tests" className="max-w-[240px]" aria-label="Test"
            options={(catalog ?? []).map((t) => ({ value: t.code, label: `${t.name} (${t.code})` }))} />
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} onRowClick={(l) => router.push(`/patients/${l.patient_id}`)}
          columns={[
            { key: "at", header: "Collected", render: (l) => fmtDateTime(l.collected_at) },
            { key: "mrn", header: "Patient", render: (l) => <span className="font-mono text-xs">{l.patient_mrn}</span> },
            { key: "test", header: "Test", render: (l) => l.test_name },
            { key: "value", header: "Value", render: (l) => <span className="font-mono">{l.value ?? l.value_text} {l.unit}</span> },
            { key: "ref", header: "Reference", render: (l) => <span className="text-xs text-muted">{l.reference_low ?? ""}–{l.reference_high ?? ""}</span> },
            { key: "flag", header: "Flag", render: (l) => <StatusBadge status={l.flag} /> },
            { key: "ctx", header: "Setting", render: (l) => <span className="text-xs text-muted">{l.admission_id ? "Inpatient" : "Outpatient"}</span> },
          ]} />
        {data && <Pagination total={data.total} limit={LIMIT} offset={offset} onChange={setOffset} />}
      </Card>
    </>
  );
}
