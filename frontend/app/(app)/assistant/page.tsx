"use client";

import { MessageSquareText, Quote, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { Card, PageHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { PERMS, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Page, PatientListItem } from "@/lib/types";

interface LLMBackup { provider: string; model: string | null; reachable: boolean | null }
interface AIStatus { provider: string; model: string | null; reachable: boolean | null; fallbacks: LLMBackup[]; tool_calling: boolean; embedding_model: string; reranker: string; injection_policy: string }

const STEPS: [React.ElementType, string, string][] = [
  [MessageSquareText, "Ask in plain language.", "About a patient, a schedule or a hospital guideline."],
  [UserRound, "Pick a patient for context.", "Questions then focus on that patient's records, labs and medicines."],
  [Quote, "Every answer shows its sources.", "Select a source marker to read the passage or record behind it."],
];

export default function AssistantPage() {
  const { can } = useAuth();
  const [patientId, setPatientId] = useState<string>("");
  const { data: patients } = useApi<Page<PatientListItem>>("/patients?limit=200");
  const { data: status } = useApi<AIStatus>("/ai/status");
  const patient = patients?.items.find((p) => String(p.id) === patientId);
  return (
    <>
      <PageHeader title="AI assistant" subtitle="Ask about patients, schedules and hospital guidelines. Every answer shows where it came from." />
      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
        <section className="min-w-0 rounded-xl border border-line bg-panel shadow-e1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2 rounded-t-xl border-b border-line px-4 py-3 sm:px-6">
            <label htmlFor="assistant-patient" className="flex items-center gap-2 text-[13px] font-medium text-ink-2">
              <UserRound className="h-4 w-4 text-faint" aria-hidden /> Patient
            </label>
            <Select id="assistant-patient" value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="None, general questions" className="w-full sm:w-72"
              options={(patients?.items ?? []).map((p) => ({ value: p.id, label: `${p.full_name} (${p.mrn})` }))} />
            <p className="text-[12px] text-muted">
              {patient ? "Answers focus on this patient's record." : "Choose a patient to ask about their record."}
            </p>
          </div>
          {/* Changing the patient starts a fresh conversation. */}
          <AssistantPanel key={patientId} patientId={patient?.id} patientName={patient?.full_name.split(" ")[0]}
            patientLabel={patient ? `${patient.full_name} (${patient.mrn})` : undefined} className="xl:min-h-[calc(100vh-300px)]" />
        </section>
        <aside className="space-y-4 xl:sticky xl:top-24">
          <Card title="How it works">
            <ol className="space-y-4">
              {STEPS.map(([Icon, lead, rest]) => (
                <li key={lead} className="flex gap-3">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-tint text-accent" aria-hidden>
                    <Icon className="h-3.5 w-3.5" />
                  </span>
                  <p className="text-[13px] leading-relaxed text-ink-2"><b className="font-medium text-ink">{lead}</b> {rest}</p>
                </li>
              ))}
            </ol>
          </Card>
          {status && can(PERMS.observe) && (
            <Card title="Configuration" subtitle="Visible to administrators">
              <dl className="space-y-1.5 text-xs">
                <div className="flex justify-between"><dt className="text-muted">LLM provider</dt><dd className="font-mono">{status.provider}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Model</dt><dd className="font-mono">{status.model ?? "none (extractive)"}</dd></div>
                {status.reachable !== null && <div className="flex justify-between"><dt className="text-muted">Reachable</dt><dd>{status.reachable ? "yes" : status.fallbacks.length ? "no — uses backup" : "no — falls back to extractive"}</dd></div>}
                {status.fallbacks.map((f, i) => (
                  <div key={`${f.provider}-${f.model}`} className="flex justify-between gap-2"><dt className="text-muted">{i === 0 ? "Backups" : ""}</dt><dd className="truncate font-mono">{f.provider} · {f.model}{f.reachable === false ? " (unreachable)" : ""}</dd></div>
                ))}
                <div className="flex justify-between"><dt className="text-muted">Embeddings</dt><dd className="truncate pl-2 font-mono">{status.embedding_model}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Reranker</dt><dd className="truncate pl-2 font-mono">{status.reranker}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Injection policy</dt><dd>{status.injection_policy}</dd></div>
              </dl>
            </Card>
          )}
          <p className="flex gap-2 px-1 text-xs leading-relaxed text-muted">
            <ShieldCheck className="h-4 w-4 shrink-0 text-faint" aria-hidden /> The assistant retrieves, summarises and explains. It does not diagnose or choose treatments.
          </p>
        </aside>
      </div>
    </>
  );
}
