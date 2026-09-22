import { render, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TriagePanel } from "@/components/imaging/findings";
import { ReportForm } from "@/components/imaging/report-form";
import { WorklistRow } from "@/components/imaging/worklist-row";
import type { Finding, ImagingStudy, Triage, WorklistItem } from "@/lib/types";

const finding = (over: Partial<Finding> = {}): Finding => ({
  finding: "Effusion", label: "Pleural effusion", probability: 0.44, threshold: 0.063, flagged: true,
  priority: true, roc_auc: 0.78, roc_auc_ci: [0.76, 0.79], sensitivity: 0.87, specificity: 0.51,
  prevalence: 0.11, attention: [], ...over,
});

const triage = (over: Partial<Triage> = {}): Triage => ({
  priority: "priority", priority_score: 0.89,
  findings: [
    finding({ finding: "any_finding", label: "Any finding", probability: 0.89 }),
    finding(),
    finding({ finding: "Cardiomegaly", label: "Cardiomegaly", probability: 0.018, flagged: false,
      priority: false, threshold: 0.013, prevalence: 0.024, roc_auc: 0.73, roc_auc_ci: [0.68, 0.76],
      sensitivity: 0.95, specificity: 0.18 }),
  ],
  model_name: "chest_xray_triage", model_version: "1.0.0", trained_at: "2026-09-22T08:39:47+00:00",
  backbone: "Qdrant/resnet50-onnx", operating_point: "two cut-offs per finding",
  limitations: ["It is not a diagnosis."], disclaimer: "Triage support, not a diagnosis.",
  scored_at: "2026-09-22T08:40:00Z", inference_ms: 61, ...over,
});

const study = (over: Partial<ImagingStudy> = {}): ImagingStudy => ({
  id: 44, patient_id: 23, accession: "IMG-583618412500", study_uid: "1.2.826.0.1.3680043.10.1337.1",
  modality: "DX", body_part: "CHEST", view_position: "PA", description: "Chest PA",
  indication: "Pre-operative assessment", acquired_at: "2026-09-10T00:00:00Z", rows: 1024, columns: 1024,
  bits_stored: 8, window_center: 128, window_width: 256, source: "seed",
  deidentification: { method: "PS3.15", removed_tags: ["InstitutionName"], blanked_tags: ["PatientName"],
    date_tags_shifted: ["StudyDate"], shift_days: 42, private_tags_removed: true, uids_regenerated: true },
  triage: triage(), report: null, ...over,
});

const item = (over: Partial<WorklistItem> = {}): WorklistItem => ({
  study_id: 44, accession: "IMG-583618412500", patient_id: 23, mrn: "P1023", full_name: "Yusuf Gaikwad",
  age: 52, sex: "M", department: "General Medicine", inpatient: false, acquired_at: "2026-09-10T00:00:00Z",
  waiting_hours: 288, description: "Chest PA", indication: "Pre-operative assessment", view_position: "PA",
  priority: "priority", priority_score: 0.89, flagged: ["Pleural effusion"], reported: false,
  reported_at: null, ...over,
});

describe("triage panel", () => {
  it("says what the model means, not just a number", () => {
    const { container } = render(<TriagePanel triage={triage()} selected={null} onSelect={() => {}} />);
    const panel = within(container);
    // "Flagged" at a 90%-sensitivity cut-off means the finding is not ruled out, not that it is present.
    expect(panel.getByText("For attention")).toBeInTheDocument();
    expect(panel.getByText("Below the cut-off")).toBeInTheDocument();
    expect(panel.getByText(/Probability that the film shows any finding/)).toBeInTheDocument();
    // The numbers that let a reader weigh the flag are on the row itself.
    expect(panel.getByText(/Cut-off 6.3% · base rate 11% · AUC 0.78 \(0.76–0.79\)/)).toBeInTheDocument();
    expect(panel.getByText(/catches 87% and clears 51%/)).toBeInTheDocument();
  });

  it("keeps the overall score out of the per-finding list", () => {
    const { container } = render(<TriagePanel triage={triage()} selected={null} onSelect={() => {}} />);
    expect(within(container).queryByRole("button", { name: /Any finding/ })).not.toBeInTheDocument();
  });

  it("is explicit when a study was not scored", () => {
    const { container } = render(<TriagePanel triage={null} selected={null} onSelect={() => {}} />);
    expect(within(container).getByText(/frontal chest films of adults only/)).toBeInTheDocument();
  });
});

describe("reading queue", () => {
  it("shows the score, what was raised and how long the film has waited", () => {
    const { container } = render(<WorklistRow item={item()} />);
    const row = within(container);
    expect(row.getByText("89%")).toBeInTheDocument();
    expect(row.getByText(/Any finding · Priority/)).toBeInTheDocument();
    expect(row.getByText("Pleural effusion")).toBeInTheDocument();
    expect(row.getByText(/Waiting 12 d/)).toBeInTheDocument();
    expect(row.getByRole("link", { name: /Read/ })).toHaveAttribute("href", "/imaging/44");
  });

  it("says plainly when a film was not scored rather than implying it is normal", () => {
    const { container } = render(<WorklistRow item={item({ priority: null, priority_score: null, flagged: [] })} />);
    expect(within(container).getByText(/Not scored by the triage model/)).toBeInTheDocument();
  });

  it("marks a film that has already been reported", () => {
    const { container } = render(<WorklistRow item={item({ reported: true, reported_at: "2026-09-22T08:45:00Z" })} />);
    expect(within(container).getByText(/Reported/)).toBeInTheDocument();
    expect(within(container).getByRole("link", { name: /Open study/ })).toBeInTheDocument();
  });
});

describe("report", () => {
  it("cannot be signed by someone without a doctor profile", () => {
    const { container } = render(
      <ReportForm study={study()} onSaved={() => {}} canWrite canSign={false} />);
    const form = within(container);
    expect(form.getByRole("button", { name: /Save draft/ })).toBeInTheDocument();
    expect(form.queryByRole("button", { name: /Sign report/ })).not.toBeInTheDocument();
    expect(form.getByText(/only when a clinician with a doctor profile signs it/)).toBeInTheDocument();
  });

  it("shows a signed report read-only, with the reader's verdict on the model", () => {
    const signed = study({ report: { id: 5, findings: "Blunting of the left costophrenic angle.",
      impression: "Small left pleural effusion.", status: "final", model_agreement: "partly",
      reported_by: "Dr. Ananya Rao", signed_at: "2026-09-22T08:45:00Z", record_id: 1916 } });
    const { container } = render(<ReportForm study={signed} onSaved={() => {}} canWrite canSign />);
    const form = within(container);
    expect(form.getByText("Final")).toBeInTheDocument();
    expect(form.getByText("Small left pleural effusion.")).toBeInTheDocument();
    expect(form.getByText("Partly")).toBeInTheDocument();
    expect(form.queryByRole("button", { name: /Sign report/ })).not.toBeInTheDocument();
  });
});
