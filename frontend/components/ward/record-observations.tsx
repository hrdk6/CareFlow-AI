"use client";

import { Activity, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Modal } from "@/components/ui/overlay";
import { api } from "@/lib/api";
import { cn } from "@/lib/format";
import { useDebounced } from "@/lib/hooks";
import type { News2, VitalSigns } from "@/lib/types";

import { RISK } from "./board-card";

const ACVPU: [string, string][] = [
  ["A", "Alert"], ["C", "New confusion"], ["V", "Responds to voice"], ["P", "Responds to pain"], ["U", "Unresponsive"],
];
const LABELS: Record<string, string> = {
  respiratory_rate: "Respiration rate", spo2: "Oxygen saturation", air_or_oxygen: "Air or oxygen",
  systolic_bp: "Systolic blood pressure", heart_rate: "Pulse", consciousness: "Consciousness", temperature: "Temperature",
};

const EMPTY = { respiratory_rate: "16", spo2: "97", systolic_bp: "124", diastolic_bp: "78", heart_rate: "76",
  temperature: "36.7", consciousness: "A", notes: "" };

/** The nurse's form. The score beside it comes from the server on every change, so what the form shows is
 *  exactly what will be stored - the chart is never reimplemented in the browser. */
export function RecordObservations({ patientId, patientName, onClose, onSaved }: {
  patientId: number; patientName: string; onClose: () => void; onSaved: (v: VitalSigns) => void;
}) {
  const [form, setForm] = useState({ ...EMPTY });
  const [onOxygen, setOnOxygen] = useState(false);
  const [scale2, setScale2] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [preview, setPreview] = useState<News2 | null>(null);
  const set = (key: keyof typeof EMPTY, value: string) => setForm((f) => ({ ...f, [key]: value }));

  const payload = {
    respiratory_rate: Number(form.respiratory_rate), spo2: Number(form.spo2), spo2_scale: scale2 ? 2 : 1,
    on_oxygen: onOxygen, systolic_bp: Number(form.systolic_bp),
    diastolic_bp: form.diastolic_bp === "" ? null : Number(form.diastolic_bp), heart_rate: Number(form.heart_rate),
    temperature: Number(form.temperature), consciousness: form.consciousness, notes: form.notes || null,
  };
  const complete = ["respiratory_rate", "spo2", "systolic_bp", "heart_rate", "temperature"]
    .every((k) => form[k as keyof typeof EMPTY] !== "" && Number.isFinite(Number(form[k as keyof typeof EMPTY])));
  const debounced = useDebounced(JSON.stringify(payload), 250);

  useEffect(() => {
    if (!complete) return;
    let alive = true;
    api<News2>(`/vitals/score?patient_id=${patientId}`, { method: "POST", json: JSON.parse(debounced) })
      .then((n) => alive && setPreview(n), () => alive && setPreview(null));
    return () => {
      alive = false;
    };
  }, [debounced, complete, patientId]);

  async function save() {
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<VitalSigns>(`/patients/${patientId}/vitals`, { method: "POST", json: payload }));
    } catch (e) {
      setError(e);
      setBusy(false);
    }
  }

  const shown = complete ? preview : null;  // an incomplete form shows no score rather than a stale one
  const risk = shown?.applies ? RISK[shown.risk] : null;
  return (
    <Modal open wide onClose={onClose} title={`Record observations · ${patientName}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button onClick={save} loading={busy} disabled={!complete}>Save observations</Button></>}>
      <div className="grid gap-5 sm:grid-cols-[minmax(0,1fr)_240px]">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Respiration rate" hint="breaths per minute">
            <Input type="number" inputMode="numeric" min={0} max={80} value={form.respiratory_rate} onChange={(e) => set("respiratory_rate", e.target.value)} autoFocus />
          </Field>
          <Field label="Oxygen saturation" hint="%">
            <Input type="number" inputMode="numeric" min={50} max={100} value={form.spo2} onChange={(e) => set("spo2", e.target.value)} />
          </Field>
          <Field label="Systolic blood pressure" hint="mmHg">
            <Input type="number" inputMode="numeric" min={40} max={300} value={form.systolic_bp} onChange={(e) => set("systolic_bp", e.target.value)} />
          </Field>
          <Field label="Diastolic blood pressure" hint="mmHg, not scored">
            <Input type="number" inputMode="numeric" min={20} max={200} value={form.diastolic_bp} onChange={(e) => set("diastolic_bp", e.target.value)} />
          </Field>
          <Field label="Pulse" hint="beats per minute">
            <Input type="number" inputMode="numeric" min={20} max={250} value={form.heart_rate} onChange={(e) => set("heart_rate", e.target.value)} />
          </Field>
          <Field label="Temperature" hint="°C">
            <Input type="number" inputMode="decimal" step="0.1" min={30} max={45} value={form.temperature} onChange={(e) => set("temperature", e.target.value)} />
          </Field>
          <Field label="Consciousness" className="sm:col-span-2">
            <Select value={form.consciousness} onChange={(e) => set("consciousness", e.target.value)}
              options={ACVPU.map(([value, label]) => ({ value, label: `${value} — ${label}` }))} />
          </Field>
          <div className="space-y-2 sm:col-span-2">
            <label className="flex items-center gap-2 text-[13px] text-ink">
              <input type="checkbox" className="accent-[var(--color-accent)]" checked={onOxygen} onChange={(e) => setOnOxygen(e.target.checked)} />
              Receiving supplemental oxygen
            </label>
            <label className="flex items-start gap-2 text-[13px] text-ink">
              <input type="checkbox" className="mt-0.5 accent-[var(--color-accent)]" checked={scale2} onChange={(e) => setScale2(e.target.checked)} />
              <span>Use SpO₂ scale 2 <span className="text-muted">— only when a clinician has prescribed it for confirmed hypercapnic respiratory failure (target 88–92%)</span></span>
            </label>
          </div>
          <Field label="Notes" hint="Optional" className="sm:col-span-2">
            <Textarea value={form.notes} onChange={(e) => set("notes", e.target.value)} rows={2} />
          </Field>
        </div>

        <aside className="rounded-xl border border-line bg-sunken p-4">
          <h3 className="flex items-center gap-1.5 text-xs font-medium text-muted"><Activity className="h-3.5 w-3.5" aria-hidden /> NEWS2</h3>
          {shown ? (
            <>
              <p className={cn("tabular mt-1 font-display text-[40px] font-semibold leading-none", risk ? risk.text : "text-muted")}>{shown.score}</p>
              {risk
                ? <Badge tone={risk.tone} className="mt-2">{risk.label} clinical risk</Badge>
                : <p className="mt-2 text-[12px] leading-relaxed text-warn">{shown.note}</p>}
              <ul className="mt-3 space-y-1 border-t border-line pt-3">
                {Object.entries(shown.parameters).map(([key, points]) => (
                  <li key={key} className="flex items-center justify-between text-[12px]">
                    <span className={points > 0 ? "text-ink" : "text-muted"}>{LABELS[key] ?? key}</span>
                    <span className={cn("tabular rounded px-1.5 font-semibold",
                      points === 0 ? "text-faint" : points === 3 ? "bg-high-tint text-high" : "bg-warn-tint text-warn")}>
                      {points}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 border-t border-line pt-3 text-[12px] leading-relaxed text-ink-2">
                <span className="font-medium text-ink">{shown.monitoring}.</span> {shown.response}
              </p>
              {shown.triggers.length > 0 && (
                <p className="mt-2 flex items-start gap-1.5 rounded-lg bg-high-tint px-2 py-1.5 text-[12px] font-medium text-high">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                  <span>Rapid response criteria: {shown.triggers.join("; ")}.</span>
                </p>
              )}
            </>
          ) : <p className="mt-2 text-[13px] text-muted">Fill in the observations to see the score.</p>}
        </aside>
      </div>
      {error ? <div className="mt-3"><ErrorState error={error} compact /></div> : null}
    </Modal>
  );
}
