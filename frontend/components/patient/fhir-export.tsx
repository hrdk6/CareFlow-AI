"use client";

import { Check, ChevronRight, Copy, Download, ShieldCheck } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState, Skeleton } from "@/components/ui/feedback";
import { Drawer } from "@/components/ui/overlay";
import { useApi } from "@/lib/hooks";

interface FhirResource { resourceType: string; id: string; [key: string]: unknown }
interface FhirBundle { resourceType: "Bundle"; total: number; timestamp: string; entry: { fullUrl: string; resource: FhirResource }[] }

const SYSTEMS: [prefix: string, label: string, what: string][] = [
  ["http://hl7.org/fhir/sid/icd-10-cm", "ICD-10-CM", "diagnoses"],
  ["http://loinc.org", "LOINC", "laboratory tests and note types"],
  ["http://unitsofmeasure.org", "UCUM", "units of measure"],
  ["http://www.whocc.no/atc", "WHO ATC", "medicines"],
  ["http://snomed.info/sct", "SNOMED CT", "routes of administration"],
  ["http://terminology.hl7.org/CodeSystem", "HL7 terminology", "statuses, classes and roles"],
];

const RESOURCE_LABEL: Record<string, string> = {
  Patient: "Patient", Observation: "Results and observations", MedicationRequest: "Medication orders",
  Condition: "Diagnoses", Encounter: "Admissions", DocumentReference: "Clinical notes", Appointment: "Appointments",
  AllergyIntolerance: "Allergies", RiskAssessment: "Risk estimates", Practitioner: "Clinicians",
  Organization: "Hospital and departments", Provenance: "AI provenance records", Device: "Drafting models",
};

function codingSystems(node: unknown, counts: Map<string, number>): Map<string, number> {
  if (Array.isArray(node)) node.forEach((n) => codingSystems(n, counts));
  else if (node && typeof node === "object") {
    const o = node as Record<string, unknown>;
    if (typeof o.system === "string" && typeof o.code === "string") {
      const hit = SYSTEMS.find(([prefix]) => (o.system as string).startsWith(prefix));
      if (hit) counts.set(hit[1], (counts.get(hit[1]) ?? 0) + 1);
    }
    Object.values(o).forEach((v) => codingSystems(v, counts));
  }
  return counts;
}

/** The patient's record as other hospital systems exchange it: a FHIR R4 Bundle, under the same access rules. */
export function FhirExportDrawer({ open, onClose, mrn, name }: { open: boolean; onClose: () => void; mrn: string; name: string }) {
  const { data, error, loading, reload } = useApi<FhirBundle>(open ? `/fhir/Patient/${mrn}/$everything` : null);
  const [copied, setCopied] = useState(false);
  const json = useMemo(() => (data ? JSON.stringify(data, null, 2) : ""), [data]);
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of data?.entry ?? []) m.set(e.resource.resourceType, (m.get(e.resource.resourceType) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1]);
  }, [data]);
  const systems = useMemo(() => (data ? codingSystems(data, new Map()) : new Map<string, number>()), [data]);
  const patient = data?.entry.find((e) => e.resource.resourceType === "Patient")?.resource;

  function download() {
    const url = URL.createObjectURL(new Blob([json], { type: "application/fhir+json" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: `${mrn}-fhir-r4.json` });
    a.click();
    URL.revokeObjectURL(url);
  }
  async function copy() {
    await navigator.clipboard.writeText(json);
    setCopied(true);
    setTimeout(() => setCopied(false), 1600);
  }

  return (
    <Drawer open={open} onClose={onClose} title="Export as FHIR" subtitle={<span>{name} ({mrn}) · HL7 FHIR R4 · application/fhir+json</span>}>
      {error ? <ErrorState error={error} onRetry={reload} /> : null}
      {loading && !data && <Skeleton lines={10} />}
      {data && (
        <div className="space-y-5 text-sm">
          <p className="leading-relaxed text-ink-2">
            The whole record as one FHIR Bundle, the format hospital systems use to exchange data. Diagnoses, results and medicines
            carry standard codes, so another system can read them without CareFlow&apos;s own vocabulary.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button onClick={download}><Download className="h-4 w-4" aria-hidden /> Download JSON</Button>
            <Button variant="secondary" onClick={copy}>
              {copied ? <Check className="h-4 w-4 text-ok" aria-hidden /> : <Copy className="h-4 w-4" aria-hidden />} {copied ? "Copied" : "Copy"}
            </Button>
          </div>
          <section>
            <h3 className="mb-2 text-xs font-medium text-muted">{data.entry.length} resources</h3>
            <ul className="grid grid-cols-2 gap-1.5">
              {counts.map(([type, n], i) => (
                <li key={type} className="stagger-in flex items-center justify-between rounded-lg bg-sunken px-3 py-2" style={{ "--i": i } as React.CSSProperties}>
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] text-ink">{RESOURCE_LABEL[type] ?? type}</span>
                    <span className="block font-mono text-[11px] text-faint">{type}</span>
                  </span>
                  <span className="tabular font-display text-[17px] font-semibold text-ink">{n}</span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h3 className="mb-2 text-xs font-medium text-muted">Standard codes in this export</h3>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {SYSTEMS.filter(([, label]) => systems.has(label)).map(([, label, what]) => (
                <li key={label} className="flex items-center justify-between gap-3 px-3 py-2">
                  <span><span className="font-medium text-ink">{label}</span> <span className="text-xs text-muted">{what}</span></span>
                  <span className="tabular text-xs text-muted">{systems.get(label)} codes</span>
                </li>
              ))}
            </ul>
          </section>
          <p className="flex items-start gap-2 rounded-lg bg-ok-tint px-3 py-2.5 text-xs leading-relaxed text-ink-2 ring-1 ring-inset ring-ok-edge">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-hidden />
            <span>The same access rules apply as everywhere else, and every export is recorded in the audit log. Each resource is
              labelled as test data, and discharge summaries drafted with AI carry a provenance record naming the model and the
              clinician who signed.</span>
          </p>
          {patient && (
            <details className="group rounded-lg border border-line">
              <summary className="flex cursor-pointer list-none items-center gap-1.5 rounded-lg px-3 py-2.5 text-xs font-medium text-ink-2 hover:bg-sunken hover:text-ink [&::-webkit-details-marker]:hidden">
                <ChevronRight className="h-3.5 w-3.5 transition-transform duration-200 group-open:rotate-90" aria-hidden /> The Patient resource
              </summary>
              <pre className="scroll-thin max-h-96 overflow-auto border-t border-line bg-sunken p-3 font-mono text-[11px] leading-relaxed text-ink-2">{JSON.stringify(patient, null, 2)}</pre>
            </details>
          )}
        </div>
      )}
    </Drawer>
  );
}
