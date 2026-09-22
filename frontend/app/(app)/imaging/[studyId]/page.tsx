"use client";

import { ArrowLeft, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { TriagePanel } from "@/components/imaging/findings";
import { ReportForm } from "@/components/imaging/report-form";
import { FilmViewer } from "@/components/imaging/viewer";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/card";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { PERMS, useAuth } from "@/lib/auth";
import { fmtDate } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Finding, ImagingStudy } from "@/lib/types";

/** What ingestion removed from this file, so the claim is checkable rather than a promise. */
function DeidentificationCard({ study }: { study: ImagingStudy }) {
  const cleaning = study.deidentification;
  const removed = cleaning.removed_tags?.length ?? 0;
  const blanked = cleaning.blanked_tags?.length ?? 0;
  if (!removed && !blanked) return null;
  return (
    <section className="rounded-xl border border-line bg-panel p-4 shadow-e1">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
        <ShieldCheck className="h-4 w-4 text-ok" aria-hidden /> De-identified on arrival
      </h2>
      <p className="mt-1.5 text-[12px] leading-relaxed text-muted">
        {removed} identifying tag{removed === 1 ? "" : "s"} removed and {blanked} emptied before this file was
        written to disk{cleaning.private_tags_removed ? ", private tags dropped" : ""}
        {cleaning.uids_regenerated ? ", and new study identifiers minted" : ""}. Dates were shifted by a
        fixed offset for this patient, so intervals between films survive and no real date does.
      </p>
      <details className="mt-2">
        <summary className="cursor-pointer text-[11px] font-medium text-muted hover:text-ink">
          Which tags
        </summary>
        <p className="mt-1.5 break-words font-mono text-[10px] leading-relaxed text-faint">
          {[...(cleaning.removed_tags ?? []), ...(cleaning.blanked_tags ?? [])].join(", ")}
        </p>
        <p className="mt-1.5 text-[10px] text-faint">{cleaning.method}</p>
      </details>
    </section>
  );
}

export default function StudyPage() {
  const params = useParams<{ studyId: string }>();
  const { can, user } = useAuth();
  const { data: study, error, loading, reload } = useApi<ImagingStudy>(`/imaging/studies/${params.studyId}`);
  const [finding, setFinding] = useState<Finding | null>(null);

  if (error) return <ErrorState error={error} onRetry={reload} />;
  if (loading && !study) {
    return <div className="rounded-xl border border-line bg-panel p-5 shadow-e1"><Skeleton lines={10} /></div>;
  }
  if (!study) return null;

  return (
    <div className="space-y-4">
      <Link href="/imaging" className="inline-flex items-center gap-1.5 text-[12px] font-medium text-muted hover:text-ink">
        <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Reading queue
      </Link>

      <PageHeader title={study.description ?? `${study.modality} study`}
        subtitle={[study.accession, `Acquired ${fmtDate(study.acquired_at)}`, study.indication]
          .filter(Boolean).join(" · ")}
        actions={
          <div className="flex items-center gap-2">
            {study.report?.status === "final" && <Badge tone="success">Reported</Badge>}
            {study.report?.status === "draft" && <Badge tone="warning">Draft report</Badge>}
            <Link href={`/patients/${study.patient_id}`}
              className="text-[12px] font-medium text-accent hover:text-accent-strong">Open the record</Link>
          </div>
        } />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
        {/* self-start: the viewer hugs the film instead of stretching to the height of the right column. */}
        <FilmViewer study={study} finding={finding} className="self-start" />
        <div className="space-y-4">
          <TriagePanel triage={study.triage} selected={finding?.finding ?? null} onSelect={setFinding} />
          <ReportForm study={study} onSaved={reload} canWrite={can(PERMS.clinicalWrite)}
            canSign={can(PERMS.clinicalWrite) && Boolean(user?.doctor_id)} />
          <DeidentificationCard study={study} />
        </div>
      </div>
    </div>
  );
}
