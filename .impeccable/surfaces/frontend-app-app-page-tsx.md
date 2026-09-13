---
version: 1
slug: "frontend-app-app-page-tsx"
primary_target: "frontend/app/(app)/page.tsx"
related_targets: ["frontend/app/login/page.tsx"]
---

# Dashboard (signed-in home) and sign-in

Scope: the first screen after sign-in for every role, and the sign-in page that precedes it. Visitor mode: Operate.
Audience and job: a clinician or staff member starting a shift, and an interviewer judging in seconds whether
this is polished, trustworthy hospital software. Everything shown is limited to the signed-in user's authority,
but the interface does not narrate the access model.
Proof on hand: census, today's appointments, recent discharges, critical lab results and, for administrators,
AI question, blocked-access and document counts. No invented figures.
Constraints: synthetic-data advisory stays visible; nothing implies diagnosis. The user rejected the dark
monitor world as too technical and chose the earlier light CareFlow look, refined (2026-09-13).

## Direction contract

THESIS: A calm, light clinical workspace that reads like finished hospital software: what needs attention first, then today's work. It refuses both the dark instrument costume and the generic icon-tile KPI grid.

OWN-WORLD: Cool near-white canvas, white cards on hairline borders with soft offset shadows, deep teal-ink sidebar. One teal accent for actions and selection; status in quiet tinted chips (emerald, amber, rose, sky, violet). Hanken Grotesk headings and numerals in sentence case, Inter for text and tables. Round avatars, rounded-xl cards, pill status chips.

STORY: The user is greeted by name, sees any critical results as a clear rose attention panel, then four summary figures, admitted patients, recent discharges and today's appointments, and opens a patient from any row.

FIRST VIEWPORT: Greeting heading with date line left, "Ask the assistant" primary button right. Beneath, the attention panel (critical results as patient rows with value chips). Then four summary cards in one row (number 32px, label, context line). Below, admitted patients across two thirds with discharges in the right third.

FORM: Earlier CareFlow, refined: the user-chosen standing path (no roll this round; prior seed key 47e8aea2 retired). Signature interaction: cards and rows lift on hover with a soft shadow and the row's arrow slides in; a gentle staggered rise on first load only.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
