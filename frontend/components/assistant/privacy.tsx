"use client";

import { ChevronDown, ShieldCheck } from "lucide-react";
import { Fragment, useState } from "react";

import { cn } from "@/lib/format";
import type { Privacy } from "@/lib/types";

const DESTINATION: Record<string, string> = {
  groq: "Groq", gemini: "Google Gemini", anthropic: "Anthropic", openai_compatible: "the model server",
};
const KIND: Record<string, [string, string]> = {
  patient_name: ["name", "names"], mrn: ["record number", "record numbers"],
  date_of_birth: ["date of birth", "dates of birth"], phone: ["phone number", "phone numbers"],
  email: ["email address", "email addresses"], address: ["home address", "home addresses"],
  contact_name: ["emergency contact", "emergency contacts"], national_id: ["ID number", "ID numbers"],
  person: ["other person named in a note", "other people named in notes"],
};
const PLACEHOLDER = /\b((?:PATIENT|MRN|DOB|PHONE|EMAIL|ADDRESS|CONTACT|NATIONAL_ID|PERSON)_\d+)\b/;

export function destinationLabel(destination: string | null): string {
  return (destination && DESTINATION[destination]) || "the language model";
}

/** "1 name, 1 record number and 1 date of birth" */
export function describeReplaced(replaced: Record<string, number>): string {
  // Names first, then the other identifiers in the order a registration form lists them.
  const order = Object.keys(KIND);
  const rank = (kind: string) => (order.includes(kind) ? order.indexOf(kind) : order.length);
  const parts = Object.entries(replaced).sort(([a], [b]) => rank(a) - rank(b)).map(([kind, n]) => {
    const [one, many] = KIND[kind] ?? [kind.replace(/_/g, " "), `${kind.replace(/_/g, " ")}s`];
    return `${n} ${n === 1 ? one : many}`;
  });
  return parts.length < 2 ? parts.join("") : `${parts.slice(0, -1).join(", ")} and ${parts[parts.length - 1]}`;
}

/** The request as the model received it, with each placeholder marked so the substitution is visible. */
function Preview({ text }: { text: string }) {
  return (
    <pre className="scroll-thin max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-line bg-panel p-3 font-mono text-[11px] leading-relaxed text-ink-2">
      {text.split(PLACEHOLDER).map((part, i) => (i % 2 === 1
        ? <mark key={i} className="rounded bg-ok-tint px-0.5 font-semibold text-ok ring-1 ring-inset ring-ok-edge">{part}</mark>
        : <Fragment key={i}>{part}</Fragment>))}
    </pre>
  );
}

export function PrivacyPanel({ privacy }: { privacy: Privacy }) {
  const [open, setOpen] = useState(false);
  const where = destinationLabel(privacy.destination);
  if (!privacy.applied) {
    return (
      <p className="leading-relaxed text-ink-2">
        This answer was written by a model that runs inside the hospital network ({where}), so the question and the
        records were sent to it unchanged.
      </p>
    );
  }
  return (
    <div className="space-y-2.5">
      <p className="flex items-start gap-2 leading-relaxed text-ink-2">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />
        <span>
          {privacy.total > 0
            ? <>Before this question went to {where}, {describeReplaced(privacy.replaced)} {privacy.total === 1 ? "was" : "were"} replaced
              with placeholders such as <code className="rounded bg-raised px-1 font-mono">PATIENT_1</code>. {where} never received
              them; the real details were put back into the answer here, on the CareFlow server.</>
            : <>No patient identifiers were needed to answer this question, so nothing had to be replaced before it went to {where}.</>}
        </span>
      </p>
      <p className="leading-relaxed text-muted">
        Dates, results and diagnoses are sent as they are, because a summary needs them. This hospital&apos;s own
        clinicians are not hidden.{privacy.name_model
          ? " People named in free text — a relative, a clinician elsewhere — are found by a name model, which is a good pass and not a perfect one."
          : ""}
      </p>
      {privacy.preview && (
        <div>
          <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
            className="flex items-center gap-1 rounded-md font-medium text-accent hover:text-accent-strong">
            {open ? "Hide" : "Show"} exactly what {where} received
            <ChevronDown className={cn("h-3.5 w-3.5 transition-transform duration-200", open && "rotate-180")} aria-hidden />
          </button>
          {open && <div className="animate-fade-in mt-2"><Preview text={privacy.preview} /></div>}
        </div>
      )}
    </div>
  );
}
