"use client";

import { AlertTriangle, Bot, ChevronDown, Clock, CornerDownLeft, Cpu, Database, FileSearch, Info, Wrench } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Badge, RouteBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { cn, pct, titleCase } from "@/lib/format";
import type { AIResponse, Citation } from "@/lib/types";

import { Answer } from "./answer";
import { SourceDrawer } from "./source-drawer";

interface Turn { id: number; query: string; response?: AIResponse; error?: unknown; startedAt: number }

const PATIENT_PROMPTS = [
  "Summarize this patient's medical history.",
  "Why is this patient's readmission risk high?",
  "Compare this patient's treatment with our diabetes guideline.",
  "Find similar historical patients and summarize relevant patterns.",
  "What were the major treatment changes?",
];
const GLOBAL_PROMPTS = [
  "What does our diabetes guideline say about monitoring?",
  "Which medications are high-alert under MED-POL-004?",
  "What appointments does Dr. Rao have?",
  "What must happen for high-risk patients at discharge?",
];

export function AssistantPanel({ patientId, patientLabel, compact }: { patientId?: number; patientLabel?: string; compact?: boolean }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [citation, setCitation] = useState<Citation | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [turns]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, query: q, startedAt: id }]);
    setQuery("");
    setBusy(true);
    try {
      const response = await api<AIResponse>("/ai/query", { method: "POST", json: { query: q, patient_id: patientId ?? null } });
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, response } : x)));
    } catch (error) {
      setTurns((t) => t.map((x) => (x.id === id ? { ...x, error } : x)));
    } finally {
      setBusy(false);
    }
  }

  const prompts = patientId ? PATIENT_PROMPTS : GLOBAL_PROMPTS;
  return (
    <div className="flex flex-col">
      <div className={cn("space-y-4", compact ? "" : "min-h-[200px]")}>
        {turns.length === 0 && (
          <div className="rounded-lg border border-dashed border-line-strong bg-sunken/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-ink-2">
              <Bot className="h-4 w-4 text-accent" />
              {patientLabel ? `Ask about ${patientLabel}` : "Ask about patients, schedules or hospital documents"}
            </div>
            <p className="mt-1 text-xs text-muted">Answers come from the hospital&apos;s own records and documents, and every answer shows the sources it used.</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {prompts.map((p) => (
                <button key={p} onClick={() => ask(p)} className="rounded-full border border-line bg-panel px-3 py-1.5 text-xs text-ink-2 shadow-e1 transition-all duration-150 hover:-translate-y-px hover:border-accent-edge hover:bg-accent-tint/60 hover:text-accent">{p}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-md bg-accent px-3.5 py-2 text-sm leading-relaxed text-white shadow-e1">{t.query}</div>
            </div>
            {!t.response && !t.error && <Pending startedAt={t.startedAt} />}
            {t.error ? <ErrorState error={t.error} /> : null}
            {t.response && <ResponseCard r={t.response} onCite={(c) => setCitation(c)} />}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(query); }}
        className="sticky bottom-0 mt-4 flex items-end gap-2 rounded-xl border border-line-strong bg-panel p-2 shadow-e2 transition-[border-color,box-shadow] focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/12">
        <textarea value={query} onChange={(e) => setQuery(e.target.value)} rows={2} maxLength={2000}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(query); } }}
          placeholder={patientLabel ? `Question about ${patientLabel}…` : "Ask a question… (mention an MRN such as P1024 for patient questions)"}
          aria-label="Question" className="max-h-40 min-h-[40px] flex-1 resize-y border-0 bg-transparent px-1 py-1 text-sm focus:outline-none" />
        <Button type="submit" loading={busy} disabled={!query.trim()}><CornerDownLeft className="h-4 w-4" /> Ask</Button>
      </form>
      <SourceDrawer citation={citation} onClose={() => setCitation(null)} />
    </div>
  );
}

function Pending({ startedAt }: { startedAt: number }) {
  const [now, setNow] = useState(startedAt);
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, []);
  const s = Math.round((now - startedAt) / 1000);
  const stage = s < 2 ? "Understanding the question" : s < 5 ? "Looking through records and documents" : "Writing the answer";
  return (
    <div className="flex items-center gap-3 rounded-lg border border-line bg-panel p-3 text-sm text-muted">
      <span className="dot-pulse flex gap-1"><span className="h-1.5 w-1.5 rounded-full bg-accent" /><span className="h-1.5 w-1.5 rounded-full bg-accent" /><span className="h-1.5 w-1.5 rounded-full bg-accent" /></span>
      {stage}… <span className="ml-auto font-mono text-xs tabular-nums">{s}s</span>
    </div>
  );
}

function ResponseCard({ r, onCite }: { r: AIResponse; onCite: (c: Citation) => void }) {
  const [tab, setTab] = useState<"sources" | "records" | "model" | "trace" | null>(null);
  const labels: Record<string, string> = Object.fromEntries([
    ...r.citations.map((c) => [c.id, `${c.document_title} — ${c.section_path}`]),
    ...r.record_refs.map((x) => [x.id, `${titleCase(x.source_type)}: ${x.label}${x.date ? ` (${x.date})` : ""}`]),
  ]);
  const cite = (id: string) => {
    const c = r.citations.find((x) => x.id === id);
    if (c) onCite(c);
    else setTab("records");
  };
  const tabs = [
    { id: "sources" as const, label: "Document sources", count: r.citations.length, icon: FileSearch },
    { id: "records" as const, label: "Database records", count: r.record_refs.length, icon: Database },
    { id: "model" as const, label: "Model output", count: r.predictions.length + (r.similarity ? 1 : 0), icon: Cpu },
    { id: "trace" as const, label: "Details", count: r.tool_calls.length, icon: Wrench },
  ];
  const origins = [...new Set(r.route.map((x) => ORIGIN_LABEL[x]).filter(Boolean))];
  return (
    <article className="rounded-lg border border-line bg-panel">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2">
        <span className="text-xs text-muted">Answered from</span>
        {origins.map((o) => <Badge key={o}>{o}</Badge>)}
        <span className="ml-auto flex items-center gap-1 text-xs text-muted">
          <Clock className="h-3 w-3" aria-hidden /> {(r.stage_ms.total / 1000).toFixed(1)} s
        </span>
      </div>
      <div className="px-4 py-3">
        {r.insufficient_context && <div className="mb-2"><Notice tone="warning" icon={<Info className="h-3.5 w-3.5" />}>No record or document answered this question.</Notice></div>}
        <Answer text={r.answer} onCite={cite} labels={labels} />
        {r.warnings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {r.warnings.map((w) => <Notice key={w} tone="warning" icon={<AlertTriangle className="h-3.5 w-3.5 shrink-0" />}>{w}</Notice>)}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1 border-t border-line px-3 py-1.5">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(tab === t.id ? null : t.id)} disabled={t.count === 0 && t.id !== "trace"}
            className={cn("flex items-center gap-1 rounded px-2 py-1 text-xs disabled:opacity-40", tab === t.id ? "bg-raised text-ink" : "text-muted hover:bg-sunken")}>
            <t.icon className="h-3.5 w-3.5" /> {t.label} <span className="tabular-nums text-faint">{t.count}</span>
            <ChevronDown className={cn("h-3 w-3 transition-transform", tab === t.id && "rotate-180")} />
          </button>
        ))}
      </div>
      {tab && <div className="border-t border-line bg-sunken/50 px-4 py-3 text-xs">{
        tab === "sources" ? <SourcesList r={r} onCite={onCite} /> :
          tab === "records" ? <RecordsList r={r} /> :
            tab === "model" ? <ModelOutput r={r} /> : <Trace r={r} />
      }</div>}
      <div className="border-t border-line px-4 py-2 text-[11px] leading-snug text-faint">
        {r.limitations.map((l) => <p key={l}>{l}</p>)}
        <p>{r.disclaimer}</p>
      </div>
    </article>
  );
}

function SourcesList({ r, onCite }: { r: AIResponse; onCite: (c: Citation) => void }) {
  return (
    <ul className="space-y-2">
      {r.citations.map((c) => (
        <li key={c.id}>
          <button onClick={() => onCite(c)} className="w-full rounded border border-line bg-panel p-2 text-left hover:border-ai-edge">
            <div className="flex items-center gap-2">
              <Badge tone="violet">{c.id}</Badge>
              <span className="font-medium text-ink">{c.document_title}</span>
              <span className="text-faint">v{c.version} · p.{c.page_start ?? "–"}</span>
            </div>
            <div className="mt-0.5 text-muted">{c.section_path}</div>
            <p className="mt-1 line-clamp-2 text-ink-2">{c.excerpt}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}

function RecordsList({ r }: { r: AIResponse }) {
  return (
    <ul className="grid gap-1 sm:grid-cols-2">
      {r.record_refs.map((x) => (
        <li key={x.id} className="flex items-start gap-2 rounded border border-line bg-panel px-2 py-1.5">
          <Badge tone="info">{x.id}</Badge>
          <div className="min-w-0">
            <div className="truncate text-ink-2">{x.label}</div>
            <div className="text-faint">{titleCase(x.source_type)} #{x.source_id}{x.date ? ` · ${x.date}` : ""}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function ModelOutput({ r }: { r: AIResponse }) {
  return (
    <div className="space-y-2">
      {r.predictions.map((p) => (
        <div key={p.prediction_type} className="rounded border border-line bg-panel p-2">
          <div className="font-medium text-ink">{p.prediction_type === "readmission_30d" ? "30-day readmission model" : "Length-of-stay model"}</div>
          {p.status === "ok" ? (
            <div className="mt-1 text-ink-2">
              {p.prediction_type === "readmission_30d" ? pct(p.value) : `${p.value?.toFixed(1)} days`} ·{" "}
              <span className="font-mono">{p.model_name}@{p.model_version}</span> ({p.model_algorithm}) · trained {p.trained_at?.slice(0, 10)}
            </div>
          ) : <div className="text-muted">{p.reason}</div>}
        </div>
      ))}
      {r.similarity && (
        <div className="rounded border border-line bg-panel p-2">
          <div className="font-medium text-ink">Patient similarity ({r.similarity.representation_version}, {r.similarity.metric})</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {r.similarity.results.map((s) => (
              <Link key={s.patient_id} href={`/patients/${s.patient_id}`} className="rounded bg-raised px-1.5 py-0.5 hover:bg-accent-tint">
                {s.mrn} · {s.similarity.toFixed(2)}
              </Link>
            ))}
          </div>
          <p className="mt-1 text-faint">{r.similarity.candidate_scope}</p>
        </div>
      )}
    </div>
  );
}

const ORIGIN_LABEL: Record<string, string> = {
  SQL: "Hospital records", RAG: "Documents", ML: "Predictions", SIMILARITY: "Similar patients", LLM: "Assistant",
};

function Trace({ r }: { r: AIResponse }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div className="flex flex-wrap items-center gap-1.5 lg:col-span-2">
        <span className="font-semibold text-ink-2">Route</span>
        {r.route.map((x) => <RouteBadge key={x} route={x} />)}
        <span className="text-muted">
          {r.routing_method === "llm" ? "LLM tool selection" : "deterministic routing"} ·{" "}
          {r.provider === "extractive" ? "extractive (no LLM)" : r.model ?? r.provider}
        </span>
      </div>
      <div>
        <div className="mb-1 font-semibold text-ink-2">Tool calls (authorized server-side)</div>
        {r.tool_calls.length === 0 ? <p className="text-faint">No tools were needed.</p> : (
          <ul className="space-y-1">
            {r.tool_calls.map((t, i) => (
              <li key={i} className="flex items-center gap-2 rounded bg-panel px-2 py-1 ring-1 ring-line">
                <span className="font-mono text-ink-2">{t.name}</span>
                <StatusBadge status={t.status} />
                <span className="truncate text-faint">{t.summary}</span>
                <span className="ml-auto tabular-nums text-faint">{t.ms ?? "–"} ms</span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-2 text-muted">Intents: {r.intents.join(", ")}</div>
      </div>
      <div>
        <div className="mb-1 font-semibold text-ink-2">Stage latency</div>
        <ul className="space-y-0.5">
          {Object.entries(r.stage_ms).map(([k, v]) => (
            <li key={k} className="flex justify-between"><span className="text-muted">{titleCase(k)}</span><span className="font-mono tabular-nums text-ink-2">{v.toFixed(0)} ms</span></li>
          ))}
        </ul>
        {Object.keys(r.retrieval).length > 0 && (
          <div className="mt-2 text-muted">
            Retrieval: {String(r.retrieval.mode ?? "")} · {String(r.retrieval.vector_candidates ?? 0)} vector + {String(r.retrieval.keyword_candidates ?? 0)} keyword candidates → {String(r.retrieval.returned ?? 0)} passages
            {r.retrieval.reranker ? ` · reranker ${String(r.retrieval.reranker)}` : ""}
          </div>
        )}
        {r.request_id && <div className="mt-1 font-mono text-faint">request {r.request_id}</div>}
      </div>
    </div>
  );
}
