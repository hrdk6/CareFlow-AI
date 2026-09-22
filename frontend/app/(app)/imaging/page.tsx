"use client";

import { CheckCircle2, Images, RefreshCw, ScanEye, Siren } from "lucide-react";
import Link from "next/link";

import { WorklistRow } from "@/components/imaging/worklist-row";
import { IconButton } from "@/components/ui/button";
import { PageHeader, StatCard } from "@/components/ui/card";
import { EmptyState, ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { useApi } from "@/lib/hooks";
import type { Worklist } from "@/lib/types";

export default function ImagingPage() {
  const { data, error, loading, reload } = useApi<Worklist>("/imaging/worklist");
  const counts = data?.counts ?? {};
  const items = data?.items ?? [];

  return (
    <div className="space-y-4">
      <PageHeader title="Radiology"
        subtitle="Films waiting to be read for patients whose record you can open. The triage model sets the order; every film is still read, and a film it does not flag has not been cleared."
        actions={<IconButton label="Refresh" onClick={reload}><RefreshCw className="h-4 w-4" /></IconButton>} />

      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {data && !data.model_available && (
        <Notice tone="warning">
          The triage model is not installed on this server, so films are listed by how long they have waited.
          Everything else works as usual.
        </Notice>
      )}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Waiting to be read" value={counts.waiting ?? 0} icon={<Images />} hint="Across your patients" />
        <StatCard label="For attention" value={counts.priority ?? 0} tone={counts.priority ? "rose" : "slate"}
          icon={<Siren />} hint="Above the model's higher cut-off" />
        <StatCard label="Not ruled out" value={counts.elevated ?? 0} tone={counts.elevated ? "amber" : "slate"}
          icon={<ScanEye />} hint="Above the rule-out cut-off" />
        <StatCard label="Reported today" value={counts.reported ?? 0} icon={<CheckCircle2 />}
          hint="Signed in the last 24 hours" />
      </div>

      {loading && !data && (
        <div className="rounded-xl border border-line bg-panel p-5 shadow-e1"><Skeleton lines={8} /></div>
      )}
      {data && items.length === 0 && (
        <div className="rounded-xl border border-line bg-panel shadow-e1">
          <EmptyState title="No films waiting" icon={<Images className="h-5 w-5" />}
            message="Studies appear here as soon as they are ingested for a patient under your care." />
        </div>
      )}

      <div className="space-y-3">
        {items.map((item, i) => (
          <div key={item.study_id} className="stagger-in" style={{ "--i": Math.min(i, 8) } as React.CSSProperties}>
            <WorklistRow item={item} />
          </div>
        ))}
      </div>

      {data && (
        <p className="px-1 text-[11px] leading-relaxed text-faint">
          {data.note}{" "}
          {data.model_name && (
            <>
              Model: {data.model_name} v{data.model_version} —{" "}
              <Link href="/analytics" className="text-accent hover:text-accent-strong">how it was evaluated</Link>.
            </>
          )}
        </p>
      )}
    </div>
  );
}
