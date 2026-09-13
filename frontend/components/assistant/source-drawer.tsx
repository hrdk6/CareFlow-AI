"use client";

import { FileText, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Drawer } from "@/components/ui/overlay";
import { titleCase } from "@/lib/format";
import { useApi } from "@/lib/hooks";
import type { Citation, Source } from "@/lib/types";

/** Shows the exact passage behind a citation, fetched through the same access checks as retrieval. */
export function SourceDrawer({ citation, onClose }: { citation: Citation | null; onClose: () => void }) {
  const { data, error, loading, reload } = useApi<Source>(citation ? `/ai/sources/${citation.chunk_id}` : null);
  const pages = citation?.page_start
    ? citation.page_start === citation.page_end ? `page ${citation.page_start}` : `pages ${citation.page_start}–${citation.page_end}`
    : "no page";
  return (
    <Drawer open={!!citation} onClose={onClose} title={citation ? `[${citation.id}] ${citation.document_title}` : ""}
      subtitle={citation && <span>Version {citation.version} · {citation.section_path || "Body"} · {pages}</span>}>
      {loading && <Skeleton lines={8} />}
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {data && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="violet"><FileText className="h-3 w-3" /> {titleCase(data.doc_type)}</Badge>
            {data.department && <Badge>{data.department}</Badge>}
            {data.is_synthetic && <Badge tone="warning">Synthetic demo document</Badge>}
            {Boolean(data.flags?.injection_suspected) && <Badge tone="danger"><ShieldAlert className="h-3 w-3" /> Instruction-like content</Badge>}
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-muted">Retrieved passage</div>
            <blockquote className="whitespace-pre-wrap rounded-md border-l-4 border-ai bg-ai-tint/50 p-3 text-sm leading-relaxed text-ink">
              {data.text}
            </blockquote>
          </div>
          {citation && (
            <div>
              <div className="mb-1 text-xs font-medium text-muted">Why it was retrieved</div>
              <dl className="grid grid-cols-2 gap-2 text-xs">
                {Object.entries(citation.retrieval).map(([k, v]) => (
                  <div key={k} className="rounded bg-sunken px-2 py-1.5">
                    <dt className="text-muted">{titleCase(k)}</dt>
                    <dd className="font-mono text-ink">{v === null ? "not retrieved" : String(v)}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-2 text-[11px] text-muted">Ranks come from semantic (vector) and keyword (BM25) retrieval, fused with reciprocal rank fusion and re-scored by a cross-encoder.</p>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}
