import { render, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { VitalsRow, WardCard } from "@/components/ward/board-card";
import type { News2, VitalSigns, WardPatient } from "@/lib/types";

const news2 = (over: Partial<News2> = {}): News2 => ({
  score: 6, risk: "medium", label: "Medium", single_parameter_3: false, due_within_hours: 1,
  parameters: { respiratory_rate: 2, spo2: 1, air_or_oxygen: 2, systolic_bp: 0, heart_rate: 1, consciousness: 0, temperature: 0 },
  response: "Urgent response: inform the medical team immediately.", monitoring: "At least hourly",
  triggers: [], applies: true, note: null, ...over,
});

const vitals = (over: Partial<VitalSigns> = {}): VitalSigns => ({
  id: 1, patient_id: 3, admission_id: 9, recorded_at: "2026-09-21T09:00:00Z", recorded_by: "Jiwoo Kim, RN",
  respiratory_rate: 22, spo2: 94, spo2_scale: 1, on_oxygen: true, systolic_bp: 118, diastolic_bp: 74, heart_rate: 96,
  temperature: 37.4, consciousness: "A", news2_score: 6, news2_risk: "medium", source: "manual", notes: null,
  news2: news2(), ...over,
});

const row = (over: Partial<WardPatient> = {}): WardPatient => ({
  patient_id: 3, mrn: "P1026", full_name: "Meena Kapoor", age: 46, sex: "F", department: "General Medicine",
  ward: "GM-3", admitted_at: "2026-09-18T10:00:00Z", day_of_stay: 4, reason: "Hyperglycemia", attending: "Dr. Rao",
  latest: vitals(), trend: [{ at: "2026-09-21T05:00:00Z", score: 2 }, { at: "2026-09-21T09:00:00Z", score: 6 }],
  due_at: "2026-09-21T10:00:00Z", overdue_hours: null, ...over,
});

describe("ward board", () => {
  it("marks the parameters that scored, with their points", () => {
    const { container } = render(<VitalsRow v={vitals()} />);
    expect(within(container).getByText("22/min").textContent).toBe("22/min+2");
    expect(within(container).getByText("118/74").textContent).toBe("118/74"); // scored 0: no badge
  });

  it("shows the score, the escalation the policy asks for, and overdue observations", () => {
    const { container } = render(<WardCard row={row({ overdue_hours: 3.5 })} canRecord onRecord={() => {}} />);
    const card = within(container);
    expect(card.getByText("6")).toBeInTheDocument();
    expect(card.getByText(/NEWS2 · Medium/)).toBeInTheDocument();
    expect(card.getByText(/Observations overdue by 3.5 h/)).toBeInTheDocument();
    expect(card.getByText(/Urgent response/)).toBeInTheDocument();
    expect(card.getByRole("button", { name: /Record/ })).toBeInTheDocument();
  });

  it("lists the hospital's rapid response criteria when they are met", () => {
    const triggers = ["NEWS2 of 12 (7 or more)", "New drop in consciousness (new confusion)"];
    const { container } = render(<WardCard row={row({ latest: vitals({ news2: news2({ score: 12, risk: "high", label: "High", triggers }) }) })}
      canRecord={false} onRecord={() => {}} />);
    for (const trigger of triggers) expect(within(container).getByText(trigger)).toBeInTheDocument();
    expect(within(container).queryByRole("button", { name: /Record/ })).not.toBeInTheDocument(); // read-only role
  });

  it("withholds the risk band for a patient the score is not validated for", () => {
    const child = vitals({ news2: news2({ applies: false, note: "NEWS2 is validated for adults (16 and over)." }) });
    const { container } = render(<WardCard row={row({ age: 5, latest: child })} canRecord onRecord={() => {}} />);
    const card = within(container);
    expect(card.getByText(/NEWS2 is not used for this patient/)).toBeInTheDocument();
    expect(card.queryByText("NEWS2 · Medium")).not.toBeInTheDocument();
    expect(card.getByText("22/min").textContent).toBe("22/min+2"); // the values are still shown
  });
});
