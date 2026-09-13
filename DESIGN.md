---
name: CareFlow AI
description: A calm, light clinical workspace in CareFlow teal - white cards on a cool near-white canvas, a deep teal-ink sidebar, and quiet tinted status chips.
colors:
  field: "#f3f6f7"
  panel: "#ffffff"
  sunken: "#f7f9fa"
  raised: "#eff3f5"
  raised-2: "#e6ecef"
  line: "#e3e9ec"
  line-strong: "#cfd8dd"
  rail: "#0e2326"
  rail-2: "#16313a"
  rail-ink: "#e4f1ef"
  rail-muted: "#93aeb0"
  ink: "#10222a"
  ink-2: "#34474f"
  muted: "#526770"
  faint: "#5f727a"
  on-signal: "#ffffff"
  accent: "#0b7d6e"
  accent-strong: "#09685c"
  accent-tint: "#e8f6f3"
  accent-edge: "#b5e2d8"
  info: "#0369a1"
  info-tint: "#eef7fd"
  info-edge: "#c4e3f6"
  ok: "#047857"
  ok-tint: "#ecfaf3"
  ok-edge: "#bde9d3"
  warn: "#b45309"
  warn-tint: "#fff8eb"
  warn-edge: "#f6dca8"
  high: "#d61f45"
  high-tint: "#fff1f3"
  high-edge: "#fac8d2"
  ai: "#6d3fd8"
  ai-tint: "#f4f1fe"
  ai-edge: "#dcd2fb"
typography:
  display:
    fontFamily: "Hanken Grotesk, Inter, Segoe UI, system-ui, sans-serif"
    fontSize: "44px"
    fontWeight: 600
    lineHeight: 1.08
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Hanken Grotesk, Inter, Segoe UI, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.015em"
  figure:
    fontFamily: "Hanken Grotesk, Inter, Segoe UI, system-ui, sans-serif"
    fontSize: "34px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
  title:
    fontFamily: "Hanken Grotesk, Inter, Segoe UI, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.015em"
  body:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "cv05, cv11"
  body-sm:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.45
  label:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "ui-monospace, Cascadia Code, SFMono-Regular, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "14px"
  2xl: "18px"
  full: "999px"
spacing:
  hairline-gap: "4px"
  row-y: "12px"
  gutter: "16px"
  card: "20px"
  section: "24px"
  page: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-signal}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.on-signal}"
  button-secondary:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.sunken}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-ghost-hover:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
  button-danger:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.high}"
    rounded: "{rounded.md}"
    padding: "0 16px"
    height: "36px"
  button-danger-hover:
    backgroundColor: "{colors.high-tint}"
  input:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
    height: "36px"
  card:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.xl}"
    padding: "{spacing.card}"
  chip-neutral:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-brand:
    backgroundColor: "{colors.accent-tint}"
    textColor: "{colors.accent}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-success:
    backgroundColor: "{colors.ok-tint}"
    textColor: "{colors.ok}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-warning:
    backgroundColor: "{colors.warn-tint}"
    textColor: "{colors.warn}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-danger:
    backgroundColor: "{colors.high-tint}"
    textColor: "{colors.high}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-info:
    backgroundColor: "{colors.info-tint}"
    textColor: "{colors.info}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  chip-violet:
    backgroundColor: "{colors.ai-tint}"
    textColor: "{colors.ai}"
    rounded: "{rounded.full}"
    padding: "1px 8px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.rail-ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  nav-item-active:
    backgroundColor: "{colors.rail-2}"
    textColor: "{colors.on-signal}"
  avatar:
    backgroundColor: "{colors.accent-tint}"
    textColor: "{colors.accent}"
    rounded: "{rounded.full}"
    size: "36px"
  avatar-alert:
    backgroundColor: "{colors.high-tint}"
    textColor: "{colors.high}"
    rounded: "{rounded.full}"
    size: "36px"
---

# Design System: CareFlow AI

## Overview

**Creative North Star: "The Calm Ward Desk"**

CareFlow reads like finished hospital software on a well-lit desk: a cool near-white canvas, white cards sitting on hairline borders with soft shadows, and a deep teal-ink sidebar that anchors the page. One teal accent carries action and selection. Everything else is quiet neutrals, so that the only loud thing on a screen is the thing that needs a clinician's attention.

Density is moderate and operational. A signed-in screen leads with what needs attention (a rose attention panel, shown only when there is something to act on), then summary figures, then lists of patients a user opens by clicking a row. Headings and figures are set in Hanken Grotesk, text and tables in Inter, all in sentence case. Motion is small and earned: rows and cards lift on hover, an arrow slides a few pixels, and sections rise once on first load.

This world replaces a dark "bedside monitor" treatment (matte black, condensed uppercase labels, channel colours, sweep and alarm-lamp motion) that the user rejected as too technical. Do not reintroduce the instrument costume.

**Key Characteristics:**
- Light, cool canvas with white cards on 1px hairline borders and soft, ink-tinted shadows.
- A deep teal-ink sidebar is the only dark surface in the app shell.
- One teal accent for primary actions, selection, links and focus.
- Status lives in pill chips: a pale tint, a readable ink, and a matching inset ring.
- Sentence case everywhere; Hanken Grotesk for headings and figures, Inter for text and tables.
- Hover lift, sliding row arrows, and a one-time staggered rise; nothing flashes.

## Colors

A cool, low-chroma neutral family around one clinical teal, with five quiet status hues that always come as tint, ink and edge.

### Primary
- **CareFlow Teal** (accent): primary buttons, the wordmark tile, selected tabs, links, focus outlines, the caret, and selected demo-account tiles. **Deep Teal** (accent-strong) is its hover and pressed state. **Teal Mist** (accent-tint) with **Teal Edge** (accent-edge) fills brand chips, neutral avatars and selected counts.

### Secondary
- **Sky Advisory** (info, with info-tint and info-edge): informational notices, scheduled and discharged statuses, appointment time blocks, and correct cells in model charts.
- **Assistant Violet** (ai, with ai-tint and ai-edge): anything the assistant authored or cited, such as the assistant label and source markers. Not a general decoration colour.

### Tertiary (status)
- **Emerald** (ok, ok-tint, ok-edge): completed, active, indexed, and factors that lower risk.
- **Amber** (warn, warn-tint, warn-edge): admitted status, moderate risk, warnings, and the synthetic-data advisory pill.
- **Clinical Rose** (high, high-tint, high-edge): critical lab results, errors, denied and failed states, no-shows, high-risk bands and factors that raise risk, and the danger button.

### Neutral
- **Cool Canvas** (field): the page background behind every signed-in screen.
- **Paper White** (panel): cards, header bar (at 90% with backdrop blur), dialogs, the sign-in form side.
- **Well** (sunken): table heads, dialog footers, row hover fill, disabled inputs.
- **Raised / Pressed** (raised, raised-2): hover and pressed fills for ghost controls, neutral chips, count pills, empty-state marks.
- **Hairline / Strong Hairline** (line, line-strong): card borders and row dividers; input borders, secondary button rings and resting row chevrons.
- **Teal Ink** (ink), **Slate Ink** (ink-2), **Muted** (muted), **Faint** (faint): primary text, secondary text and table cells, supporting lines and labels, placeholders and MRNs. Faint still clears 4.5:1 on the canvas.
- **Rail Teal-Ink** (rail) and **Rail Active** (rail-2), with **Rail Ink** (rail-ink) and **Rail Muted** (rail-muted): the sidebar and the modal and drawer scrims (rail at 35-45%).

### Named Rules
**The One Teal Rule.** Teal is the only action and selection colour. Summary figures and headings stay in ink; a figure takes colour only when the figure is itself a status.

**The Rose Means Danger Rule.** Rose is reserved for critical results, errors, denials and failures, and risk that is going up. Never use it for emphasis, branding, or a merely negative-sounding number.

**The Tint, Ink, Edge Rule.** Every status colour appears as a three-part set: pale tint fill, full-strength ink text, and a 1px inset ring in the edge tone. Never a saturated fill with white text for status.

## Typography

**Display Font:** Hanken Grotesk 500/600/700 (with Inter, Segoe UI, system-ui)
**Body Font:** Inter (with Segoe UI, system-ui, -apple-system)
**Label/Mono Font:** ui-monospace stack, only for identifiers such as MRNs, model versions, request IDs and route codes

**Character:** A friendly, slightly humanist grotesk for headings and numbers over a highly legible UI sans. The pairing reads as confident software, not as a lab instrument.

### Hierarchy
- **Display**: reserved; the sign-in headline follows the Stitch design (Inter 700, 44px) described under Layout.
- **Headline** (600, 30px, tight): the dashboard greeting and the sign-in form heading; ordinary page headers use 26px.
- **Figure** (600, 34px desktop / 28px mobile, line-height 1, -0.02em, tabular): summary card numbers.
- **Title** (600, 15-17px): card, panel, dialog and drawer titles.
- **Body** (400, 14px, 1.5): default text and table cells, tabular numerals in tables and times.
- **Body small** (400-500, 13px): row secondary lines, panel descriptions, links out of panels.
- **Label** (500, 11-13px, normal tracking, sentence case): field labels, table headings, chip text, sidebar group names.

### Named Rules
**The Sentence Case Rule.** All labels, headings, chips, table headings, nav groups and buttons are sentence case with normal tracking. No uppercase tracked labels, and no eyebrow line above a heading; the only line above the greeting is the date.

**The Tabular Figures Rule.** Numbers that are compared or scanned (tables, times, counts, figures) use tabular numerals.

## Layout

The app shell is a fixed 256px sidebar on large screens beside a fluid content column. The content column has a 64px sticky header (patient search at left, synthetic-data advisory pill at right from the xl breakpoint) and a main area capped at 1440px with 32px padding on desktop, 16px on mobile. Below lg the sidebar becomes a 288px slide-in drawer over a teal-ink scrim; below xl the advisory drops out of the header into its own full-width amber line, so it is visible on every screen.

The dashboard stacks sections 24px apart: the greeting row (heading left, primary action right), the attention panel, a row of summary cards (2 columns on mobile, 4 at xl, 3 when only three exist, 12-16px gaps), then admitted patients across two thirds with discharges in the right third at xl, then today's appointments in a two-column list. Cards pad 20px; list rows pad 12px by 20px. Wide tables scroll inside their card rather than widening the page.

Sign-in is the one deliberate exception to the light world: it reproduces the owner's Google Stitch design. A black hero (glowing emerald care core with orbiting rings, a medical cross and an ECG trace, soft emerald backlights, white 44px Inter bold headline) sits beside a white form panel (rounded-xl inputs, deep green #0a5c48 Sign in button, demo-account tiles with a 2px emerald selected border). The two halves split 1:1 at lg and stack on small screens, hero first. Its animations stop under reduced motion. Keep the rest of the product in the light system; do not spread the black hero to other screens.

## Elevation & Depth

A layered-light system: surfaces are separated first by hairline borders and tonal steps (canvas, white panel, well), then by soft shadows tinted with the ink colour rather than black. Shadows are ambient at rest and grow only in response to hover or when something floats above the page.

### Shadow Vocabulary
- **Resting** (`box-shadow: 0 1px 2px rgba(16,34,42,0.05), 0 1px 3px rgba(16,34,42,0.04)`): every card, summary card, panel and secondary button.
- **Lifted** (`box-shadow: 0 2px 4px -1px rgba(16,34,42,0.06), 0 8px 20px -6px rgba(16,34,42,0.12)`): linked cards on hover, together with a 2px upward move and a stronger border.
- **Floating** (`box-shadow: 0 24px 48px -12px rgba(16,34,42,0.24), 0 6px 14px -6px rgba(16,34,42,0.12)`): dialogs, drawers and the mobile navigation drawer.

### Named Rules
**The Lift On Intent Rule.** Surfaces rest on the resting shadow. Only something the user can open lifts, and only on hover: a 2px rise, the lifted shadow, and the row arrow sliding 2px toward teal.

## Shapes

Softly rounded, never pill-shaped for containers. Controls and small wells use 8px; cards, panels and demo-account tiles use 14px; dialogs use 18px. Chips, count pills, avatars and the advisory are full pills or circles. The wordmark tile is a 10px-rounded teal square. Borders are 1px hairlines; status shapes use a 1px inset ring rather than an outer border. Focus is a 2px teal outline offset by 2px.

## Components

### Buttons
Quiet, compact and firm.
- **Shape:** gently rounded (8px), 36px tall (32px small), 16px horizontal padding, 500 weight, icon gap 6px.
- **Primary:** teal fill with white text, a faint teal drop and inner top highlight; hover deepens to Deep Teal, press nudges down 1px.
- **Secondary:** white with a strong-hairline inset ring and resting shadow; hover to the well colour.
- **Ghost:** no fill, slate ink; hover raised fill and ink text. Icon buttons are square ghost buttons on the same 32/36px rhythm and always carry an accessible label.
- **Danger:** white with a rose ring and rose text; hover takes the rose tint. Never a solid red fill.
- **Loading / Disabled:** a spinning loader inside the button; disabled drops to 50% opacity.

### Chips
- **Style:** full pill, 11px medium text, 1px vertical and 8px horizontal padding, tint fill, ink text, inset edge ring. Status chips carry a 6px dot in the ink colour.
- **Critical values:** the value chip in the attention panel is an 8px-rounded rose block with the value in semibold tabular text; inline critical chips in patient rows carry an alert icon plus the test name and value.

### Cards / Containers
- **Corner Style:** 14px.
- **Background:** Paper White on the Cool Canvas.
- **Shadow Strategy:** resting shadow; linked cards lift on hover (see Elevation).
- **Border:** 1px hairline; the attention panel uses a rose edge with a rose-tint header strip.
- **Internal Padding:** 20px; card headers 14px by 20px with a hairline beneath and actions on the right.

### Inputs / Fields
- **Style:** white, 1px strong-hairline border, 8px radius, 36px tall (44px on sign-in), a barely-there shadow, faint placeholders. Selects use a drawn chevron rather than the OS arrow.
- **Focus:** border turns teal with a 3px teal ring at 15% opacity.
- **Error / Disabled:** the label stays; a 12px rose message appears beneath. Disabled fields take the well colour at 60% opacity.

### Navigation
- **Sidebar:** teal-ink rail with the wordmark at top, sentence-case group names in 11px Rail Muted, items at 13.5px medium with an 18px icon. Hover gives a 6% white wash; the active item takes Rail Active with white text and a mint icon. The signed-in user sits at the bottom in a translucent card with a round initials avatar and a sign-out icon button.
- **Tabs:** underlined on the card edge; the selected tab gets a 2px teal underline and ink text, with a teal-tint count pill.

### Patient Row
The signature list item. A 36px round initials avatar (teal tint, or rose tint with a rose ring when the patient has a critical result), a name in 14px medium ink, a 13px muted second line, optional right-aligned context such as ward and day of stay in tabular figures, and a chevron in the strong hairline colour. On hover the row fills with the well colour and the chevron slides 2px and turns teal.

### Attention Panel
Shown only when critical results exist. A rose-edged card with a rose-tint header: a rose dot with a slow expanding ring (2.4s, disabled under reduced motion), a sentence such as "3 critical lab results need review", a muted period, and a rose link out. Results lay out as patient rows in two columns at md, most out-of-range first, each ending in its value chip.

### Model Details Disclosure
Predictions read as a plain-language clinical estimate first: a large figure, a risk band chip, and factor bars labelled in words ("Raises risk" in rose, "Lowers risk" in emerald). Engineering provenance (model name and version, algorithm, training date, SHAP scale, error metrics) folds into a collapsed "Model details" disclosure with a rotating chevron beneath a hairline.

### Feedback
Errors are 8px-rounded rose-tint blocks with an alert icon, the message in ink and a secondary Retry button. Notices use the same shape in info, warning, success or danger tints. Empty states are a centred quiet mark in a raised circle, one factual line, and at most one action. Loading uses soft shimmer bars.

## Do's and Don'ts

### Do:
- **Do** keep the canvas light (field) with white cards on 1px hairlines and the resting shadow.
- **Do** spend teal only on actions, selection, links and focus.
- **Do** reserve rose for critical results, errors, denials and failures, and rising risk.
- **Do** pair colour with a second signal: status chips carry a dot and a word, critical chips carry an alert icon and the value text, factor bars carry "Raises risk" or "Lowers risk".
- **Do** write sentence case with normal tracking for every label, heading, chip and button.
- **Do** write user-facing copy in task language ("Here is what needs your attention today", "Review readmission risk").
- **Do** fold engineering provenance into a collapsed "Model details" disclosure.
- **Do** keep the synthetic-data advisory visible on every signed-in screen.
- **Do** limit motion to hover lift, a 2px arrow slide, and the one-time staggered rise (0.5s, 60ms steps), all removed under reduced motion.

### Don't:
- **Don't** bring back the dark bedside-monitor world: matte black fields, condensed uppercase labels, channel colours, sweep or alarm-lamp motion.
- **Don't** use uppercase tracked labels or put an eyebrow or kicker line above a heading.
- **Don't** let colour be the only signal for a status or a result.
- **Don't** narrate the access model or the engineering in user-facing copy (no "authorization-aware", "RAG" or permission talk outside administration and Model details).
- **Don't** colour summary figures for decoration; only a status figure such as a non-zero critical count turns rose.
- **Don't** use solid saturated fills for status chips or for the danger button.
- **Don't** use hard, black or offset shadows; shadows are soft and ink-tinted.
- **Don't** build an icon-tile KPI grid; summary cards lead with a label, a large figure and a context line.
