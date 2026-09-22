"use client";

import { ChevronDown, Info, ScanEye } from "lucide-react";
import { useState } from "react";

import { Badge, type Tone } from "@/components/ui/badge";
import { cn, fmtDate } from "@/lib/format";
import type { Finding, Priority, Triage } from "@/lib/types";

export const PRIORITY: Record<Priority, { label: string; tone: Tone; rail: string; text: string }> = {
  routine: { label: "Routine", tone: "success", rail: "bg-ok", text: "text-ok" },
  elevated: { label: "Elevated", tone: "warning", rail: "bg-warn", text: "text-warn" },
  priority: { label: "Priority", tone: "danger", rail: "bg-high", text: "text-high" },
};

/** What the model is saying about one finding, in words a reader can act on. */
function verdict(finding: Finding): { label: string; tone: Tone } {
  if (finding.priority) return { label: "For attention", tone: "danger" };
  if (finding.flagged) return { label: "Not ruled out", tone: "warning" };
  return { label: "Below the cut-off", tone: "neutral" };
}

const pct = (value: number) => `${(value * 100).toFixed(value < 0.1 ? 1 : 0)}%`;

function FindingRow({ finding, selected, onSelect }: {
  finding: Finding; selected: boolean; onSelect: () => void;
}) {
  const { label, tone } = verdict(finding);
  const mark = Math.min(96, finding.threshold * 100);
  return (
    <li>
      <button type="button" onClick={onSelect} aria-pressed={selected}
        className={cn("w-full rounded-lg border px-3 py-2.5 text-left transition-colors",
          selected ? "border-accent-edge bg-accent-tint/40" : "border-transparent hover:bg-raised")}>
        <div className="flex items-center gap-2">
          <span className="flex-1 truncate text-[13px] font-medium text-ink">{finding.label}</span>
          <Badge tone={tone}>{label}</Badge>
          <span className="tabular w-10 text-right text-[13px] font-semibold text-ink">{pct(finding.probability)}</span>
        </div>
        <div className="relative mt-2 h-1.5 rounded-full bg-sunken" aria-hidden>
          <div className={cn("h-full rounded-full", finding.priority ? "bg-high" : finding.flagged ? "bg-warn" : "bg-line-strong")}
            style={{ width: `${Math.max(2, Math.min(100, finding.probability * 100))}%` }} />
          <span className="absolute top-1/2 h-3 w-px -translate-y-1/2 bg-ink/50" style={{ left: `${mark}%` }} />
        </div>
        <p className="mt-1.5 text-[11px] leading-relaxed text-muted">
          Cut-off {pct(finding.threshold)} · base rate {pct(finding.prevalence)} · AUC {finding.roc_auc.toFixed(2)}
          {" "}({finding.roc_auc_ci[0].toFixed(2)}–{finding.roc_auc_ci[1].toFixed(2)})
          {finding.sensitivity !== null && finding.specificity !== null && (
            <> · at this cut-off it catches {pct(finding.sensitivity)} and clears {pct(finding.specificity)}</>
          )}
        </p>
      </button>
    </li>
  );
}

export function TriagePanel({ triage, selected, onSelect, className }: {
  triage: Triage | null; selected: string | null; onSelect: (finding: Finding | null) => void; className?: string;
}) {
  const [open, setOpen] = useState(false);

  if (!triage) {
    return (
      <section className={cn("rounded-xl border border-line bg-panel p-4 shadow-e1", className)}>
        <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
          <ScanEye className="h-4 w-4 text-muted" aria-hidden /> Triage model
        </h2>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          This study was not scored. The model covers frontal chest films of adults only; everything else is
          stored and displayed without a score.
        </p>
      </section>
    );
  }

  const band = PRIORITY[triage.priority];
  const overall = triage.findings.find((f) => f.finding === "any_finding");
  const rest = triage.findings.filter((f) => f.finding !== "any_finding");

  return (
    <section className={cn("overflow-hidden rounded-xl border border-line bg-panel shadow-e1", className)}>
      <div className="flex items-start gap-3 border-b border-line px-4 py-3">
        <span className={cn("mt-1 h-8 w-1 rounded-full", band.rail)} aria-hidden />
        <div className="min-w-0 flex-1">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-ink">
            <ScanEye className="h-4 w-4 text-muted" aria-hidden /> Triage model
            <Badge tone={band.tone}>{band.label}</Badge>
          </h2>
          <p className="mt-0.5 text-[12px] text-muted">
            {overall ? <>Probability that the film shows any finding: <strong className="text-ink">{pct(overall.probability)}</strong>. </> : null}
            Reading order only.
          </p>
        </div>
      </div>

      <ul className="space-y-1 p-2">
        {rest.map((finding) => (
          <FindingRow key={finding.finding} finding={finding} selected={selected === finding.finding}
            onSelect={() => onSelect(selected === finding.finding ? null : finding)} />
        ))}
      </ul>

      <div className="border-t border-line bg-sunken/60 px-4 py-2.5">
        <button type="button" onClick={() => setOpen((v) => !v)}
          className="flex w-full items-center gap-1.5 text-[11px] font-medium text-muted hover:text-ink">
          <Info className="h-3.5 w-3.5" aria-hidden /> What this model is and is not
          <ChevronDown className={cn("ml-auto h-3.5 w-3.5 transition-transform", open && "rotate-180")} aria-hidden />
        </button>
        {open && (
          <div className="mt-2 space-y-2 text-[11px] leading-relaxed text-muted">
            <p className="text-ink-2">{triage.disclaimer}</p>
            <ul className="list-disc space-y-1 pl-4">
              {triage.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
            <p>
              {triage.model_name} v{triage.model_version}, trained {fmtDate(triage.trained_at)} ·
              backbone {triage.backbone} · {triage.operating_point}
              {triage.inference_ms ? ` · scored in ${triage.inference_ms} ms` : ""}
            </p>
          </div>
        )}
      </div>
    </section>
  );
}
