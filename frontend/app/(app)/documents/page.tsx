"use client";

import { Download, FileUp, Library, ShieldAlert, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, KeyValue, PageHeader } from "@/components/ui/card";
import { ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { Drawer, Modal } from "@/components/ui/overlay";
import { DataTable } from "@/components/ui/table";
import { api, qs } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { bytes, fmtDateTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Department, DocumentDetail, DocumentItem, Page } from "@/lib/types";

const TYPES = ["guideline", "policy", "protocol", "procedure", "report", "other"];
const SCOPES = [["all_staff", "All staff"], ["clinical", "Clinical staff"], ["admin", "Administrators"]];

export default function DocumentsPage() {
  const { can } = useAuth();
  const manage = can(PERMS.docsManage);
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [q, setQ] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<number | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const { data, error, loading, reload } = useApi<Page<DocumentItem>>(`/documents${qs({ status, doc_type: type, q, limit: 100 })}`);
  const busy = data?.items.some((d) => d.status === "uploading" || d.status === "processing");

  useEffect(() => {  // poll while ingestion is running so statuses update live
    if (!busy) return;
    const id = setInterval(reload, 2000);
    return () => clearInterval(id);
  }, [busy, reload]);

  async function loadDemo() {
    const r = await api<{ message: string }>("/documents/demo-corpus", { method: "POST" });
    setNotice(r.message);
    setTimeout(reload, 1500);
  }

  return (
    <>
      <PageHeader title="Knowledge base" subtitle="Hospital guidelines, policies and reports the assistant can answer from."
        actions={manage && <>
          <Button variant="secondary" onClick={loadDemo}><Library className="h-4 w-4" /> Load demo corpus</Button>
          <Button onClick={() => setUploading(true)}><FileUp className="h-4 w-4" /> Upload</Button>
        </>} />
      {notice && <div className="mb-3"><Notice tone="success">{notice}</Notice></div>}
      <Card bodyClassName="p-0">
        <div className="flex flex-wrap gap-2 border-b border-line p-3">
          <Input placeholder="Search title or code" value={q} onChange={(e) => setQ(e.target.value)} className="max-w-xs" aria-label="Search documents" />
          <Select value={type} onChange={(e) => setType(e.target.value)} placeholder="All types" className="max-w-[160px]" aria-label="Type" options={TYPES.map((t) => ({ value: t, label: titleCase(t) }))} />
          {manage && <Select value={status} onChange={(e) => setStatus(e.target.value)} placeholder="Any status" className="max-w-[160px]" aria-label="Status"
            options={["uploading", "processing", "indexed", "failed"].map((s) => ({ value: s, label: titleCase(s) }))} />}
        </div>
        <DataTable rows={data?.items} loading={loading} error={error} onRetry={reload} onRowClick={(d) => setSelected(d.id)} empty="No documents yet"
          columns={[
            { key: "title", header: "Document", render: (d) => (
              <div><div className="font-medium text-ink">{d.title}</div><div className="font-mono text-[11px] text-faint">{d.doc_key} · v{d.version}{!d.is_current && " (superseded)"}</div></div>) },
            { key: "type", header: "Type", render: (d) => <Badge tone="violet">{titleCase(d.doc_type)}</Badge> },
            { key: "scope", header: "Access", render: (d) => <span className="text-xs">{SCOPES.find(([s]) => s === d.access_scope)?.[1]}{d.patient_mrn ? ` · patient ${d.patient_mrn}` : ""}</span> },
            { key: "dept", header: "Department", render: (d) => <span className="text-xs">{d.department ?? "Hospital-wide"}</span> },
            { key: "chunks", header: "Chunks", render: (d) => <span className="tabular-nums">{d.chunk_count}{d.flagged_chunk_count > 0 && <Badge tone="danger" className="ml-1.5"><ShieldAlert className="h-3 w-3" /> {d.flagged_chunk_count}</Badge>}</span> },
            { key: "status", header: "Status", render: (d) => <span title={d.error_message ?? undefined}><StatusBadge status={d.status} /></span> },
            { key: "at", header: "Uploaded", render: (d) => <span className="text-xs text-muted">{fmtDateTime(d.created_at)}</span> },
          ]} />
      </Card>
      {uploading && <UploadModal onClose={() => setUploading(false)} onUploaded={() => { setUploading(false); reload(); }} />}
      <DocumentDrawer id={selected} onClose={() => setSelected(null)} canManage={manage} onDeleted={() => { setSelected(null); reload(); }} />
    </>
  );
}

function UploadModal({ onClose, onUploaded }: { onClose: () => void; onUploaded: () => void }) {
  const { data: departments } = useApi<Department[]>("/departments");
  const [file, setFile] = useState<File | null>(null);
  const [form, setForm] = useState({ title: "", doc_type: "guideline", access_scope: "clinical", department_id: "", doc_key: "" });
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function submit() {
    if (!file) return;
    setBusy(true);
    setError(null);
    const body = new FormData();
    body.append("file", file);
    for (const [k, v] of Object.entries(form)) if (v) body.append(k, v);
    try {
      await api("/documents", { method: "POST", body });
      onUploaded();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal open onClose={onClose} title="Upload document"
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!file || form.title.length < 3}>Upload & index</Button></>}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="File (PDF, TXT, MD, DOCX · max 20 MB)" className="sm:col-span-2">
          <input type="file" accept=".pdf,.txt,.md,.docx" onChange={(e) => {
            const f = e.target.files?.[0] ?? null;
            setFile(f);
            if (f && !form.title) setForm({ ...form, title: f.name.replace(/\.[^.]+$/, "").replace(/[_-]+/g, " ") });
          }} className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-accent-tint file:px-3 file:py-1.5 file:text-accent" />
        </Field>
        <Field label="Title" className="sm:col-span-2"><Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
        <Field label="Type"><Select value={form.doc_type} onChange={(e) => setForm({ ...form, doc_type: e.target.value })} options={TYPES.map((t) => ({ value: t, label: titleCase(t) }))} /></Field>
        <Field label="Access scope"><Select value={form.access_scope} onChange={(e) => setForm({ ...form, access_scope: e.target.value })} options={SCOPES.map(([v, l]) => ({ value: v, label: l }))} /></Field>
        <Field label="Department"><Select value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })} placeholder="Hospital-wide" options={(departments ?? []).map((d) => ({ value: d.id, label: d.name }))} /></Field>
        <Field label="Document code" hint="Same code as an existing document creates a new version"><Input value={form.doc_key} onChange={(e) => setForm({ ...form, doc_key: e.target.value })} placeholder="e.g. MED-POL-004" /></Field>
      </div>
      <p className="mt-3 text-[11px] text-muted">Pipeline: upload → parse → clean → detect structure → chunk → scan for prompt injection → embed → index (vector + keyword). Upload only synthetic or properly de-identified material.</p>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}

function DocumentDrawer({ id, onClose, canManage, onDeleted }: { id: number | null; onClose: () => void; canManage: boolean; onDeleted: () => void }) {
  const { data, error, loading } = useApi<DocumentDetail>(id ? `/documents/${id}` : null);
  async function remove() {
    if (!data || !window.confirm(`Delete "${data.title}" v${data.version}? Its chunks will be removed from retrieval.`)) return;
    await api(`/documents/${data.id}`, { method: "DELETE" });
    onDeleted();
  }
  return (
    <Drawer open={id !== null} onClose={onClose} title={data?.title ?? "Document"} subtitle={data && <span className="font-mono">{data.doc_key} · v{data.version}</span>}>
      {loading && <Skeleton lines={10} />}
      {error ? <ErrorState error={error} /> : null}
      {data && (
        <div className="space-y-4">
          <KeyValue items={[
            ["Status", <StatusBadge key="s" status={data.status} />], ["Type", titleCase(data.doc_type)], ["Access", titleCase(data.access_scope)],
            ["File", `${data.filename} (${bytes(data.file_size)})`], ["Pages", data.page_count], ["Chunks", data.chunk_count],
            ["Indexed", fmtDateTime(data.indexed_at)], ["Current version", data.is_current ? "yes" : "no"],
          ]} />
          {data.error_message && <ErrorState error={new Error(data.error_message)} compact />}
          <div className="flex gap-2">
            <a href={`/api/documents/${data.id}/file`}><Button size="sm" variant="secondary"><Download className="h-3.5 w-3.5" /> Download</Button></a>
            {canManage && <Button size="sm" variant="danger" onClick={remove}><Trash2 className="h-3.5 w-3.5" /> Delete</Button>}
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-muted">Chunks ({data.chunks.length})</div>
            <ol className="space-y-2">
              {data.chunks.map((c) => (
                <li key={c.id} className={`rounded border p-2 text-xs ${c.flags?.injection_suspected ? "border-high-edge bg-high-tint" : "border-line"}`}>
                  <div className="mb-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                    <span className="font-mono">#{c.chunk_index}</span><span>{c.section_path || "Body"}</span><span>· p.{c.page_start}{c.page_end !== c.page_start ? `–${c.page_end}` : ""}</span><span>· {c.word_count} words</span>
                    {Boolean(c.flags?.injection_suspected) && <Badge tone="danger"><ShieldAlert className="h-3 w-3" /> quarantined: {(c.flags.injection_patterns as string[]).join(", ")}</Badge>}
                  </div>
                  <p className="whitespace-pre-wrap text-ink-2">{c.text}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </Drawer>
  );
}
