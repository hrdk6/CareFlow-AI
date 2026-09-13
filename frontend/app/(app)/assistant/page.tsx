"use client";

import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { AssistantPanel } from "@/components/assistant/assistant-panel";
import { Card, PageHeader } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { PERMS, useAuth } from "@/lib/auth";
import { useApi } from "@/lib/hooks";
import type { Page, PatientListItem } from "@/lib/types";

interface LLMBackup { provider: string; model: string | null; reachable: boolean | null }
interface AIStatus { provider: string; model: string | null; reachable: boolean | null; fallbacks: LLMBackup[]; tool_calling: boolean; embedding_model: string; reranker: string; injection_policy: string }

export default function AssistantPage() {
  const { can } = useAuth();
  const [patientId, setPatientId] = useState<string>("");
  const { data: patients } = useApi<Page<PatientListItem>>("/patients?limit=200");
  const { data: status } = useApi<AIStatus>("/ai/status");
  const patient = patients?.items.find((p) => String(p.id) === patientId);
  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_300px]">
      <div>
        <PageHeader title="AI assistant" subtitle="Ask about patients, schedules and hospital guidelines. Every answer shows where it came from." />
        <Card>
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted">Patient context</span>
            <Select value={patientId} onChange={(e) => setPatientId(e.target.value)} placeholder="None (general questions)" className="max-w-xs" aria-label="Patient context"
              options={(patients?.items ?? []).map((p) => ({ value: p.id, label: `${p.full_name} (${p.mrn})` }))} />
          </div>
          <AssistantPanel key={patientId} patientId={patient?.id} patientLabel={patient ? `${patient.full_name} (${patient.mrn})` : undefined} />
        </Card>
      </div>
      <aside className="space-y-4 xl:pt-14">
        <Card title="How it works">
          <ol className="space-y-3 text-[13px] leading-relaxed text-ink-2">
            <li><b className="font-medium text-ink">Ask in plain language.</b> About a patient, a schedule or a hospital guideline.</li>
            <li><b className="font-medium text-ink">Pick a patient for context.</b> Questions then focus on that patient&apos;s records, labs and medicines.</li>
            <li><b className="font-medium text-ink">Every answer shows its sources.</b> Select a source marker to read the passage or record behind it.</li>
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
        <p className="flex gap-1.5 text-xs leading-relaxed text-muted"><ShieldCheck className="h-4 w-4 shrink-0" /> The assistant retrieves, summarises and explains. It does not diagnose or choose treatments.</p>
      </aside>
    </div>
  );
}
