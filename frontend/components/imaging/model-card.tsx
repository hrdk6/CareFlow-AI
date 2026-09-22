"use client";

import { Badge } from "@/components/ui/badge";
import { Card, StatCard } from "@/components/ui/card";
import { cn, num } from "@/lib/format";
import type { ModelCard } from "@/lib/types";

/** One head's numbers, exactly as the training run wrote them into the model card. */
interface Head {
  roc_auc: number; roc_auc_ci: [number, number]; pr_auc: number; prevalence: number; brier: number;
  sensitivity: number; specificity: number; metadata_only_roc_auc: number; published: boolean;
  n: number; confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
  calibration: string; regularisation_C: number;
  operating_points: { name: string; threshold: number; sensitivity: number; specificity: number; share_flagged: number }[];
  subgroups: { group: string; value: string; n: number; positives: number; roc_auc: number }[];
  skipped?: string;
}

const label = (finding: string) => finding.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

export function ChestXrayCard({ card }: { card: ModelCard }) {
  const heads = card.metrics.test as unknown as Record<string, Head>;
  const dataset = card.dataset as unknown as {
    name: string; citation: string; labels: string; rows_used: number; patients: number; shards: number;
    split: { train: number; val: number; test: number; grouped_by: string };
  };
  const features = card.features as unknown as { backbone: string; description: string; input_size: number; fine_tuned: boolean };
  const bar = card.extra.publication_bar as { roc_auc: number; roc_auc_ci_lower: number; test_positives: number; bootstraps: number };
  const published = (card.extra.published_findings as string[]) ?? [];
  const operating = card.extra.operating_point as { rule: string };

  const scored = Object.entries(heads).filter(([, h]) => h.roc_auc !== undefined)
    .sort(([, a], [, b]) => b.roc_auc - a.roc_auc);
  const skipped = Object.entries(heads).filter(([, h]) => h.skipped);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">{card.model_name}@{card.version}</span>
          {card.is_active && <Badge tone="success">active</Badge>}
          <Badge tone="info">{card.algorithm}</Badge>
          <span className="text-xs text-muted">trained {card.trained_at.slice(0, 10)}</span>
        </div>
        <p className="mt-2 text-sm text-ink-2">{card.intended_use}</p>
        <div className="mt-2 text-xs leading-relaxed text-muted">
          Dataset: {dataset.name} — {dataset.citation}. Labels {dataset.labels}.{" "}
          {dataset.rows_used.toLocaleString()} films from {dataset.patients.toLocaleString()} patients, split by{" "}
          {dataset.split.grouped_by}: train {dataset.split.train.toLocaleString()} / validation{" "}
          {dataset.split.val.toLocaleString()} / test {dataset.split.test.toLocaleString()}.
        </div>
        <div className="mt-1 text-xs text-muted">
          Features: {features.description}, backbone <span className="font-mono">{features.backbone}</span>
          {features.fine_tuned ? "" : " (frozen — never fine-tuned on radiographs)"} · {operating?.rule}
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Findings shown" value={published.length} hint={`of ${scored.length} modelled`} />
        <StatCard label="Films" value={dataset.rows_used.toLocaleString()} hint={`${dataset.shards} shards of the release`} />
        <StatCard label="Held-out films" value={dataset.split.test.toLocaleString()} hint="Evaluated once" />
        <StatCard label="Best ROC-AUC" value={num(scored[0]?.[1].roc_auc, 3)} hint={label(scored[0]?.[0] ?? "")} />
      </div>

      <Card title="Per finding, on the held-out test films"
        subtitle="“Meta only” is a model on age, sex and view position with no image at all. A finding whose image model barely beats it is being predicted from who was photographed, not from the chest."
        bodyClassName="p-0">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>
                {["Finding", "Positives", "ROC-AUC", "95% CI", "PR-AUC", "Sens", "Spec", "Brier", "Meta only", "Shown"]
                  .map((h) => <th key={h} className="px-4 py-2 font-medium">{h}</th>)}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {scored.map(([finding, head]) => (
                <tr key={finding} className={cn(head.published ? "" : "text-muted")}>
                  <td className="px-4 py-2 font-medium text-ink">{label(finding)}</td>
                  <td className="tabular px-4 py-2">{(head.confusion_matrix.tp + head.confusion_matrix.fn).toLocaleString()}</td>
                  <td className="tabular px-4 py-2 font-semibold text-ink">{num(head.roc_auc, 3)}</td>
                  <td className="tabular px-4 py-2">{num(head.roc_auc_ci[0], 3)}–{num(head.roc_auc_ci[1], 3)}</td>
                  <td className="tabular px-4 py-2">{num(head.pr_auc, 3)}</td>
                  <td className="tabular px-4 py-2">{num(head.sensitivity, 2)}</td>
                  <td className="tabular px-4 py-2">{num(head.specificity, 2)}</td>
                  <td className="tabular px-4 py-2">{num(head.brier, 3)}</td>
                  <td className={cn("tabular px-4 py-2",
                    head.metadata_only_roc_auc >= head.roc_auc && "font-semibold text-warn")}>
                    {num(head.metadata_only_roc_auc, 3)}
                  </td>
                  <td className="px-4 py-2">
                    {head.published ? <Badge tone="success">yes</Badge> : <Badge tone="neutral">no</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="border-t border-line px-4 py-3 text-xs leading-relaxed text-muted">
          <strong className="text-ink-2">Publication bar.</strong> A finding is shown in the product only with
          ROC-AUC of at least {bar?.roc_auc}, a 95% interval starting at or above {bar?.roc_auc_ci_lower}{" "}
          ({bar?.bootstraps} bootstrap resamples of the test films) and at least {bar?.test_positives} positive
          test films. Everything else is measured and reported here, and shown nowhere else.
          {skipped.length > 0 && <> Not modelled at all, for too few positives: {skipped.map(([f]) => label(f)).join(", ")}.</>}
        </p>
      </Card>

      <Card title="Accuracy by subgroup" subtitle="Published findings only, on the same held-out films." bodyClassName="p-0">
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full text-[13px]">
            <thead className="border-b border-line text-left text-[11px] uppercase tracking-wide text-muted">
              <tr>{["Finding", "Group", "Films", "Positives", "ROC-AUC"].map((h) => (
                <th key={h} className="px-4 py-2 font-medium">{h}</th>))}</tr>
            </thead>
            <tbody className="divide-y divide-line">
              {published.flatMap((finding) => (heads[finding]?.subgroups ?? []).map((group) => (
                <tr key={`${finding}-${group.group}-${group.value}`}>
                  <td className="px-4 py-2 font-medium text-ink">{label(finding)}</td>
                  <td className="px-4 py-2 text-muted">{group.group} {group.value}</td>
                  <td className="tabular px-4 py-2">{group.n.toLocaleString()}</td>
                  <td className="tabular px-4 py-2">{group.positives.toLocaleString()}</td>
                  <td className="tabular px-4 py-2 font-semibold text-ink">{num(group.roc_auc, 3)}</td>
                </tr>
              )))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Limitations">
        <ul className="list-disc space-y-1.5 pl-5 text-[13px] leading-relaxed text-ink-2">
          {card.limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
        </ul>
      </Card>
    </div>
  );
}
