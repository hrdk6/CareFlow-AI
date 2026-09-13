/**
 * Markdown-lite renderer for assistant answers. Produces React elements only (no HTML injection):
 * headings, paragraphs, bullet/numbered lists, **bold**, _italic_, `code`, and citation chips [S1] / [R2].
 */
import { Fragment } from "react";

import { cn } from "@/lib/format";

const INLINE = /(\*\*[^*]+\*\*|(?<![\w])_[^_\n]+_(?![\w])|`[^`]+`|\[(?:[SR]\d+)\])/g;

export function CitationChip({ id, onClick, label }: { id: string; onClick?: (id: string) => void; label?: string }) {
  const isSource = id.startsWith("S");
  return (
    <button type="button" onClick={() => onClick?.(id)} title={label}
      className={cn("mx-0.5 inline-flex -translate-y-px items-center rounded px-1 py-0 align-baseline font-mono text-[10px] font-semibold ring-1 ring-inset transition-colors",
        isSource ? "bg-ai-tint text-ai ring-ai-edge hover:bg-ai-tint" : "bg-info-tint text-info ring-info-edge hover:bg-info-tint")}>
      {id}
    </button>
  );
}

function inline(text: string, onCite?: (id: string) => void, labels?: Record<string, string>) {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null;
    const cite = part.match(/^\[([SR]\d+)\]$/);
    if (cite) return <CitationChip key={i} id={cite[1]} onClick={onCite} label={labels?.[cite[1]]} />;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={i} className="font-semibold text-ink">{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`")) return <code key={i} className="rounded bg-raised px-1 font-mono text-[12px]">{part.slice(1, -1)}</code>;
    if (part.startsWith("_") && part.endsWith("_") && part.length > 2) return <em key={i} className="text-muted">{part.slice(1, -1)}</em>;
    return <Fragment key={i}>{part}</Fragment>;
  });
}

export function Answer({ text, onCite, labels }: { text: string; onCite?: (id: string) => void; labels?: Record<string, string> }) {
  const blocks = text.replace(/\r/g, "").split(/\n{2,}/);
  const out: React.ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    out.push(
      <Tag key={`l${out.length}`} className={cn("my-2 space-y-1 pl-5", list.ordered ? "list-decimal" : "list-disc marker:text-faint")}>
        {list.items.map((item, i) => <li key={i}>{inline(item, onCite, labels)}</li>)}
      </Tag>,
    );
    list = null;
  };
  for (const block of blocks) {
    for (const line of block.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed) continue;
      const bullet = trimmed.match(/^[-*•]\s+(.*)$/);
      const numbered = trimmed.match(/^\d+[.)]\s+(.*)$/);
      const heading = trimmed.match(/^#{1,4}\s+(.*)$/);
      if (bullet || numbered) {
        const ordered = !!numbered;
        if (list && list.ordered !== ordered) flush();
        list = list ?? { ordered, items: [] };
        list.items.push((bullet ?? numbered)![1]);
        continue;
      }
      flush();
      if (heading) {
        out.push(<h3 key={`h${out.length}`} className="mb-1 mt-3 text-[14px] font-semibold text-ink">{inline(heading[1], onCite, labels)}</h3>);
      } else {
        out.push(<p key={`p${out.length}`} className="my-1.5">{inline(trimmed, onCite, labels)}</p>);
      }
    }
    flush();
  }
  return <div className="text-[14px] leading-relaxed text-ink-2">{out}</div>;
}
