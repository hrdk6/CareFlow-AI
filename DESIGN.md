---
version: alpha
name: CareFlow AI
description: >-
  Clinical information platform: dense hospital data, machine-learning predictions and a grounded AI
  assistant. The interface must feel calm, precise and trustworthy - closer to a professional trading
  terminal than a consumer app - because clinicians scan it under time pressure.
colors:
  brand.50: "#edfbf7"
  brand.100: "#d2f4ea"
  brand.200: "#a8e8d7"
  brand.300: "#71d5bf"
  brand.400: "#3cbba3"
  brand.500: "#189e89"
  brand.600: "#0b7f6f"
  brand.700: "#0c665b"
  brand.800: "#0e514a"
  brand.900: "#0d3f3b"
  brand.950: "#04231f"
  canvas: "#f6f7f9"
  surface: "#ffffff"
  line: "#e5e9ef"
  lineStrong: "#d3d9e2"
  ink: "#0f172a"
  muted: "#64748b"
  rail: "#0b1220"
  status.successBg: "#ecfdf5"
  status.successText: "#047857"
  status.warningBg: "#fffbeb"
  status.warningText: "#b45309"
  status.dangerBg: "#fff1f2"
  status.dangerText: "#e11d48"
  status.infoBg: "#f0f9ff"
  status.infoText: "#0369a1"
  status.ragBg: "#f5f3ff"
  status.ragText: "#6d28d9"
typography:
  pageTitle:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: -0.011em
  sectionTitle:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: 400
    lineHeight: 1.5
  small:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: 400
    lineHeight: 1.5
  micro:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 500
    lineHeight: 1.45
  label:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0.06em
  metric:
    fontFamily: Inter
    fontSize: 22px
    fontWeight: 600
    lineHeight: 1.2
    fontFeature: tnum
  code:
    fontFamily: ui-monospace
    fontSize: 12px
    fontWeight: 400
rounded:
  sm: 0.375rem
  md: 0.5rem
  lg: 0.625rem
  xl: 0.875rem
  full: 9999px
spacing:
  0.5: 2px
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 20px
  6: 24px
  8: 32px
components:
  button.primary:
    backgroundColor: "{colors.brand.600}"
    textColor: "{colors.surface}"
    typography: "{typography.body}"
    rounded: "{rounded.lg}"
    height: 36px
    padding: 0 14px
  button.secondary:
    backgroundColor: "{colors.surface}"
    textColor: "#334155"
    rounded: "{rounded.lg}"
    height: 36px
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: 16px
  statCard:
    backgroundColor: "{colors.surface}"
    typography: "{typography.metric}"
    rounded: "{rounded.xl}"
  badge:
    rounded: "{rounded.full}"
    typography: "{typography.micro}"
    padding: 2px 8px
  input:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    height: 36px
    typography: "{typography.body}"
  tableHeader:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.muted}"
    typography: "{typography.label}"
  modal:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.xl}"
    padding: 20px
  navRail:
    backgroundColor: "{colors.rail}"
    textColor: "#94a3b8"
    width: 240px
---

## Overview

CareFlow AI is a hospital platform used by four roles — doctor, nurse, receptionist and administrator —
who each see a different slice of the same data. Screens are read, not browsed: a clinician wants the
answer to "what is going on with this patient" in one glance, and every number on screen is limited to
what that user is authorized to see.

The visual language follows from that:

- **Calm over colourful.** Colour carries meaning (risk, status, AI capability). Anything decorative
  competes with a critical lab flag, so the palette stays neutral until data needs attention.
- **Density with air.** Tables are compact, but sections breathe. Never sacrifice legibility for
  fitting more rows.
- **Evidence is visible.** AI answers, predictions and citations always show where they came from.
  The interface shows its work rather than asking for trust.
- **Never look playful.** No illustration, no rounded cartoon shapes, no celebratory colour. This is
  a clinical record.

Tone of voice: plain, factual, British-neutral. "No appointments today", not "Nothing here yet! 🎉".

## Colors

The teal brand ramp is the only saturated family used for interface intent; everything structural is
neutral slate.

| Token | Use |
|---|---|
| `brand.600` / `brand.700` | Primary buttons, active navigation, links, focus rings, chart series |
| `brand.50` / `brand.100` | Selected rows, hovered list items, active tab pills, badge fills |
| `brand.300` / `brand.400` | Accents on the dark rail only (logo mark, active icon, accent bar) |
| `canvas` | Page background, behind all cards |
| `surface` | Cards, tables, modals, inputs — every raised plane |
| `line` / `lineStrong` | Hairlines and card borders / input borders and dividers that need weight |
| `ink` | Primary text, headings, table values |
| `muted` | Secondary text, labels, hints, empty-state copy |
| `rail` | Navigation sidebar only |

Status colour is semantic and never decorative:

- **success** — active patients, indexed documents, completed appointments
- **warning** — admitted patients, processing documents, elevated risk, high lab values
- **danger** — critical lab values, failed ingestion, denied access, no-shows
- **info** — scheduled appointments, discharged status, low lab values
- **rag (violet)** — retrieval-augmented generation; reserved for the RAG capability badge

A cautionary amber banner sits above every authenticated page: the data is synthetic and the AI is
decision support only. It must never be styled away or dismissed.

Contrast: body text and all status text meet WCAG AA (4.5:1) on their backgrounds; `muted` is used
only at 12px and above and only for secondary content.

## Typography

Inter, loaded as a variable font, is the single family. Monospace is used exclusively for identifiers
— MRNs (`P1024`), staff codes (`D103`), model versions, request ids and citation markers (`[S1]`,
`[R3]`) — so an identifier is always recognisable as one.

- `pageTitle` opens a screen; only one per page.
- `sectionTitle` labels a card. Sentence case, never uppercase.
- `label` is the uppercase micro-label for stat cards and table headers; it carries letter-spacing.
- `metric` renders any number a user compares — always with tabular figures so digits align in a
  column. Lab values, risk percentages, counts and dates in tables all use tabular figures.

Headings tighten as they grow (`letterSpacing: -0.011em`); body text never does.

## Layout

- **Shell**: a fixed 240px dark rail on the left, a sticky 56px top bar with patient search and the
  current role, and the page content. Below 768px the rail becomes a slide-over drawer — navigation
  must never simply disappear.
- **Page width**: content is capped at 1500px and padded 32px on desktop, 16px on mobile.
- **Rhythm**: 20px between major sections, 16px inside cards, 12px between related controls. The
  spacing scale is a 4px grid.
- **Grids**: stat rows are 4-up on desktop, 2-up on tablet, stacked on mobile. Detail screens use a
  2:1 split — primary record on the left, predictions and AI panels on the right.
- **Tables** own their horizontal scrolling inside the card; the page itself never scrolls sideways.
  Table headers stick to the top of their scroll container.

## Elevation & Depth

Three levels, no more:

- **e1** `0 1px 2px rgba(15,23,42,.05)` — resting cards, inputs, buttons. The default.
- **e2** `0 2px 4px rgba(15,23,42,.06), 0 4px 12px -4px rgba(15,23,42,.08)` — hovered cards, the AI
  composer, anything the pointer is over.
- **e3** `0 12px 32px -8px rgba(15,23,42,.18)` — modals, drawers, search results: content that floats
  above the page over a blurred backdrop.

Depth communicates interactivity, not decoration: if a surface lifts on hover, it must be clickable.

## Shapes

- Cards, modals and drawers: `rounded.xl` (14px).
- Buttons, inputs, selects, tabs, list rows: `rounded.lg` (10px).
- Badges, avatars and the current-page accent bar: `rounded.full`.
- Charts are drawn with a 1px hairline grid in `line`, series in `brand.600` and violet for a second
  series; reference lines are dashed and labelled.

Icons are Lucide, 16px inside controls and 20px in stat tiles, always `1.5px` stroke.

## Components

**Button** — four variants. Primary (brand gradient, white text) for the single main action on a
screen; secondary (white, hairline ring) for everything else; ghost for toolbar actions; danger only
for destructive confirmation. Buttons press down 1px on click and show a spinner in place of their
icon while busy.

**Card** — optional header with `sectionTitle`, optional subtitle in `muted`, optional actions on the
right. Body padding 16px, or zero when the body is a table or list that draws its own rows.

**Stat card** — icon tile in a status tint, uppercase `label`, `metric` value, optional hint line.
Used for counts and model metrics, never for prose.

**Badge** — pill with a status dot. `StatusBadge` maps a domain status to its semantic tone;
`RouteBadge` shows an AI capability (SQL, RAG, ML, SIMILARITY, LLM) in monospace.

**Table** — sticky uppercase header on a tinted background, hairline row rules, hover tint only when
rows are clickable, numeric columns in tabular figures. Pagination sits in the card footer.

**Tabs** — a segmented control: a tinted track with the active tab as a raised white pill. Counts
appear as small pills inside the tab.

**Form field** — label above, control, then hint or error beneath. Inputs show a 4px brand focus ring.
Selects always use the custom chevron, never the OS arrow.

**Modal / drawer** — animate in (fade plus 6px rise, 180–240ms, ease-out-quart) over a blurred
backdrop, lock page scroll, close on Escape and on backdrop click.

**AI answer** — the assistant's response always carries: the capabilities used as route badges, the
answer body with inline citation markers, a source list that opens the original passage, and any
warnings or limitations. Never render an AI answer as plain chat text without its evidence.

**Navigation rail** — grouped links (Overview, Care, Clinical, Intelligence, System) with uppercase
group labels; the current page gets a brand accent bar and a lighter background. The signed-in user
sits at the bottom with initials avatar, name and role.

## Do's and Don'ts

**Do**

- Keep one primary action per screen; everything else is secondary or ghost.
- Use tabular figures for anything a user compares down a column.
- Show empty states as a quiet icon, a factual line and — if the user may act — one button.
- State the reason next to any refusal ("Only clinical staff can change a patient's allergies").
- Respect `prefers-reduced-motion`: all animation collapses to near-zero duration.
- Keep the demo-data banner visible on every authenticated screen.

**Don't**

- Don't use colour alone to carry meaning; pair every status colour with text or an icon.
- Don't put clinical values in `muted` grey or below 12px.
- Don't introduce a second accent hue, gradient background or decorative illustration.
- Don't animate anything longer than 250ms, and never animate data as it arrives.
- Don't hide destructive actions behind icons alone — label them.
- Don't invent progress indicators for AI answers; show the real stage timings instead.
