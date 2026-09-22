"use client";

import {
  AlertTriangle, ArrowLeft, BookOpenCheck, ClipboardList, FileSignature, FlaskConical, Gauge, Pill, RefreshCw, ShieldCheck, Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { PrivacyPanel } from "@/components/assistant/privacy";
import { SourceDrawer } from "@/components/assistant/source-drawer";
import { Chips, ChecklistCard, InvestigationsTable, ReconciliationTable, RiskScreenCard } from "@/components/discharge/panels";
import { EditableSection, flaggedSentences, remainingFlagged } from "@/components/discharge/review-text";
import { VitalsRow } from "@/components/ward/board-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { Field, Select } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { api, ApiError } from "@/lib/api";
import { PERMS, useAuth } from "@/lib/auth";
import { cn, fmtDate, fmtDateTime, titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Admission, Citation, DischargeDraft, DischargeSigned } from "@/lib/types";

type Text = { presenting_problem: string; hospital_course: string; follow_up_plan: string };
const DISPOSITIONS = ["home", "home_health", "skilled_nursing", "rehab", "transfer", "ama", "expired"];

function textOf(d: DischargeDraft): Text {
  return { presenting_problem: d.sections[0]?.text ?? "", hospital_course: d.sections[1]?.text ?? "", follow_up_plan: d.follow_up_plan };
}

function writer(generatedBy: string): string {
  if (generatedBy === "template") return "Assembled from the record (no language model)";
  const [provider, ...model] = generatedBy.split("/");
  return `Drafted by ${titleCase(provider)} · ${model.join("/")}`;
}

export default function DischargePage() {
  const { id, admissionId } = useParams<{ id: string; admissionId: string }>();
  const router = useRouter();
  const { can } = useAuth();
  const { data: admissions, error: admissionsError, reload } = useApi<Admission[]>(`/patients/${id}/admissions`);
  const admission = admissions?.find((a) => String(a.id) === admissionId);
  const [draft, setDraft] = useState<DischargeDraft | null>(null);
  const [text, setText] = useState<Text>({ presenting_problem: "", hospital_course: "", follow_up_plan: "" });
  const [checked, setChecked] = useState(false); // looked for an open draft to resume
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [citation, setCitation] = useState<Citation | null>(null);
  const [signing, setSigning] = useState(false);
  const [replacing, setReplacing] = useState(false);

  function load(d: DischargeDraft) {
    setDraft(d);
    setText(textOf(d));
  }

  // Resume the newest unsigned draft, if there is one; a 404 simply means there is none yet.
  useEffect(() => {
    let alive = true;
    api<DischargeDraft>(`/admissions/${admissionId}/discharge-draft`)
      .then((d) => alive && load(d), (e: ApiError) => alive && e.status !== 404 && setError(e))
      .finally(() => alive && setChecked(true));
    return () => {
      alive = false;
    };
  }, [admissionId]);

  async function prepare() {
    setReplacing(false);
    setBusy(true);
    setError(null);
    try {
      load(await api<DischargeDraft>(`/admissions/${admissionId}/discharge-draft`, { method: "POST" }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  const labels = useMemo<Record<string, string>>(() => Object.fromEntries([
    ...(draft?.record_refs ?? []).map((r) => [r.id, `${titleCase(r.source_type)}: ${r.label}${r.date ? ` (${r.date})` : ""}`]),
    ...(draft?.citations ?? []).map((c) => [c.id, `${c.document_title} — ${c.section_path}`]),
  ]), [draft]);
  const flagged = useMemo(() => flaggedSentences(draft?.sections ?? []), [draft]);
  const remaining = draft ? remainingFlagged(draft.sections, text) : [];
  const edited = draft ? JSON.stringify(textOf(draft)) !== JSON.stringify(text) : false;
  const onCite = (cid: string) => {
    const c = draft?.citations.find((x) => x.id === cid);
    if (c) setCitation(c);
  };

  if (!can(PERMS.admit, PERMS.clinicalWrite)) {
    return <ErrorState error={new Error("Preparing a discharge summary needs a clinician who can discharge patients.")} />;
  }
  if (admissionsError) return <ErrorState error={admissionsError} onRetry={reload} />;
  const patientName = draft?.patient.name;

  return (
    <div className="space-y-4">
      <Link href={`/patients/${id}`} className="group inline-flex items-center gap-1 rounded-md text-[13px] text-muted hover:text-accent">
        <ArrowLeft className="h-3.5 w-3.5 transition-transform duration-200 group-hover:-translate-x-0.5" aria-hidden /> {patientName ?? "Patient"}
      </Link>

      <header className="rise flex flex-wrap items-start justify-between gap-x-6 gap-y-3 rounded-xl border border-line bg-panel px-5 py-4 shadow-e1 sm:px-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-[24px] font-semibold leading-tight text-ink">Discharge summary</h1>
            {draft && <Badge tone="warning" dot>Draft · not yet in the record</Badge>}
          </div>
          {admission ? (
            <p className="mt-1 text-sm text-muted">
              {draft ? `${draft.patient.name} (${draft.patient.mrn}) · ` : ""}Admitted {fmtDate(admission.admitted_at)} to {admission.department} · {admission.reason}
              {admission.status === "admitted" ? " · still admitted" : ` · discharged ${fmtDate(admission.discharged_at)}`}
            </p>
          ) : <div className="shimmer mt-2 h-3 w-72 rounded-full" />}
          {draft && (
            <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-muted">
              <Sparkles className="h-3.5 w-3.5 text-ai" aria-hidden /> {writer(draft.generated_by)} · {fmtDateTime(draft.generated_at)} UTC
              {draft.privacy?.applied && <span className="inline-flex items-center gap-1 text-ok"><ShieldCheck className="h-3.5 w-3.5" aria-hidden /> identifiers hidden from the model</span>}
            </p>
          )}
        </div>
        {draft && (
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => (edited ? setReplacing(true) : prepare())} loading={busy}>
              {!busy && <RefreshCw className="h-4 w-4" aria-hidden />} Redraft
            </Button>
            <Button onClick={() => setSigning(true)}><FileSignature className="h-4 w-4" aria-hidden /> Review and sign</Button>
          </div>
        )}
      </header>

      {error ? <ErrorState error={error} onRetry={draft ? undefined : prepare} /> : null}

      {!draft && checked && (busy ? <Preparing /> : <Intro onStart={prepare} admission={admission} />)}
      {!draft && !checked && <Card><Skeleton lines={6} /></Card>}

      {draft && (
        <div key={draft.draft_id} className="animate-panel-in space-y-4">
          {draft.warnings.map((w) => <Notice key={w} tone="warning" icon={<AlertTriangle className="h-3.5 w-3.5 shrink-0" />}>{w}</Notice>)}
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_400px]">
            <Card title="The summary" subtitle="Edit the prose freely. Diagnoses, medicines and results come straight from the record."
              bodyClassName="space-y-6 px-5 py-5 sm:px-6">
              <dl className="grid gap-x-6 gap-y-2 rounded-lg bg-sunken px-4 py-3 text-[13px] sm:grid-cols-2">
                <div><dt className="text-xs text-muted">Patient</dt><dd className="text-ink">{draft.patient.name} · {draft.patient.age} y · {draft.patient.sex === "F" ? "Female" : draft.patient.sex === "M" ? "Male" : "Other"}</dd></div>
                <div><dt className="text-xs text-muted">Allergies</dt><dd className="text-ink">{draft.patient.allergies.length ? draft.patient.allergies.map((a) => a.substance).join(", ") : "None known"}</dd></div>
                <div><dt className="text-xs text-muted">Admission</dt><dd className="text-ink">{fmtDate(draft.admission.admitted_at)} · {titleCase(draft.admission.admission_type)} via {titleCase(draft.admission.admission_source)}</dd></div>
                <div><dt className="text-xs text-muted">Attending</dt><dd className="text-ink">{draft.admission.attending_doctor ?? "—"}{draft.admission.ward ? ` · Ward ${draft.admission.ward}` : ""}</dd></div>
                {draft.observations && (
                  <div className="sm:col-span-2">
                    <dt className="text-xs text-muted">Latest observations · {fmtDateTime(draft.observations.recorded_at)} UTC</dt>
                    <dd className="mt-1 text-ink"><VitalsRow v={draft.observations} /></dd>
                  </div>
                )}
              </dl>
              {draft.sections.map((s) => (
                <EditableSection key={s.key} title={s.title} text={text[s.key]} onChange={(v) => setText({ ...text, [s.key]: v })}
                  flagged={flagged} labels={labels} onCite={onCite} />
              ))}
              <section>
                <h3 className="mb-1.5 text-[14px] font-semibold text-ink">Diagnoses</h3>
                <ul className="space-y-1 text-[14px] text-ink-2">
                  {draft.diagnoses.map((d) => (
                    <li key={d.code} className="flex flex-wrap items-baseline gap-x-2">
                      <span className="w-[92px] shrink-0 text-xs text-muted">{titleCase(d.role)}</span>
                      <span>{d.description}</span>
                      <span className="rounded bg-raised px-1 font-mono text-[11px] text-ink-2">{d.code}</span>
                      <Chips ids={[d.ref]} labels={labels} onCite={onCite} />
                    </li>
                  ))}
                </ul>
              </section>
              <MedicationSummary draft={draft} labels={labels} onCite={onCite} />
              <EditableSection title="Follow-up plan" text={text.follow_up_plan} onChange={(v) => setText({ ...text, follow_up_plan: v })}
                flagged={flagged} labels={labels} onCite={onCite} markdown />
              <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                <p className="text-xs text-muted">{edited ? "You have edited the draft. " : ""}Nothing is saved to the record until you sign.</p>
                <Button onClick={() => setSigning(true)}><FileSignature className="h-4 w-4" aria-hidden /> Review and sign</Button>
              </div>
            </Card>
            <div className="min-w-0 space-y-4 xl:sticky xl:top-20 xl:self-start">
              <RiskScreenCard risk={draft.risk} labels={labels} onCite={onCite} />
              <ChecklistCard checklist={draft.checklist} labels={labels} onCite={onCite} patientId={draft.patient.id} />
              {draft.privacy && (
                <Card title="What the language model saw"><div className="text-xs"><PrivacyPanel privacy={draft.privacy} /></div></Card>
              )}
            </div>
          </div>
          <Card bodyClassName="p-0" title={<span className="flex items-center gap-2"><Pill className="h-4 w-4 text-faint" aria-hidden /> Medication reconciliation</span>}
            subtitle="The list on admission, the orders during the stay and the discharge list, compared line by line (discharge policy, section 5)">
            <ReconciliationTable medications={draft.medications} labels={labels} onCite={onCite} />
          </Card>
          <Card bodyClassName="p-0" title={<span className="flex items-center gap-2"><FlaskConical className="h-4 w-4 text-faint" aria-hidden /> Results during the stay</span>}
            subtitle="First and latest value of every test, most abnormal first">
            <InvestigationsTable investigations={draft.investigations} labels={labels} onCite={onCite} />
          </Card>
          <p className="px-1 text-[11px] leading-snug text-faint">{draft.disclaimer}</p>
        </div>
      )}

      <SourceDrawer citation={citation} onClose={() => setCitation(null)} />
      {replacing && (
        <Modal open onClose={() => setReplacing(false)} title="Replace your edits?"
          footer={<><Button variant="secondary" onClick={() => setReplacing(false)}>Keep editing</Button><Button onClick={prepare}>Redraft</Button></>}>
          <p className="text-sm text-ink-2">A new draft is built from the current record. The changes you made to this draft will be lost.</p>
        </Modal>
      )}
      {signing && draft && (
        <SignModal draft={draft} text={text} remaining={remaining} onClose={() => setSigning(false)}
          onSigned={() => router.push(`/patients/${id}?tab=records`)} />
      )}
    </div>
  );
}

function MedicationSummary({ draft, labels, onCite }: { draft: DischargeDraft; labels: Record<string, string>; onCite: (id: string) => void }) {
  const changes = draft.medications.filter((m) => ["changed", "new", "stopped", "held_resumed"].includes(m.status));
  const continued = draft.medications.filter((m) => m.status === "continued");
  const verb = { changed: "Changed", new: "Started", stopped: "Stopped", held_resumed: "Held during the stay, resumed" } as Record<string, string>;
  return (
    <section>
      <h3 className="mb-1.5 text-[14px] font-semibold text-ink">Medication changes at discharge</h3>
      {changes.length === 0 ? <p className="text-[14px] text-ink-2">None.</p> : (
        <ul className="space-y-1 text-[14px] text-ink-2">
          {changes.map((m) => (
            <li key={m.medication}>
              <span className="font-medium text-ink">{verb[m.status]}:</span> {m.medication}{" "}
              {m.status === "changed" ? `${m.before} → ${m.after}` : m.after ?? ""}
              {m.reason && m.status !== "held_resumed" ? <span className="text-muted"> ({m.reason})</span> : null}
              {m.high_alert && <Badge tone="danger" className="ml-1.5">High-alert</Badge>} <Chips ids={m.refs.slice(0, 2)} labels={labels} onCite={onCite} />
            </li>
          ))}
        </ul>
      )}
      {continued.length > 0 && <p className="mt-1 text-[13px] text-muted">Continued unchanged: {continued.map((m) => m.medication).join(", ")}.</p>}
    </section>
  );
}

function Intro({ onStart, admission }: { onStart: () => void; admission?: Admission }) {
  const steps: [React.ElementType, string, string][] = [
    [ClipboardList, "Reads this admission", "Notes, diagnoses, every result and every medicine order, each kept as a source."],
    [BookOpenCheck, "Applies the discharge policy", "Readmission screening, transitional care and medication reconciliation, linked to the policy text."],
    [Gauge, "Estimates readmission risk", "The readmission model is one of the policy's screening criteria."],
    [Sparkles, "Drafts the narrative", "Only the prose is written by a language model, and every sentence is checked against its sources."],
  ];
  return (
    <Card>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.3fr)] lg:items-center">
        <div>
          <h2 className="text-[19px] font-semibold text-ink">Prepare the discharge summary</h2>
          <p className="mt-1.5 text-sm leading-relaxed text-muted">
            The co-pilot assembles a draft from the record for you to check, edit and sign. Nothing is written to the medical
            record until you sign it{admission?.status === "admitted" ? ", and you choose whether to discharge the patient at the same time" : ""}.
          </p>
          <Button className="mt-4" onClick={onStart}><Sparkles className="h-4 w-4" aria-hidden /> Prepare draft</Button>
        </div>
        <ol className="grid gap-2.5 sm:grid-cols-2">
          {steps.map(([Icon, title, body], i) => (
            <li key={title} className="rise rounded-xl border border-line bg-sunken/60 p-3.5" style={{ "--i": i } as React.CSSProperties}>
              <Icon className="h-4 w-4 text-accent" aria-hidden />
              <p className="mt-2 text-[13px] font-semibold text-ink">{title}</p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">{body}</p>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

/** Time-based stages, like the assistant's: an honest indeterminate bar rather than a fake percentage. */
function Preparing() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const t = setInterval(() => setElapsed(Date.now() - started), 400);
    return () => clearInterval(t);
  }, []);
  const stages = ["Reading the admission's notes, results and medicines", "Checking the discharge policy", "Estimating readmission risk", "Writing the narrative"];
  const at = Math.min(stages.length - 1, Math.floor(elapsed / 1100));
  return (
    <div role="status" className="overflow-hidden rounded-xl border border-line bg-panel shadow-e1">
      <ul className="space-y-2 px-5 py-4 text-sm">
        {stages.map((s, i) => (
          <li key={s} className={cn("flex items-center gap-2 transition-colors duration-300", i < at ? "text-ok" : i === at ? "text-ink" : "text-faint")}>
            <span className={cn("h-1.5 w-1.5 rounded-full", i < at ? "bg-ok" : i === at ? "attention-dot bg-accent text-accent" : "bg-line-strong")} aria-hidden />
            {s}{i === at ? "…" : ""}
          </li>
        ))}
      </ul>
      <div className="h-0.5 overflow-hidden bg-raised" aria-hidden>
        <div className="progress-sweep h-full w-2/5 bg-gradient-to-r from-transparent via-accent to-transparent" />
      </div>
    </div>
  );
}

function SignModal({ draft, text, remaining, onClose, onSigned }: {
  draft: DischargeDraft; text: Text; remaining: string[]; onClose: () => void; onSigned: (s: DischargeSigned) => void;
}) {
  const open = draft.admission.status === "admitted";
  const [confirm, setConfirm] = useState(false);
  const [discharge, setDischarge] = useState(open);
  const [disposition, setDisposition] = useState("home");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const openItems = draft.checklist.filter((c) => c.status === "not_met" || c.status === "to_confirm");
  async function sign() {
    setBusy(true);
    setError(null);
    try {
      onSigned(await api<DischargeSigned>(`/admissions/${draft.admission.id}/discharge-summary`, { method: "POST", json: {
        draft_id: draft.draft_id, ...text, confirm_unsupported: confirm,
        discharge: open && discharge ? { discharge_disposition: disposition } : null } }));
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }
  return (
    <Modal open wide onClose={onClose} title="Sign the discharge summary"
      footer={<><Button variant="secondary" onClick={onClose}>Back to the draft</Button>
        <Button onClick={sign} loading={busy} disabled={remaining.length > 0 && !confirm}><FileSignature className="h-4 w-4" aria-hidden /> Sign{open && discharge ? " and discharge" : ""}</Button></>}>
      <div className="space-y-4 text-sm text-ink-2">
        <p>The summary is saved to {draft.patient.name}&apos;s record under your name. Its sources stay linked to the text, and the record notes that it was drafted with AI and how much you changed.</p>
        {remaining.length > 0 && (
          <div className="rounded-lg border border-warn-edge bg-warn-tint p-3">
            <p className="flex items-center gap-1.5 font-medium text-ink"><AlertTriangle className="h-4 w-4 text-warn" aria-hidden /> {remaining.length} drafted sentence{remaining.length === 1 ? "" : "s"} could not be traced to a source</p>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[13px]">{remaining.map((s) => <li key={s}>{s.replace(/\s*\[[SR]\d+\]/g, "")}</li>)}</ul>
            <label className="mt-2.5 flex items-start gap-2 text-[13px] text-ink">
              <input type="checkbox" className="mt-0.5 accent-[var(--color-accent)]" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} />
              I have checked these sentences against the record and they are correct.
            </label>
          </div>
        )}
        {openItems.length > 0 && (
          <div>
            <p className="font-medium text-ink">Still open on the checklist</p>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px]">{openItems.map((c) => <li key={c.key}>{c.label}</li>)}</ul>
            <p className="mt-1 text-xs text-muted">These are listed in the follow-up plan; signing does not require them to be complete.</p>
          </div>
        )}
        {open ? (
          <div className="rounded-lg border border-line p-3">
            <label className="flex items-center gap-2 font-medium text-ink">
              <input type="checkbox" className="accent-[var(--color-accent)]" checked={discharge} onChange={(e) => setDischarge(e.target.checked)} />
              Also discharge the patient now
            </label>
            {discharge && (
              <Field label="Discharge destination" className="mt-3 max-w-xs">
                <Select value={disposition} onChange={(e) => setDisposition(e.target.value)} options={DISPOSITIONS.map((d) => ({ value: d, label: d === "ama" ? "Against medical advice" : titleCase(d) }))} />
              </Field>
            )}
          </div>
        ) : <p className="text-xs text-muted">This admission is already closed; the summary is added to its record.</p>}
        {error ? <ErrorState error={error} compact /> : null}
      </div>
    </Modal>
  );
}
