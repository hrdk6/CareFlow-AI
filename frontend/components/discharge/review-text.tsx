"use client";

import { AlertTriangle, Check, Pencil } from "lucide-react";
import { Fragment, useState } from "react";

import { Answer, CitationChip } from "@/components/assistant/answer";
import { cn } from "@/lib/format";
import type { DraftSection } from "@/lib/types";

// The same rule as the server: . ! or ? followed by a space ends a sentence, except after a title ("Dr. Rao").
const SENTENCE_END = /(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)(?<!\bSt\.)(?<!\bvs\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<=[.!?])\s+(?=\S)/;
const CITE = /(\[[SR]\d+\])/;

export const norm = (s: string) => s.replace(/\s+/g, " ").trim().toLowerCase();

export function splitSentences(text: string): string[] {
  return text.replace(/\s*\n\s*/g, " ").trim().split(SENTENCE_END).filter(Boolean);
}

export function issueLabel(issue: string): string {
  if (issue === "no_source") return "No source";
  const number = issue.match(/^number_not_in_source:(.+)$/);
  return number ? `${number[1]} is not in the cited records` : issue;
}

/** Drafted sentences the checker flagged, by normalised text, with their reasons. */
export function flaggedSentences(sections: DraftSection[]): Map<string, string[]> {
  return new Map(sections.flatMap((s) => s.sentences.filter((x) => x.issues.length).map((x) => [norm(x.text), x.issues] as const)));
}

/** Flagged sentences still present, unchanged, in the edited text (the server applies the same rule when signing). */
export function remainingFlagged(sections: DraftSection[], text: Record<string, string>): string[] {
  return sections.flatMap((s) => s.sentences.filter((x) => x.issues.length && norm(text[s.key] ?? "").includes(norm(x.text))).map((x) => x.text));
}

function Cited({ text, labels, onCite }: { text: string; labels: Record<string, string>; onCite: (id: string) => void }) {
  return (
    <>
      {text.split(CITE).map((part, i) => {
        const id = part.match(/^\[([SR]\d+)\]$/)?.[1];
        return id ? <CitationChip key={i} id={id} label={labels[id]} onClick={onCite} /> : <Fragment key={i}>{part}</Fragment>;
      })}
    </>
  );
}

/** Prose with its sources: each flagged sentence is marked and says why, in words as well as colour. */
export function ReviewText({ text, flagged, labels, onCite }: {
  text: string; flagged: Map<string, string[]>; labels: Record<string, string>; onCite: (id: string) => void;
}) {
  const sentences = splitSentences(text);
  if (!sentences.length) return <p className="text-sm italic text-faint">Empty. Add text or regenerate the draft.</p>;
  return (
    <p className="text-[14px] leading-7 text-ink-2">
      {sentences.map((sentence, i) => {
        const issues = flagged.get(norm(sentence));
        if (!issues) return <Fragment key={i}><Cited text={sentence} labels={labels} onCite={onCite} />{" "}</Fragment>;
        return (
          <Fragment key={i}>
            <mark className="rounded-sm bg-warn-tint px-0.5 text-ink ring-1 ring-inset ring-warn-edge [box-decoration-break:clone]">
              <Cited text={sentence} labels={labels} onCite={onCite} />
            </mark>
            <span className="ml-1 inline-flex items-center gap-0.5 align-baseline text-[11px] font-medium text-warn">
              <AlertTriangle className="h-3 w-3" aria-hidden /> {issues.map(issueLabel).join("; ")}
            </span>{" "}
          </Fragment>
        );
      })}
    </p>
  );
}

/** A section of the summary: read with its sources, or edit as text. */
export function EditableSection({ title, text, onChange, flagged, labels, onCite, markdown }: {
  title: string; text: string; onChange: (text: string) => void; flagged: Map<string, string[]>;
  labels: Record<string, string>; onCite: (id: string) => void; markdown?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  return (
    <section>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <h3 className="text-[14px] font-semibold text-ink">{title}</h3>
        <button type="button" onClick={() => setEditing(!editing)} aria-pressed={editing}
          className={cn("flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium transition-colors duration-150",
            editing ? "bg-accent-tint text-accent" : "text-muted hover:bg-raised hover:text-ink")}>
          {editing ? <><Check className="h-3.5 w-3.5" aria-hidden /> Done</> : <><Pencil className="h-3.5 w-3.5" aria-hidden /> Edit</>}
        </button>
      </div>
      {editing ? (
        <textarea value={text} onChange={(e) => onChange(e.target.value)} aria-label={title} autoFocus
          rows={Math.min(14, Math.max(4, Math.ceil(text.length / 85) + text.split("\n").length))}
          className="scroll-thin block w-full rounded-lg border border-accent bg-panel px-3 py-2 text-[14px] leading-6 text-ink shadow-e1 focus:outline-none focus:ring-3 focus:ring-accent/15" />
      ) : markdown ? (
        <Answer text={text} onCite={onCite} labels={labels} />
      ) : (
        <ReviewText text={text} flagged={flagged} labels={labels} onCite={onCite} />
      )}
    </section>
  );
}
