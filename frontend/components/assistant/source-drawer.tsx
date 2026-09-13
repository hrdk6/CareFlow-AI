"use client";

import { ChevronRight, FileText, ShieldAlert } from "lucide-react";

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
      {(loading || (data && data.chunk_id !== citation?.chunk_id)) && <Skeleton lines={8} />}
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {data && data.chunk_id === citation?.chunk_id && (
        <div className="space-y-5">
          <div className="flex flex-wrap gap-1.5">
            <Badge tone="violet"><FileText className="h-3 w-3" aria-hidden /> {titleCase(data.doc_type)}</Badge>
            {data.department && <Badge>{data.department}</Badge>}
            {data.is_synthetic && <Badge tone="warning">Synthetic demo document</Badge>}
            {Boolean(data.flags?.injection_suspected) && <Badge tone="danger"><ShieldAlert className="h-3 w-3" aria-hidden /> Instruction-like content</Badge>}
          </div>
          <figure>
            <figcaption className="mb-2 text-xs font-medium text-muted">The passage the answer used</figcaption>
            <blockquote className="whitespace-pre-wrap rounded-xl bg-panel p-4 text-sm leading-7 text-ink shadow-e1 ring-1 ring-inset ring-ai-edge">
              {/* A highlighter sweeps through the passage once, in reading order. */}
              <span key={data.chunk_id} className="evidence-mark">{data.text}</span>
            </blockquote>
          </figure>
          {citation && (
            <details className="group rounded-lg border border-line">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg px-3 py-2.5 text-xs font-medium text-ink-2 hover:bg-sunken hover:text-ink [&::-webkit-details-marker]:hidden">
                <ChevronRight className="h-3.5 w-3.5 transition-transform duration-200 group-open:rotate-90" aria-hidden /> How this passage was found
              </summary>
              <div className="border-t border-line px-3 pb-3 pt-2.5">
                <dl className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(citation.retrieval).map(([k, v]) => (
                    <div key={k} className="rounded-md bg-sunken px-2.5 py-1.5">
                      <dt className="text-muted">{titleCase(k)}</dt>
                      <dd className="font-mono text-ink">{v === null ? "not retrieved" : String(v)}</dd>
                    </div>
                  ))}
                </dl>
                <p className="mt-2 text-[11px] leading-relaxed text-muted">Ranks come from semantic (vector) and keyword (BM25) retrieval, fused with reciprocal rank fusion and re-scored by a cross-encoder.</p>
              </div>
            </details>
          )}
        </div>
      )}
    </Drawer>
  );
}
