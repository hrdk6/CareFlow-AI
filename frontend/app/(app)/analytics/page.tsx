"use client";

import { useState } from "react";

import { BarList, ConfusionMatrix, LineChart } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Card, PageHeader, StatCard } from "@/components/ui/card";
import { ErrorState, Notice, Skeleton } from "@/components/ui/feedback";
import { Tabs } from "@/components/ui/tabs";
import { num } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { ModelCard } from "@/lib/types";

type Metrics = Record<string, number | Record<string, number> | [number, number][] | { mean_predicted: number; observed_rate: number }[]>;

export default function AnalyticsPage() {
  const [tab, setTab] = useState<"readmission" | "los" | "rag" | "similarity">("readmission");
  const { data: cards, error, loading, reload } = useApi<ModelCard[]>("/ml/models");
  const readmission = cards?.find((c) => c.model_name === "readmission_30d" && c.is_active);
  const los = cards?.find((c) => c.model_name === "length_of_stay" && c.is_active);
  return (
    <>
      <PageHeader title="Model performance" subtitle="How well the prediction models and the assistant's search perform on held-out data. Every figure comes from the evaluation scripts." />
      <Tabs active={tab} onChange={setTab} tabs={[
        { id: "readmission", label: "Readmission model" }, { id: "los", label: "Length-of-stay model" },
        { id: "rag", label: "RAG evaluation" }, { id: "similarity", label: "Patient similarity" },
      ]} />
      <div className="mt-4">
        {error && <ErrorState error={error} onRetry={reload} />}
        {loading && !cards && <Skeleton lines={8} />}
        {tab === "readmission" && readmission && <ReadmissionCard card={readmission} />}
        {tab === "los" && los && <LosCard card={los} />}
        {tab === "rag" && <RagEval />}
        {tab === "similarity" && <SimilarityEval />}
      </div>
    </>
  );
}

function ModelHeader({ card }: { card: ModelCard }) {
  const d = card.dataset as { name: string; license: string; rows_used: number; sha256: string; rows_excluded: Record<string, number> };
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-sm font-semibold text-ink">{card.model_name}@{card.version}</span>
        <Badge tone="success">active</Badge><Badge tone="info">{card.algorithm}</Badge>
        <span className="text-xs text-muted">trained {card.trained_at.slice(0, 10)}</span>
      </div>
      <p className="mt-2 text-sm text-ink-2">{card.intended_use}</p>
      <div className="mt-2 text-xs text-muted">
        Dataset: {d.name} ({d.license}) · {d.rows_used.toLocaleString()} encounters used · excluded {Object.entries(d.rows_excluded).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join(", ")} · sha256 <span className="font-mono">{d.sha256.slice(0, 12)}…</span>
      </div>
      <div className="mt-1 text-xs text-muted">Split: {String((card.extra.split as { method: string })?.method)} · selection by {String(card.extra.selection_metric)}</div>
    </Card>
  );
}

function ReadmissionCard({ card }: { card: ModelCard }) {
  const t = card.metrics.test as unknown as Metrics & { confusion_matrix: { tn: number; fp: number; fn: number; tp: number } };
  const base = card.metrics.baseline_validation as Record<string, number>;
  const cal = card.extra.calibration as Record<string, number>;
  const ablation = card.leakage_ablation as { grouped_split_test: Record<string, number>; row_split_test: Record<string, number>; note: string };
  return (
    <div className="space-y-4">
      <ModelHeader card={card} />
      <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-6">
        <StatCard label="ROC-AUC (test)" value={num(t.roc_auc as number, 3)} hint="0.5 = chance" />
        <StatCard label="PR-AUC (test)" value={num(t.pr_auc as number, 3)} hint={`baseline ${num(t.prevalence as number, 3)}`} />
        <StatCard label="Precision" value={num(t.precision as number, 3)} hint={`at threshold ${num(t.threshold as number, 3)}`} />
        <StatCard label="Recall" value={num(t.recall as number, 3)} />
        <StatCard label="F1" value={num(t.f1 as number, 3)} />
        <StatCard label="Brier" value={num(t.brier as number, 4)} hint={`raw ${num(cal.test_brier_uncalibrated, 4)}`} />
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="ROC curve (test)"><LineChart diagonal xDomain={[0, 1]} yDomain={[0, 1]} xLabel="False positive rate" yLabel="True positive rate"
          series={[{ name: "model", color: "var(--color-ok)", points: t.roc_curve as [number, number][] }]} xFormat={(v) => v.toFixed(1)} yFormat={(v) => v.toFixed(1)} /></Card>
        <Card title="Precision–recall (test)"><LineChart xDomain={[0, 1]} yDomain={[0, 1]} xLabel="Recall" yLabel="Precision"
          refLines={[{ y: t.prevalence as number, label: "prevalence", color: "var(--color-muted)" }]}
          series={[{ name: "model", color: "var(--color-ai)", points: t.pr_curve as [number, number][] }]} /></Card>
        <Card title="Calibration (test deciles)"><LineChart diagonal xDomain={[0, 0.5]} yDomain={[0, 0.5]} xLabel="Mean predicted" yLabel="Observed rate"
          series={[{ name: "calibrated", color: "var(--color-warn)", points: (t.calibration as { mean_predicted: number; observed_rate: number }[]).map((b) => [b.mean_predicted, b.observed_rate]) }]}
          xFormat={(v) => v.toFixed(2)} yFormat={(v) => v.toFixed(2)} /></Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        <Card title="Confusion matrix (test)"><ConfusionMatrix {...t.confusion_matrix} />
          <p className="mt-3 text-xs text-muted">Threshold chosen on validation to maximise F1 on calibrated scores; the test set was used once.</p></Card>
        <Card title="Global feature importance" subtitle={`mean |SHAP| on test sample`} className="xl:col-span-2">
          <BarList items={Object.entries(card.global_importance).slice(0, 12).map(([k, v]) => ({ label: card.features.labels[k] ?? k, value: v }))} format={(v) => v.toFixed(4)} />
        </Card>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Candidate models" subtitle="Selected on validation PR-AUC" bodyClassName="p-0"><CandidatesTable rows={card.candidates} kind="classification" /></Card>
        <Card title="Leakage ablation">
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th>Split</th><th>ROC-AUC</th><th>PR-AUC</th></tr></thead>
            <tbody>
              <tr><td>Grouped by patient (deployed)</td><td>{num(ablation.grouped_split_test.roc_auc, 3)}</td><td>{num(ablation.grouped_split_test.pr_auc, 3)}</td></tr>
              <tr><td>Naive row split</td><td>{num(ablation.row_split_test.roc_auc, 3)}</td><td>{num(ablation.row_split_test.pr_auc, 3)}</td></tr>
            </tbody></table>
          <p className="mt-2 text-xs text-muted">{ablation.note}</p>
          <p className="mt-2 text-xs text-muted">Baseline (predict prevalence) validation: ROC-AUC {num(base.roc_auc, 3)}, PR-AUC {num(base.pr_auc, 3)}.</p>
        </Card>
      </div>
      <Limitations items={card.limitations} />
    </div>
  );
}

function LosCard({ card }: { card: ModelCard }) {
  const t = card.metrics.test as Record<string, number>;
  const b = card.metrics.baseline_test as Record<string, number>;
  const pi = card.extra.prediction_interval as Record<string, number>;
  const ab = card.leakage_ablation as { admission_time_features_test: Record<string, number>; with_stay_time_features_test: Record<string, number>; extra_features: string[]; note: string };
  return (
    <div className="space-y-4">
      <ModelHeader card={card} />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="MAE (test)" value={`${num(t.mae)} d`} hint={`median baseline ${num(b.mae)} d`} />
        <StatCard label="RMSE (test)" value={`${num(t.rmse)} d`} hint={`baseline ${num(b.rmse)} d`} />
        <StatCard label="R² (test)" value={num(t.r2, 3)} hint={`baseline ${num(b.r2, 3)}`} />
        <StatCard label="80% interval coverage" value={`${(pi.test_coverage * 100).toFixed(1)}%`} hint={`${num(pi.lower_residual)} / +${num(pi.upper_residual)} d`} />
      </div>
      <Notice tone="warning">Admission-time information explains little of the variation in length of stay. The model beats the median baseline only modestly and is presented as a rough operational estimate.</Notice>
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Candidate models" subtitle="Selected on validation MAE" bodyClassName="p-0"><CandidatesTable rows={card.candidates} kind="regression" /></Card>
        <Card title="Leakage ablation">
          <table className="w-full text-sm"><thead><tr className="text-left text-xs text-muted"><th>Features</th><th>MAE</th><th>R²</th></tr></thead>
            <tbody>
              <tr><td>Admission-time (deployed)</td><td>{num(ab.admission_time_features_test.mae)}</td><td>{num(ab.admission_time_features_test.r2, 3)}</td></tr>
              <tr><td>+ stay-time features</td><td>{num(ab.with_stay_time_features_test.mae)}</td><td>{num(ab.with_stay_time_features_test.r2, 3)}</td></tr>
            </tbody></table>
          <p className="mt-2 text-xs text-muted">{ab.note} Extra features: {ab.extra_features.join(", ")}.</p>
        </Card>
      </div>
      <Card title="Global feature importance (days)"><BarList items={Object.entries(card.global_importance).map(([k, v]) => ({ label: card.features.labels[k] ?? k, value: v }))} format={(v) => v.toFixed(3)} /></Card>
      <Limitations items={card.limitations} />
    </div>
  );
}

function CandidatesTable({ rows, kind }: { rows: Record<string, unknown>[]; kind: "classification" | "regression" }) {
  const cols = kind === "classification" ? ["roc_auc", "pr_auc", "f1"] : ["mae", "rmse", "r2"];
  return (
    <table className="w-full text-sm">
      <thead><tr className="border-b border-line text-left text-xs font-medium text-muted"><th className="px-3 py-2">Candidate</th>{cols.map((c) => <th key={c} className="px-2">Validation {c.replace(/_/g, "-").toUpperCase()}</th>)}<th className="px-2">Test {cols[kind === "classification" ? 1 : 0].replace(/_/g, "-").toUpperCase()}</th></tr></thead>
      <tbody className="divide-y divide-line">
        {rows.map((r) => {
          const v = r.validation as Record<string, number>, te = r.test as Record<string, number>;
          return (
            <tr key={String(r.candidate)}><td className="px-3 py-1.5 font-mono text-xs">{String(r.candidate)}</td>
              {cols.map((c) => <td key={c} className="px-2 tabular-nums">{num(v[c], 3)}</td>)}
              <td className="px-2 tabular-nums">{num(te[cols[kind === "classification" ? 1 : 0]], 3)}</td></tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Limitations({ items }: { items: string[] }) {
  return <Card title="Limitations"><ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{items.map((l) => <li key={l}>{l}</li>)}</ul></Card>;
}

interface RagResult { status?: string; generated_at: string; k: number; questions: number; answerable: number; modes: Record<string, Record<string, number | null | Record<string, { n: number; "recall@5": number }>>> }

function RagEval() {
  const { data, error } = useApi<RagResult>("/ml/evaluation/rag");
  const { data: server } = useApi<{ reranker: string }>("/ai/status");
  if (error) return <ErrorState error={error} />;
  if (!data) return <Skeleton lines={6} />;
  if (data.status === "not_run") return <Notice tone="info">Run <code>python -m rag.evaluation.run_eval</code> to produce retrieval results.</Notice>;
  const metrics: [string, string][] = [["recall@1", "Recall@1"], ["recall@5", "Recall@5"], ["mrr", "MRR"], ["context_precision", "Context precision"],
    ["answer_correctness", "Answer correctness"], ["faithfulness", "Faithfulness"], ["citation_precision", "Citation precision"], ["abstention_accuracy", "Abstention"], ["latency_ms_p50", "p50 latency (ms)"]];
  const modes = Object.keys(data.modes);
  const cats = Object.keys(data.modes[modes[0]].by_category as object);
  return (
    <div className="space-y-4">
      {server?.reranker === "none" && (
        <Notice tone="info">
          This server runs without the reranker to fit a small hosting plan, so its document search matches the{" "}
          <b>hybrid</b> column below rather than <b>hybrid_rerank</b>.
        </Notice>
      )}
      <Card title="Vector vs keyword vs hybrid vs hybrid + reranking" subtitle={`${data.questions} benchmark questions (${data.answerable} answerable) · top-k ${data.k} · generated ${data.generated_at}`} bodyClassName="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-line text-left text-xs font-medium text-muted"><th className="px-3 py-2">Metric</th>{modes.map((m) => <th key={m} className="px-3">{m}</th>)}</tr></thead>
            <tbody className="divide-y divide-line">
              {metrics.map(([k, label]) => {
                const values = modes.map((m) => data.modes[m][k] as number | null);
                const best = k === "latency_ms_p50" ? Math.min(...values.map((v) => v ?? Infinity)) : Math.max(...values.map((v) => v ?? -Infinity));
                return (
                  <tr key={k}><td className="px-3 py-1.5 text-ink-2">{label}</td>
                    {values.map((v, i) => <td key={modes[i]} className={`px-3 tabular-nums ${v === best ? "font-semibold text-accent" : ""}`}>{v === null ? "—" : k === "latency_ms_p50" ? v.toFixed(0) : v.toFixed(3)}</td>)}</tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
      <Card title="Recall@5 by question category" bodyClassName="p-0">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-line text-left text-xs font-medium text-muted"><th className="px-3 py-2">Category</th>{modes.map((m) => <th key={m} className="px-3">{m}</th>)}</tr></thead>
          <tbody className="divide-y divide-line">
            {cats.map((c) => <tr key={c}><td className="px-3 py-1.5">{c.replace("_", " ")} <span className="text-xs text-faint">n={(data.modes[modes[0]].by_category as Record<string, { n: number }>)[c].n}</span></td>
              {modes.map((m) => <td key={m} className="px-3 tabular-nums">{(data.modes[m].by_category as Record<string, { "recall@5": number }>)[c]["recall@5"].toFixed(2)}</td>)}</tr>)}
          </tbody>
        </table>
      </Card>
      <Notice tone="info">The benchmark is small and was written alongside the synthetic corpus, so absolute numbers are optimistic; the relative comparison between retrieval modes is the useful signal. Answer metrics use the same extractive generator for every mode.</Notice>
    </div>
  );
}

interface SimResult { status?: string; patients: number; k: number; generated_at: string; overall_readmission_rate: number; variants: Record<string, Record<string, number | null>>; note: string }

function SimilarityEval() {
  const { data, error } = useApi<SimResult>("/ml/evaluation/similarity");
  if (error) return <ErrorState error={error} />;
  if (!data) return <Skeleton lines={6} />;
  if (data.status === "not_run") return <Notice tone="info">Run <code>python -m ml.evaluation.evaluate_similarity</code> to produce results.</Notice>;
  return (
    <Card title="Similarity validation (proxy metrics)" subtitle={`${data.patients} synthetic patients · k=${data.k} · overall 30-day readmission rate ${(data.overall_readmission_rate * 100).toFixed(1)}%`} bodyClassName="p-0">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-line text-left text-xs font-medium text-muted"><th className="px-3 py-2">Variant</th><th>Dept agreement@k</th><th>Diagnosis Jaccard</th><th>Neighbour readmit (readmitted)</th><th>(not readmitted)</th></tr></thead>
        <tbody className="divide-y divide-line">
          {Object.entries(data.variants).map(([name, v]) => (
            <tr key={name}><td className="px-3 py-1.5">{name}</td><td className="tabular-nums">{num(v.department_agreement, 3)}</td><td className="tabular-nums">{num(v.diagnosis_jaccard, 3)}</td>
              <td className="tabular-nums">{num(v.neighbour_readmission_rate_if_readmitted, 3)}</td><td className="tabular-nums">{num(v.neighbour_readmission_rate_if_not, 3)}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="px-3 py-2 text-xs text-muted">{data.note}</p>
    </Card>
  );
}
