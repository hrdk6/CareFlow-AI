---
version: 1
slug: "frontend-app-app-page-tsx"
primary_target: "frontend/app/(app)/page.tsx"
related_targets: []
---

# Dashboard (signed-in home)

Scope: the first screen after sign-in, for every role. Visitor mode: Operate.
Audience and job: a clinician or staff member orienting at the start of a shift, and an interviewer
judging in seconds whether this is credible clinical software. Everything shown is limited to the
signed-in user's authority.
Proof on hand: live census, today's outpatient appointments, recent discharges, critical laboratory
flags and, for administrators, AI query and denied-access counts. No invented figures.
Constraints: synthetic-data advisory stays visible; nothing implies diagnosis.

## Direction contract

THESIS: The dashboard is a central monitoring station: every figure a live channel in its clinical colour at a fixed position. It refuses the SaaS grid of same-size KPI cards with icon tiles.

OWN-WORLD: Matte black field, channel panels separated by 1px rules with no card shadows or glow. Condensed uppercase channel labels and monitor-scale tabular numerics; a quiet sans for prose and tables. Channel colours carry meaning only: green census/stable, cyan scheduled/advisory, yellow medium alarm, red high alarm, near-white values. A priority alarm bar sits under the top bar.

STORY: In one glance the user sees who is admitted, today's outpatient load, which results are critical and who left recently and needs readmission review, all within their authority. They open a patient from any channel or row.

FIRST VIEWPORT: Full-width alarm bar listing critical flags by priority with patient and value. Beneath, four equal channel tiles in one strip (inpatients, outpatients today, critical results, discharges to review), each with label, unit, state and a 60px numeric. Below, a central-station grid: bed-row census strips across two thirds, the discharge review queue in the right third. "Ask the assistant" sits top right as a secondary control.

FORM: Bedside Monitor, position 4 on the ordered grounded list, seed key 47e8aea2. Signature interaction: the monitor sweep, a refresh line crossing each channel while changed values update in place without moving the grid.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
