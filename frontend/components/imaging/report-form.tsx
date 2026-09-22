"use client";

import { CheckCircle2, FileSignature, Save } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { Field, Textarea } from "@/components/ui/form";
import { api } from "@/lib/api";
import { cn, fmtDateTime } from "@/lib/format";
import type { Agreement, ImagingReport, ImagingStudy } from "@/lib/types";

const AGREEMENT: { value: Agreement; label: string }[] = [
  { value: "agreed", label: "Matched my read" },
  { value: "partly", label: "Partly" },
  { value: "disagreed", label: "Did not match" },
  { value: "not_used", label: "I did not use it" },
];

/**
 * The radiologist's report. Nothing here is drafted by a model: the text is the reader's, and signing is
 * what puts it in the medical record. The one question about the model is asked because a flag is only
 * worth keeping if readers say it was right, and that answer is stored with the report.
 */
export function ReportForm({ study, onSaved, canWrite, canSign }: {
  study: ImagingStudy; onSaved: (report: ImagingReport) => void; canWrite: boolean; canSign: boolean;
}) {
  const existing = study.report;
  const [findings, setFindings] = useState(existing?.findings ?? "");
  const [impression, setImpression] = useState(existing?.impression ?? "");
  const [agreement, setAgreement] = useState<Agreement>(existing?.model_agreement ?? (study.triage ? "agreed" : "not_used"));
  const [busy, setBusy] = useState<"draft" | "sign" | null>(null);
  const [error, setError] = useState<unknown>(null);

  if (existing?.status === "final") {
    return (
      <section className="rounded-xl border border-ok-edge bg-panel p-4 shadow-e1">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <CheckCircle2 className="h-4 w-4 text-ok" aria-hidden /> Report signed
          <Badge tone="success">Final</Badge>
        </h2>
        <p className="mt-1 text-[12px] text-muted">
          {existing.reported_by ? `${existing.reported_by} · ` : ""}{existing.signed_at ? fmtDateTime(existing.signed_at) : ""}
          {existing.record_id ? " · in the medical record" : ""}
        </p>
        <dl className="mt-3 space-y-3 text-[13px] leading-relaxed">
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">Findings</dt>
            <dd className="mt-0.5 whitespace-pre-wrap text-ink-2">{existing.findings}</dd>
          </div>
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">Impression</dt>
            <dd className="mt-0.5 whitespace-pre-wrap font-medium text-ink">{existing.impression}</dd>
          </div>
          {existing.model_agreement && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wide text-muted">Triage model</dt>
              <dd className="mt-0.5 text-ink-2">
                {AGREEMENT.find((a) => a.value === existing.model_agreement)?.label ?? existing.model_agreement}
              </dd>
            </div>
          )}
        </dl>
      </section>
    );
  }

  const save = async (sign: boolean) => {
    setBusy(sign ? "sign" : "draft");
    setError(null);
    try {
      const report = await api<ImagingReport>(`/imaging/studies/${study.id}/report`, {
        method: "PUT",
        json: { findings: findings.trim(), impression: impression.trim(), model_agreement: agreement, sign },
      });
      onSaved(report);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(null);
    }
  };

  const complete = findings.trim().length > 0 && impression.trim().length > 0;

  return (
    <section className="rounded-xl border border-line bg-panel p-4 shadow-e1">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <FileSignature className="h-4 w-4 text-muted" aria-hidden /> Report
        {existing?.status === "draft" && <Badge tone="warning">Draft</Badge>}
      </h2>
      {!canWrite ? (
        <p className="mt-2 text-[13px] text-muted">Your role can read this study but not report on it.</p>
      ) : (
        <div className="mt-3 space-y-3">
          <Field label="Findings">
            <Textarea rows={6} value={findings} onChange={(e) => setFindings(e.target.value)}
              placeholder="Describe what you see: lung fields, heart size, costophrenic angles, lines and tubes." />
          </Field>
          <Field label="Impression">
            <Textarea rows={3} value={impression} onChange={(e) => setImpression(e.target.value)}
              placeholder="The conclusion the referring team will act on." />
          </Field>

          {study.triage && (
            <fieldset>
              <legend className="text-[12px] font-medium text-ink">Did the model&rsquo;s flags match your read?</legend>
              <p className="mt-0.5 text-[11px] text-muted">
                Kept with the report. It is the only honest measure of the model once a film is not a test film.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {AGREEMENT.map((option) => (
                  <button key={option.value} type="button" onClick={() => setAgreement(option.value)}
                    aria-pressed={agreement === option.value}
                    className={cn("rounded-full border px-3 py-1 text-[12px] font-medium transition-colors",
                      agreement === option.value
                        ? "border-accent-edge bg-accent-tint text-accent"
                        : "border-line bg-raised text-ink-2 hover:border-line-strong")}>
                    {option.label}
                  </button>
                ))}
              </div>
            </fieldset>
          )}

          {error ? <ErrorState error={error} compact /> : null}
          {!canSign && (
            <Notice tone="info">
              You can save a draft. A report enters the medical record only when a clinician with a doctor
              profile signs it.
            </Notice>
          )}

          <div className="flex flex-wrap items-center gap-2">
            <Button variant="secondary" onClick={() => save(false)} disabled={!complete || busy !== null}>
              <Save className="h-3.5 w-3.5" aria-hidden /> {busy === "draft" ? "Saving…" : "Save draft"}
            </Button>
            {canSign && (
              <Button onClick={() => save(true)} disabled={!complete || busy !== null}>
                <FileSignature className="h-3.5 w-3.5" aria-hidden /> {busy === "sign" ? "Signing…" : "Sign report"}
              </Button>
            )}
            <span className="text-[11px] text-muted">Signing writes it into the patient&rsquo;s record.</span>
          </div>
        </div>
      )}
    </section>
  );
}
