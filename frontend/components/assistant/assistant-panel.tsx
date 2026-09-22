"use client";

import {
  AlertTriangle, ArrowRight, ArrowUp, BookOpen, Bot, CalendarDays, ChevronDown, ClipboardCheck, Clock, Cpu, Database, FileSearch, Gauge,
  History, Info, Pill, ShieldCheck, Users, Wrench,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Badge, RouteBadge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState, Notice } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { cn, pct, titleCase } from "@/lib/format";
import type { AIResponse, Citation } from "@/lib/types";

import { Answer } from "./answer";
import { destinationLabel, PrivacyPanel } from "./privacy";
import { SourceDrawer } from "./source-drawer";

interface Turn { id: number; query: string; response?: AIResponse; error?: unknown; startedAt: number }

type Prompt = [text: string, icon: React.ElementType];

const PATIENT_PROMPTS: Prompt[] = [
  ["Summarize this patient's medical history.", History],
  ["Why is this patient's readmission risk high?", Gauge],
  ["Compare this patient's treatment with our diabetes guideline.", BookOpen],
  ["Find similar historical patients and summarize relevant patterns.", Users],
  ["What were the major treatment changes?", Pill],
];
const GLOBAL_PROMPTS: Prompt[] = [
  ["What does our diabetes guideline say about monitoring?", BookOpen],
  ["Which medications are high-alert under MED-POL-004?", Pill],
  ["What appointments does Dr. Rao have?", CalendarDays],
  ["What must happen for high-risk patients at discharge?", ClipboardCheck],
];

function AssistantMark() {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-ai-tint text-ai ring-1 ring-inset ring-ai-edge" aria-hidden>
      <Bot className="h-4 w-4" />
    </span>
  );
}

export function AssistantPanel({ patientId, patientLabel, patientName, className }: {
  patientId?: number; patientLabel?: string; patientName?: string; className?: string;
}) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [citation, setCitation] = useState<Citation | null>(null);
  const latest = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  // Bring a newly asked question to the top of the view; its answer then grows beneath it.
  useEffect(() => {
    if (turns.length) latest.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [turns.length]);

  async function ask(text: string) {
    const q = text.trim();
    if (!q || busy) return;
    const id = Date.now();
    setTurns((t) => [...t, { id, query: q, startedAt: id }]);
    setQuery("");
    if (input.current) input.current.style.height = "";
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
    <div className={cn("flex min-h-[520px] flex-col", className)}>
      <div className="flex flex-1 flex-col gap-6 px-4 py-6 sm:px-6">
        {turns.length === 0 && (
          <div className="flex flex-1 flex-col items-center justify-center py-6 text-center">
            <span className="rise flex h-12 w-12 items-center justify-center rounded-2xl bg-ai-tint text-ai ring-1 ring-inset ring-ai-edge" aria-hidden>
              <Bot className="h-6 w-6" />
            </span>
            <h2 className="rise mt-4 text-[20px] font-semibold text-ink" style={{ "--i": 1 } as React.CSSProperties}>
              {patientName ? `What would you like to know about ${patientName}?` : "What would you like to know?"}
            </h2>
            <p className="rise mt-1.5 max-w-md text-sm leading-relaxed text-muted" style={{ "--i": 2 } as React.CSSProperties}>
              {patientLabel
                ? "Answers draw on this patient's records, labs, medicines and the hospital's documents, with a source for each claim."
                : "Answers draw on the hospital's own records and documents, with a source for each claim."}
            </p>
            <ul className="mt-7 grid w-full max-w-2xl gap-2 text-left sm:grid-cols-2">
              {prompts.map(([text, Icon], i) => (
                <li key={text} className="rise sm:[&:last-child:nth-child(odd)]:col-span-2" style={{ "--i": i + 3 } as React.CSSProperties}>
                  <button type="button" onClick={() => ask(text)}
                    className="group flex h-full w-full items-center gap-3 rounded-xl border border-line bg-panel px-4 py-3 text-left text-[13.5px] leading-snug text-ink-2 shadow-e1 transition-[border-color,box-shadow,transform,color] duration-200 hover:-translate-y-0.5 hover:border-accent-edge hover:text-ink hover:shadow-e2">
                    <Icon className="h-4 w-4 shrink-0 text-faint transition-colors group-hover:text-accent" aria-hidden />
                    <span className="flex-1">{text}</span>
                    <ArrowRight className="h-4 w-4 shrink-0 text-line-strong transition-[color,transform] duration-200 group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={t.id} ref={i === turns.length - 1 ? latest : undefined} className="scroll-mt-32 space-y-3">
            <div className="flex justify-end">
              <p className="animate-pop-in max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm leading-relaxed text-white shadow-e1">{t.query}</p>
            </div>
            <div className="flex items-start gap-3">
              <AssistantMark />
              <div className="min-w-0 flex-1">
                {!t.response && !t.error && <Pending startedAt={t.startedAt} />}
                {t.error ? <ErrorState error={t.error} /> : null}
                {t.response && <ResponseCard r={t.response} onCite={(c) => setCitation(c)} />}
              </div>
            </div>
          </div>
        ))}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); ask(query); }}
        className="sticky bottom-0 z-10 rounded-b-xl border-t border-line bg-panel/95 px-4 pb-3 pt-3 backdrop-blur-sm sm:px-6">
        <div className="flex items-end gap-2 rounded-xl border border-line-strong bg-panel p-1.5 pl-3.5 shadow-e1 transition-[border-color,box-shadow] duration-150 focus-within:border-accent focus-within:ring-3 focus-within:ring-accent/15">
          <textarea ref={input} value={query} rows={1} maxLength={2000}
            onChange={(e) => setQuery(e.target.value)}
            // Grows with the question up to about six lines, then scrolls.
            onInput={(e) => { const el = e.currentTarget; el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, 160)}px`; }}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(query); } }}
            placeholder={patientName ? `Ask about ${patientName}` : "Ask a question"}
            aria-label="Question" className="scroll-thin min-h-9 flex-1 resize-none bg-transparent py-2 text-sm leading-5 text-ink placeholder:text-faint focus:outline-none" />
          <Button type="submit" loading={busy} disabled={!query.trim()}>
            {!busy && <ArrowUp className="h-4 w-4" aria-hidden />} Ask
          </Button>
        </div>
        <p className="mt-1.5 px-1 text-[12px] text-faint">
          {patientLabel ? "" : "Mention an MRN such as P1024 to ask about one patient. "}Enter to ask, Shift + Enter for a new line.
        </p>
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
    <div role="status" className="animate-fade-in overflow-hidden rounded-xl border border-line bg-panel">
      <div className="flex items-center gap-3 px-4 py-3 text-sm text-ink-2">
        <span key={stage} className="animate-fade-in">{stage}…</span>
        <span className="ml-auto font-mono text-xs tabular-nums text-faint">{s}s</span>
      </div>
      <div className="h-0.5 overflow-hidden bg-raised" aria-hidden>
        <div className="progress-sweep h-full w-2/5 bg-gradient-to-r from-transparent via-accent to-transparent" />
      </div>
    </div>
  );
}

function ResponseCard({ r, onCite }: { r: AIResponse; onCite: (c: Citation) => void }) {
  const [tab, setTab] = useState<"sources" | "records" | "model" | "privacy" | "trace" | null>(null);
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
    ...(r.privacy ? [{ id: "privacy" as const, label: "Privacy", count: r.privacy.total, icon: ShieldCheck }] : []),
    { id: "trace" as const, label: "Details", count: r.tool_calls.length, icon: Wrench },
  ];
  const origins = [...new Set(r.route.map((x) => ORIGIN_LABEL[x]).filter(Boolean))];
  return (
    <article className="answer-reveal rounded-xl border border-line bg-panel shadow-e1">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line px-4 py-2.5">
        <span className="mr-1 text-xs font-medium text-ai">Assistant</span>
        <span className="text-xs text-muted">answered from</span>
        {origins.map((o) => <Badge key={o}>{o}</Badge>)}
        {r.privacy?.applied && (
          <button type="button" onClick={() => setTab(tab === "privacy" ? null : "privacy")}
            title={`Patient identifiers were replaced before the question went to ${destinationLabel(r.privacy.destination)}`}
            className="ml-1 flex items-center gap-1 rounded-full px-1.5 text-xs font-medium text-ok transition-colors duration-150 hover:bg-ok-tint">
            <ShieldCheck className="h-3.5 w-3.5" aria-hidden /> Identifiers hidden
          </button>
        )}
        <span className="ml-auto flex items-center gap-1 text-xs text-muted">
          <Clock className="h-3 w-3" aria-hidden /> {(r.stage_ms.total / 1000).toFixed(1)} s
        </span>
      </div>
      <div className="px-4 py-3.5">
        {r.insufficient_context && <div className="mb-2"><Notice tone="warning" icon={<Info className="h-3.5 w-3.5" />}>No record or document answered this question.</Notice></div>}
        <Answer text={r.answer} onCite={cite} labels={labels} />
        {r.warnings.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {r.warnings.map((w) => <Notice key={w} tone="warning" icon={<AlertTriangle className="h-3.5 w-3.5 shrink-0" />}>{w}</Notice>)}
          </div>
        )}
      </div>
      <div className="flex flex-wrap gap-1 border-t border-line px-2.5 py-2">
        {tabs.map((t) => (
          <button key={t.id} type="button" onClick={() => setTab(tab === t.id ? null : t.id)} disabled={t.count === 0 && t.id !== "trace" && t.id !== "privacy"}
            aria-expanded={tab === t.id}
            className={cn("flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-150 disabled:opacity-40",
              tab === t.id ? "bg-raised text-ink" : "text-muted hover:bg-sunken hover:text-ink")}>
            <t.icon className="h-3.5 w-3.5" aria-hidden /> {t.label}
            <span className={cn("tabular rounded-full px-1.5 text-[11px] leading-[18px]", tab === t.id ? "bg-panel text-ink-2" : "bg-raised text-muted")}>{t.count}</span>
            <ChevronDown className={cn("h-3 w-3 transition-transform duration-200", tab === t.id && "rotate-180")} aria-hidden />
          </button>
        ))}
      </div>
      {tab && <div key={tab} className="animate-fade-in border-t border-line bg-sunken/50 px-4 py-3 text-xs">{
        tab === "sources" ? <SourcesList r={r} onCite={onCite} /> :
          tab === "records" ? <RecordsList r={r} /> :
            tab === "model" ? <ModelOutput r={r} /> :
              tab === "privacy" && r.privacy ? <PrivacyPanel privacy={r.privacy} /> : <Trace r={r} />
      }</div>}
      <div className="space-y-0.5 rounded-b-xl border-t border-line px-4 py-2.5 text-[11px] leading-snug text-faint">
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
          <button type="button" onClick={() => onCite(c)} className="w-full rounded-lg border border-line bg-panel p-2.5 text-left shadow-e1 transition-[border-color,box-shadow] duration-150 hover:border-ai-edge hover:shadow-e2">
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
