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
          <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50/60 p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
              <Bot className="h-4 w-4 text-brand-700" />
              {patientLabel ? `Ask about ${patientLabel}` : "Ask about patients, schedules or hospital documents"}
            </div>
            <p className="mt-1 text-xs text-slate-500">Answers use only records and documents you are authorized to access, cite their sources, and separate database facts, document passages and model predictions.</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {prompts.map((p) => (
                <button key={p} onClick={() => ask(p)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-800">{p}</button>
              ))}
            </div>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] rounded-lg bg-slate-800 px-3 py-2 text-sm text-white">{t.query}</div>
            </div>
            {!t.response && !t.error && <Pending startedAt={t.startedAt} />}
            {t.error ? <ErrorState error={t.error} /> : null}
            {t.response && <ResponseCard r={t.response} onCite={(c) => setCitation(c)} />}
          </div>
        ))}
        <div ref={bottom} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(query); }}
        className="sticky bottom-0 mt-4 flex items-end gap-2 rounded-lg border border-slate-300 bg-white p-2 shadow-sm focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-500/20">
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
  const stage = s < 2 ? "Routing question and checking access" : s < 5 ? "Retrieving authorized records and documents" : "Composing a grounded answer";
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-500">
      <span className="dot-pulse flex gap-1"><span className="h-1.5 w-1.5 rounded-full bg-brand-600" /><span className="h-1.5 w-1.5 rounded-full bg-brand-600" /><span className="h-1.5 w-1.5 rounded-full bg-brand-600" /></span>
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
    { id: "trace" as const, label: "Trace", count: r.tool_calls.length, icon: Wrench },
  ];
  return (
    <article className="rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-100 px-4 py-2">
        {r.route.map((x) => <RouteBadge key={x} route={x} />)}
        <span className="text-[11px] text-slate-400">{r.routing_method === "llm" ? "LLM tool selection" : "deterministic routing"}</span>
        <span className="ml-auto flex items-center gap-1 text-[11px] text-slate-400">
          <Clock className="h-3 w-3" /> {(r.stage_ms.total / 1000).toFixed(1)}s · {r.provider === "extractive" ? "extractive (no LLM)" : r.model ?? r.provider}
        </span>
      </div>
      <div className="px-4 py-3">
        {r.insufficient_context && <div className="mb-2"><Notice tone="warning" icon={<Info className="h-3.5 w-3.5" />}>No authorized record or document answered this question.</Notice></div>}
        <Answer text={r.answer} onCite={cite} labels={labels} />
        {r.warnings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {r.warnings.map((w) => <Notice key={w} tone="warning" icon={<AlertTriangle className="h-3.5 w-3.5 shrink-0" />}>{w}</Notice>)}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1 border-t border-slate-100 px-3 py-1.5">
        {tabs.map((t) => (
          <button key={t.id} onClick={() => setTab(tab === t.id ? null : t.id)} disabled={t.count === 0 && t.id !== "trace"}
            className={cn("flex items-center gap-1 rounded px-2 py-1 text-xs disabled:opacity-40", tab === t.id ? "bg-slate-100 text-slate-800" : "text-slate-500 hover:bg-slate-50")}>
            <t.icon className="h-3.5 w-3.5" /> {t.label} <span className="tabular-nums text-slate-400">{t.count}</span>
            <ChevronDown className={cn("h-3 w-3 transition-transform", tab === t.id && "rotate-180")} />
          </button>
        ))}
      </div>
      {tab && <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-3 text-xs">{
        tab === "sources" ? <SourcesList r={r} onCite={onCite} /> :
          tab === "records" ? <RecordsList r={r} /> :
            tab === "model" ? <ModelOutput r={r} /> : <Trace r={r} />
      }</div>}
      <div className="border-t border-slate-100 px-4 py-2 text-[11px] leading-snug text-slate-400">
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
          <button onClick={() => onCite(c)} className="w-full rounded border border-slate-200 bg-white p-2 text-left hover:border-violet-300">
            <div className="flex items-center gap-2">
              <Badge tone="violet">{c.id}</Badge>
              <span className="font-medium text-slate-800">{c.document_title}</span>
              <span className="text-slate-400">v{c.version} · p.{c.page_start ?? "–"}</span>
            </div>
            <div className="mt-0.5 text-slate-500">{c.section_path}</div>
            <p className="mt-1 line-clamp-2 text-slate-600">{c.excerpt}</p>
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
        <li key={x.id} className="flex items-start gap-2 rounded border border-slate-200 bg-white px-2 py-1.5">
          <Badge tone="info">{x.id}</Badge>
          <div className="min-w-0">
            <div className="truncate text-slate-700">{x.label}</div>
            <div className="text-slate-400">{titleCase(x.source_type)} #{x.source_id}{x.date ? ` · ${x.date}` : ""}</div>
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
        <div key={p.prediction_type} className="rounded border border-slate-200 bg-white p-2">
          <div className="font-medium text-slate-800">{p.prediction_type === "readmission_30d" ? "30-day readmission model" : "Length-of-stay model"}</div>
          {p.status === "ok" ? (
            <div className="mt-1 text-slate-600">
              {p.prediction_type === "readmission_30d" ? pct(p.value) : `${p.value?.toFixed(1)} days`} ·{" "}
              <span className="font-mono">{p.model_name}@{p.model_version}</span> ({p.model_algorithm}) · trained {p.trained_at?.slice(0, 10)}
            </div>
          ) : <div className="text-slate-500">{p.reason}</div>}
        </div>
      ))}
      {r.similarity && (
        <div className="rounded border border-slate-200 bg-white p-2">
          <div className="font-medium text-slate-800">Patient similarity ({r.similarity.representation_version}, {r.similarity.metric})</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {r.similarity.results.map((s) => (
              <Link key={s.patient_id} href={`/patients/${s.patient_id}`} className="rounded bg-slate-100 px-1.5 py-0.5 hover:bg-brand-100">
                {s.mrn} · {s.similarity.toFixed(2)}
              </Link>
            ))}
          </div>
          <p className="mt-1 text-slate-400">{r.similarity.candidate_scope}</p>
        </div>
      )}
    </div>
  );
}

function Trace({ r }: { r: AIResponse }) {
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <div>
        <div className="mb-1 font-semibold text-slate-600">Tool calls (authorized server-side)</div>
        {r.tool_calls.length === 0 ? <p className="text-slate-400">No tools were needed.</p> : (
          <ul className="space-y-1">
            {r.tool_calls.map((t, i) => (
              <li key={i} className="flex items-center gap-2 rounded bg-white px-2 py-1 ring-1 ring-slate-200">
                <span className="font-mono text-slate-700">{t.name}</span>
                <StatusBadge status={t.status} />
                <span className="truncate text-slate-400">{t.summary}</span>
                <span className="ml-auto tabular-nums text-slate-400">{t.ms ?? "–"} ms</span>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-2 text-slate-500">Intents: {r.intents.join(", ")}</div>
      </div>
      <div>
        <div className="mb-1 font-semibold text-slate-600">Stage latency</div>
        <ul className="space-y-0.5">
          {Object.entries(r.stage_ms).map(([k, v]) => (
            <li key={k} className="flex justify-between"><span className="text-slate-500">{titleCase(k)}</span><span className="font-mono tabular-nums text-slate-700">{v.toFixed(0)} ms</span></li>
          ))}
        </ul>
        {Object.keys(r.retrieval).length > 0 && (
          <div className="mt-2 text-slate-500">
            Retrieval: {String(r.retrieval.mode ?? "")} · {String(r.retrieval.vector_candidates ?? 0)} vector + {String(r.retrieval.keyword_candidates ?? 0)} keyword candidates → {String(r.retrieval.returned ?? 0)} passages
            {r.retrieval.reranker ? ` · reranker ${String(r.retrieval.reranker)}` : ""}
          </div>
        )}
        {r.request_id && <div className="mt-1 font-mono text-slate-400">request {r.request_id}</div>}
      </div>
    </div>
  );
}
