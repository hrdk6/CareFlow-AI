"use client";

import { ArrowRight, Images, ScanLine, ShieldCheck, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { PRIORITY } from "@/components/imaging/findings";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { api } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { ImagingStudy } from "@/lib/types";

function UploadStudy({ patientId, onClose, onDone }: {
  patientId: number; onClose: () => void; onDone: (message: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [indication, setIndication] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const send = async () => {
    const file = input.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (indication.trim()) form.append("indication", indication.trim());
      const result = await api<{ message: string }>(`/patients/${patientId}/imaging`, { method: "POST", body: form });
      onDone(result.message);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onClose} title="Add a DICOM study"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button onClick={send} disabled={busy}>
            <Upload className="h-3.5 w-3.5" aria-hidden /> {busy ? "Ingesting…" : "Ingest"}
          </Button>
        </>
      }>
      <div className="space-y-3">
        <Notice tone="info" icon={<ShieldCheck className="h-3.5 w-3.5 shrink-0" />}>
          The file is de-identified before it is written to disk: patient name, record number, accession,
          referrer, institution and device tags are removed or emptied, private tags are dropped, dates are
          shifted and new study identifiers are minted. The link to this patient lives in the database.
        </Notice>
        <Field label="DICOM file" hint="A single-frame image (.dcm)">
          <input ref={input} type="file" accept=".dcm,application/dicom"
            className="block w-full text-[13px] text-ink-2 file:mr-3 file:rounded-lg file:border-0 file:bg-raised file:px-3 file:py-1.5 file:text-[13px] file:font-medium file:text-ink" />
        </Field>
        <Field label="Indication" hint="Why the film was requested (optional)">
          <Input value={indication} onChange={(e) => setIndication(e.target.value)} maxLength={256}
            placeholder="Cough and fever" />
        </Field>
        {error ? <ErrorState error={error} compact /> : null}
      </div>
    </Modal>
  );
}

export function ImagingTab({ patientId }: { patientId: number }) {
  const { can } = useAuth();
  const { data, error, loading, reload } = useApi<ImagingStudy[]>(`/patients/${patientId}/imaging`);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const addButton = can(PERMS.clinicalWrite)
    ? <Button size="sm" onClick={() => setUploading(true)}><Upload className="h-3.5 w-3.5" aria-hidden /> Add study</Button>
    : null;
  const modal = uploading ? (
    <UploadStudy patientId={patientId} onClose={() => setUploading(false)}
      onDone={(text) => { setUploading(false); setMessage(text); reload(); }} />
  ) : null;

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !data) return <Skeleton lines={6} />;

  return (
    <Card bodyClassName="p-0" title="Imaging"
      subtitle={data?.length ? `${data.length} stud${data.length === 1 ? "y" : "ies"}, newest first` : undefined}
      actions={addButton}>
      {modal}
      {message && <div className="px-5 pt-4"><Notice tone="success">{message}</Notice></div>}
      {!data?.length ? (
        <EmptyState title="No imaging" icon={<Images className="h-5 w-5" />}
          message="Studies appear here once a DICOM file has been ingested for this patient." />
      ) : (
        <ul className="divide-y divide-line">
          {data.map((study) => {
            const band = study.triage ? PRIORITY[study.triage.priority] : null;
            return (
              <li key={study.id}>
                <Link href={`/imaging/${study.id}`}
                  className="group flex flex-wrap items-center gap-x-3 gap-y-1.5 px-5 py-3 transition-colors hover:bg-sunken">
                  <span className="w-24 shrink-0 text-xs tabular-nums text-muted">{fmtDate(study.acquired_at)}</span>
                  <ScanLine className="h-4 w-4 shrink-0 text-faint" aria-hidden />
                  <span className="text-sm font-medium text-ink">{study.description ?? study.modality}</span>
                  <span className="font-mono text-[11px] text-faint">{study.accession}</span>
                  {study.indication && <span className="min-w-0 flex-1 truncate text-[13px] text-muted">{study.indication}</span>}
                  <span className="ml-auto flex items-center gap-2">
                    {band && (
                      <Badge tone={band.tone}>
                        {Math.round((study.triage?.priority_score ?? 0) * 100)}% · {band.label}
                      </Badge>
                    )}
                    {study.report?.status === "final" ? <Badge tone="success">Reported</Badge>
                      : study.report ? <Badge tone="warning">Draft</Badge>
                        : <Badge tone="neutral">Unread</Badge>}
                    <ArrowRight className={cn("h-4 w-4 text-faint transition-transform duration-200",
                      "group-hover:translate-x-0.5 group-hover:text-accent")} aria-hidden />
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
