"use client";

import { AlertTriangle, CalendarPlus, CheckCircle2, CircleDashed, CircleHelp, MinusCircle, ShieldCheck, XCircle } from "lucide-react";
import Link from "next/link";

import { CitationChip } from "@/components/assistant/answer";
import { Badge, type Tone } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { DataTable } from "@/components/ui/table";
import { cn, fmtDate, pct, titleCase } from "@/lib/format";
import type { CheckStatus, DischargeDraft, InvestigationLine, MedicationLine, PolicyCheck } from "@/lib/types";

type OnCite = (id: string) => void;

export function Chips({ ids, labels, onCite }: { ids: string[]; labels: Record<string, string>; onCite: OnCite }) {
  if (!ids.length) return null;
  return <span className="inline-flex flex-wrap">{ids.map((id) => <CitationChip key={id} id={id} label={labels[id]} onClick={onCite} />)}</span>;
}

const CHECK: Record<CheckStatus, { icon: React.ElementType; label: string; className: string }> = {
  met: { icon: CheckCircle2, label: "Done", className: "text-ok" },
  not_met: { icon: XCircle, label: "Missing", className: "text-high" },
  to_confirm: { icon: CircleDashed, label: "To confirm", className: "text-warn" },
  unknown: { icon: CircleHelp, label: "Unknown", className: "text-faint" },
  not_applicable: { icon: MinusCircle, label: "Not required", className: "text-faint" },
};

/** A readmission criterion reads as a yes/no question: "met" means the risk factor is present. */
const CRITERION: Record<CheckStatus, { label: string; tone: Tone }> = {
  met: { label: "Yes", tone: "warning" }, not_met: { label: "No", tone: "neutral" }, unknown: { label: "Unknown", tone: "neutral" },
  to_confirm: { label: "Check", tone: "warning" }, not_applicable: { label: "n/a", tone: "neutral" },
};

export function RiskScreenCard({ risk, labels, onCite }: { risk: DischargeDraft["risk"]; labels: Record<string, string>; onCite: OnCite }) {
  return (
    <Card title="Readmission risk screening" subtitle="Discharge policy, section 3: high risk if any criterion applies">
      <div className={cn("mb-4 flex items-start gap-2.5 rounded-lg border px-3 py-2.5",
        risk.high_risk ? "border-warn-edge bg-warn-tint" : "border-ok-edge bg-ok-tint")}>
        {risk.high_risk
          ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden />
          : <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />}
        <div className="min-w-0 text-[13px] leading-snug">
          <p className="font-semibold text-ink">{risk.high_risk ? "High risk under the discharge policy" : "Not high risk under the discharge policy"}</p>
          <p className="mt-0.5 text-ink-2">{risk.high_risk
            ? "Transitional care applies: follow-up within 7 days, a nurse call within 72 hours and a pharmacist review."
            : "Follow-up within 14 days."}</p>
        </div>
      </div>
      <ul className="space-y-3">
        {risk.criteria.map((c, i) => (
          <li key={c.key} className="stagger-in flex gap-3" style={{ "--i": i } as React.CSSProperties}>
            <Badge tone={CRITERION[c.status].tone} className="mt-0.5 w-[62px] shrink-0 justify-center self-start">{CRITERION[c.status].label}</Badge>
            <div className="min-w-0 text-[13px]">
              <p className="font-medium leading-snug text-ink">{c.label}</p>
              <p className="mt-0.5 leading-snug text-muted">{c.detail} <Chips ids={c.refs} labels={labels} onCite={onCite} /></p>
            </div>
          </li>
        ))}
      </ul>
      {risk.model && (
        <div className="mt-4 rounded-lg bg-sunken px-3 py-2.5 text-xs text-muted">
          <div className="flex items-baseline justify-between gap-2">
            <span className="font-medium text-ink-2">Model estimate</span>
            <span className="tabular font-display text-[18px] font-semibold text-ink">{pct(risk.model.probability)}</span>
          </div>
          <div className="relative mt-2 h-1.5 rounded-full bg-raised-2" aria-hidden>
            <div className="absolute inset-y-0 left-0 rounded-full bg-warn/70" style={{ width: `${Math.min(100, risk.model.probability / 0.5 * 100)}%` }} />
            <div className="absolute -top-1 h-3.5 w-0.5 rounded bg-ink" style={{ left: `${Math.min(100, risk.model.threshold / 0.5 * 100)}%` }} title="Alert threshold" />
          </div>
          <p className="mt-1.5">Alert threshold {pct(risk.model.threshold)} · <span className="font-mono">{risk.model.model}</span></p>
          {risk.model.top_factors.length > 0 && <p className="mt-0.5">Largest contributions: {risk.model.top_factors.join(", ")}.</p>}
        </div>
      )}
    </Card>
  );
}

export function ChecklistCard({ checklist, labels, onCite, patientId }: {
  checklist: PolicyCheck[]; labels: Record<string, string>; onCite: OnCite; patientId: number;
}) {
  const open = checklist.filter((c) => c.status === "not_met" || c.status === "to_confirm").length;
  return (
    <Card title="Before the patient leaves" subtitle={open ? `${open} item${open === 1 ? "" : "s"} still to do or confirm` : "Everything the policy requires is in place"}>
      <ul className="space-y-3">
        {checklist.map((c, i) => {
          const s = CHECK[c.status];
          return (
            <li key={c.key} className="stagger-in flex gap-2.5" style={{ "--i": i } as React.CSSProperties}>
              <s.icon className={cn("mt-0.5 h-4 w-4 shrink-0", s.className)} aria-hidden />
              <div className="min-w-0 text-[13px]">
                <p className="leading-snug text-ink"><span className="font-medium">{c.label}</span> <span className={cn("text-xs font-medium", s.className)}>· {s.label}</span></p>
                <p className="mt-0.5 leading-snug text-muted">{c.detail} <Chips ids={c.refs} labels={labels} onCite={onCite} /></p>
                {c.key === "follow_up" && c.status === "not_met" && (
                  <Link href={`/appointments?patient=${patientId}`} className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-accent hover:text-accent-strong">
                    <CalendarPlus className="h-3.5 w-3.5" aria-hidden /> Book the appointment
                  </Link>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

const MED_STATUS: Record<MedicationLine["status"], { label: string; tone: Tone }> = {
  changed: { label: "Changed", tone: "warning" }, new: { label: "Started", tone: "info" }, stopped: { label: "Stopped", tone: "danger" },
  held_resumed: { label: "Held, resumed", tone: "violet" }, continued: { label: "Continued", tone: "neutral" },
  inpatient_only: { label: "In hospital only", tone: "neutral" },
};

export function ReconciliationTable({ medications, labels, onCite }: { medications: MedicationLine[]; labels: Record<string, string>; onCite: OnCite }) {
  return (
    <DataTable dense rows={medications.map((m) => ({ ...m, id: m.medication }))} empty="No medicines on record for this admission"
      columns={[
        { key: "medication", header: "Medicine", render: (m) => (
          <div className="min-w-[150px]">
            <span className="font-medium text-ink">{m.medication}</span>{" "}
            {m.high_alert && <Badge tone="danger">High-alert</Badge>}
            <div className="text-xs text-muted">{titleCase(m.drug_class)}</div>
          </div>) },
        { key: "before", header: "On admission", render: (m) => <span className="text-xs">{m.before ?? "—"}</span> },
        { key: "after", header: "At discharge", render: (m) => <span className={cn("text-xs", m.status === "changed" && "font-semibold text-ink")}>{m.after ?? "—"}</span> },
        { key: "status", header: "Change", render: (m) => <Badge tone={MED_STATUS[m.status].tone} dot={m.status !== "continued" && m.status !== "inpatient_only"}>{MED_STATUS[m.status].label}</Badge> },
        { key: "reason", header: "Reason", render: (m) => <span className="text-xs text-muted">{m.reason ?? "—"}</span> },
        { key: "src", header: "Sources", render: (m) => <Chips ids={m.refs} labels={labels} onCite={onCite} /> },
      ]} />
  );
}

const value = (v: number | null, unit: string | null) => (v === null ? "—" : `${v}${unit ? ` ${unit}` : ""}`);

export function InvestigationsTable({ investigations, labels, onCite }: { investigations: InvestigationLine[]; labels: Record<string, string>; onCite: OnCite }) {
  return (
    <DataTable dense rows={investigations.map((i) => ({ ...i, id: i.test_code }))} empty="No results were recorded during this admission"
      columns={[
        { key: "test", header: "Test", render: (i) => <span className="font-medium text-ink">{i.test_name}</span> },
        { key: "first", header: "First", render: (i) => <span className="tabular text-xs">{value(i.first, i.unit)} <span className="text-faint">· {fmtDate(i.first_at)}</span></span> },
        { key: "last", header: "Latest", render: (i) => i.results > 1
          ? <span className="tabular text-xs">{value(i.last, i.unit)} <span className="text-faint">· {fmtDate(i.last_at)}</span></span>
          : <span className="text-xs text-faint">single result</span> },
        { key: "flag", header: "Worst", render: (i) => <Badge tone={i.worst_flag === "critical" ? "danger" : i.worst_flag === "normal" ? "neutral" : "warning"} dot={i.worst_flag !== "normal"}>{titleCase(i.worst_flag)}</Badge> },
        { key: "n", header: "Results", render: (i) => <span className="tabular text-xs">{i.results}</span> },
        { key: "src", header: "Sources", render: (i) => <Chips ids={i.refs} labels={labels} onCite={onCite} /> },
      ]} />
  );
}
