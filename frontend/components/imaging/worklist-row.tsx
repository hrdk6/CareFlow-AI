"use client";

import { ArrowRight, BedDouble, CheckCircle2, Clock, ScanLine } from "lucide-react";
import Link from "next/link";

import { PRIORITY } from "@/components/imaging/findings";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { cn, fmtTime } from "@/lib/format";
import type { WorklistItem } from "@/lib/types";

const waited = (hours: number) =>
  hours < 1 ? `${Math.max(1, Math.round(hours * 60))} min` : hours < 48 ? `${Math.round(hours)} h` : `${Math.round(hours / 24)} d`;

/** One film in the reading queue. The score decides the order; the reader decides everything else. */
export function WorklistRow({ item }: { item: WorklistItem }) {
  const band = item.priority ? PRIORITY[item.priority] : null;
  return (
    <article className={cn("relative overflow-hidden rounded-xl border bg-panel shadow-e1 transition-colors",
      item.reported ? "border-line opacity-80" : band?.label === "Priority" ? "border-high-edge" : "border-line")}>
      <span className={cn("absolute inset-y-0 left-0 w-1", band ? band.rail : "bg-line-strong")} aria-hidden />
      <div className="flex flex-wrap items-start gap-x-5 gap-y-3 px-5 py-4 pl-6">
        <Avatar name={item.full_name} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <Link href={`/patients/${item.patient_id}`} className="text-[15px] font-semibold text-ink hover:text-accent">
              {item.full_name}
            </Link>
            <span className="rounded bg-raised px-1.5 font-mono text-[11px] leading-5 text-ink-2">{item.mrn}</span>
            <span className="text-xs text-muted">
              {item.age} y · {item.sex}{item.department ? ` · ${item.department}` : ""}
            </span>
            {item.inpatient && (
              <Badge tone="info"><BedDouble className="h-3 w-3" aria-hidden /> Inpatient</Badge>
            )}
          </div>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[13px] text-muted">
            <ScanLine className="h-3.5 w-3.5" aria-hidden />
            <span className="font-medium text-ink-2">{item.description ?? "Study"}</span>
            <span className="font-mono text-[11px]">{item.accession}</span>
            {item.indication ? <span className="truncate">· {item.indication}</span> : null}
          </p>
          {item.flagged.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {item.flagged.map((finding) => (
                <li key={finding}><Badge tone={item.priority === "priority" ? "danger" : "warning"}>{finding}</Badge></li>
              ))}
            </ul>
          )}
        </div>
        <div className="flex items-center gap-4">
          {band ? (
            <div className="text-right">
              <div className={cn("tabular font-display text-[26px] font-semibold leading-none", band.text)}>
                {Math.round((item.priority_score ?? 0) * 100)}%
              </div>
              <div className="mt-1 text-[11px] font-medium text-muted">Any finding · {band.label}</div>
            </div>
          ) : (
            <p className="max-w-[170px] text-right text-[11px] leading-snug text-muted">
              Not scored by the triage model
            </p>
          )}
          <div className="flex flex-col items-end gap-1.5">
            {item.reported ? (
              <span className="flex items-center gap-1 whitespace-nowrap text-[11px] text-ok">
                <CheckCircle2 className="h-3 w-3" aria-hidden /> Reported {item.reported_at ? fmtTime(item.reported_at) : ""}
              </span>
            ) : (
              <span className="flex items-center gap-1 whitespace-nowrap text-[11px] text-muted">
                <Clock className="h-3 w-3" aria-hidden /> Waiting {waited(item.waiting_hours)}
              </span>
            )}
            <Link href={`/imaging/${item.study_id}`}
              className="group flex items-center gap-1 text-[11px] font-medium text-accent hover:text-accent-strong">
              {item.reported ? "Open study" : "Read"}
              <ArrowRight className="h-3 w-3 transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}
