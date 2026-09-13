---
name: CareFlow AI
description: A hospital information platform drawn as a bedside monitor - matte black field, hairline-ruled panels, and one channel table that gives every hue a single clinical meaning.
colors:
  field: "#070707"
  rail: "#040404"
  panel: "#0f0f10"
  sunken: "#0a0a0b"
  raised: "#171718"
  raised-2: "#202022"
  line: "#1f1f21"
  line-strong: "#2e2e31"
  ink: "#ededee"
  ink-2: "#cbcbcf"
  muted: "#a3a3a8"
  faint: "#85858b"
  on-signal: "#041014"
  accent: "#38d5e6"
  accent-tint: "#14292c"
  accent-edge: "#1f5a61"
  info: "#38d5e6"
  info-tint: "#14292c"
  info-edge: "#1f5a61"
  ok: "#43de8c"
  ok-tint: "#162a20"
  ok-edge: "#235e3f"
  warn: "#f4c34a"
  warn-tint: "#2d2618"
  warn-edge: "#665326"
  high: "#ff6b6b"
  high-tint: "#2e1b1c"
  high-edge: "#6a3233"
  ai: "#b79cff"
  ai-tint: "#25212f"
  ai-edge: "#4f456b"
typography:
  display:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, Segoe UI, system-ui, sans-serif"
    fontSize: "60px"
    fontWeight: 600
    lineHeight: 0.85
    letterSpacing: "normal"
    fontFeature: "\"tnum\" 1"
  headline:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, Segoe UI, system-ui, sans-serif"
    fontSize: "28px"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "-0.005em"
  title:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "0.1em"
  body:
    fontFamily: "Inter, Segoe UI, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontFeature: "\"cv05\" 1, \"cv11\" 1"
  label:
    fontFamily: "Barlow Semi Condensed, Arial Narrow, Segoe UI, system-ui, sans-serif"
    fontSize: "11px"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.1em"
  mono:
    fontFamily: "ui-monospace, Cascadia Code, SFMono-Regular, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  sm: "0.25rem"
  md: "0.375rem"
  lg: "0.5rem"
  xl: "0.625rem"
spacing:
  hairline: "1px"
  xs: "6px"
  sm: "10px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-signal}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "#62e0ee"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.raised-2}"
  button-ghost:
    textColor: "{colors.ink-2}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "36px"
  button-danger:
    backgroundColor: "{colors.high-tint}"
    textColor: "{colors.high}"
    rounded: "{rounded.md}"
    padding: "0 14px"
    height: "36px"
  input:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
    height: "36px"
  input-focus:
    backgroundColor: "{colors.panel}"
  status-tag:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink-2}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "1px 6px"
  status-tag-high:
    backgroundColor: "{colors.high-tint}"
    textColor: "{colors.high}"
    rounded: "{rounded.sm}"
  panel:
    backgroundColor: "{colors.panel}"
    rounded: "{rounded.lg}"
    padding: "16px"
  channel-cell:
    backgroundColor: "{colors.panel}"
    textColor: "{colors.ink}"
    typography: "{typography.display}"
    padding: "14px 16px 12px"
  tab-key:
    backgroundColor: "{colors.sunken}"
    textColor: "{colors.muted}"
    typography: "{typography.title}"
    padding: "8px 14px"
  tab-key-selected:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.ink}"
  advisory-band:
    backgroundColor: "{colors.warn-tint}"
    textColor: "{colors.warn}"
    typography: "{typography.label}"
    padding: "6px 24px"
---

# Design System: CareFlow AI

## Overview

**Creative North Star: "The Bedside Monitor"**

CareFlow AI is drawn as a central monitoring station. The scene is a clinician glancing between patients beside monitor-adjacent equipment, so the field is matte black, the planes are flat, and nothing on screen is lit unless it means something. Every figure is a channel at a fixed position: a condensed uppercase label in its clinical colour, a near-white monitor-scale numeric in tabular figures, and a quiet line of context beneath. Prose and tables recede into a neutral sans so the channels read first.

Density is high but ordered. Instruments are built from flush cells that share 1px rules rather than floating as separate cards, and the grid never moves: when data refreshes a thin sweep line crosses each channel and changed values settle in place. Colour is never decoration. One channel table supplies every hue on screen, and each hue carries exactly one meaning, so a red lamp is an alarm and nothing else.

The world refuses the SaaS dashboard grammar: same-size KPI cards with icon tiles, gradient text, decorative blur, soft pill tags and card shadows. Honesty about state is part of the surface: every value declares whether it is live, stale, untimed or withheld, and every time is labelled with its zone.

**Key Characteristics:**
- Matte black field with neutral greys of near-equal RGB, never blue slate; `color-scheme: dark`.
- One channel table (cyan, green, yellow, red, violet) is the only source of hue.
- Depth by 1px rules; only floating layers cast a shadow.
- Barlow Semi Condensed for channel labels, headings and numerics; Inter for prose and tables.
- Small radii, rectangular tags, square lamps.
- One authored motion: the monitor sweep with value-settle; a 2 Hz alarm lamp for high priority.

## Colors

A near-black instrument face with five saturated signal hues, each paired with a dark tint (fill) and a mid edge (rule).

### Primary
- **Monitor Cyan** (accent): the navigable channel. Primary buttons, links, focus rings, the caret, the lit lamp on the active nav item and the underline on the selected tab. Selection uses its edge.
- **Advisory Cyan** (info): the same hue in its clinical role - scheduled, advisory, low priority, discharged, outpatient times. Kept as a separate token so role stays legible in code even though the value matches accent.

### Secondary
- **Census Green** (ok): census, stable, active, indexed, completed; clinical-access marks on the login role strip; the logo pulse.
- **Caution Yellow** (warn): medium priority - admitted, abnormal, processing, recent-discharge review; the standing synthetic-data advisory.
- **Alarm Red** (high): high priority - critical results, failed, denied, no-show, request errors. Never used to mark model error.

### Tertiary
- **Retrieval Violet** (ai): retrieval and model output - RAG routes, AI query channels, assistant provenance.

Each signal has a **-tint** (panel fill behind that channel's band or tag) and an **-edge** (its ring or rule). Text on a tint is always the signal colour or ink.

### Neutral
- **Field Black** (field): page background and top bar. **Rail Black** (rail) sits one step deeper under the navigation rail.
- **Panel** (panel): every instrument cell, card and dialog face. **Sunken** (sunken): inputs, table heads, tab strips, modal footers. **Raised / Raised 2** (raised, raised-2): hover and selected rows, secondary buttons, skeleton shimmer.
- **Rule** (line) and **Strong Rule** (line-strong): hairline dividers between cells and rows; strong rules for control strokes, table heads, overlays and scrollbar thumbs.
- **Ink ramp**: ink for values and names, ink-2 for panel titles and secondary text, muted for context and field labels, faint for disabled marks, empty values and unlit lamps. **On-signal** is the dark text on a lit cyan key.

### Named Rules
**The Channel Table Rule.** Hue exists only in the channel table, and each hue has one meaning. If a colour is not accent, info, ok, warn, high or ai, it is a neutral.

**The Near-White Value Rule.** The label and the top rule carry the channel colour; the number stays near-white so it reads first. Colour arrives on a value only while it settles.

**The Red Means Alarm Rule.** Red marks a clinical alarm, a failure or a denial. Wrong model predictions render neutral, correct ones advisory cyan.

## Typography

**Display Font:** Barlow Semi Condensed 500/600/700 (with Arial Narrow, Segoe UI, system-ui), self-hosted via next/font
**Body Font:** Inter (with Segoe UI, system-ui, -apple-system), self-hosted via next/font, `cv05` and `cv11` on
**Label/Mono Font:** ui-monospace stack for MRNs, staff codes, ward codes, request IDs and route tags

**Character:** A condensed grotesk in the register of monitor readouts carries every label and numeric; a quiet, even sans carries sentences and table cells so the readouts stay dominant.

### Hierarchy
- **Display** (600, 60px desktop / 44px mobile, 0.85): channel numerics in the station strip. Smaller numeric readouts use the same face: 40px on the login role strip, 32px in StatCard, 26px day-of-stay, 18px alarm values and appointment times. The login hero headline runs 48px at 1.02.
- **Headline** (600, 28px, 1, -0.005em): page titles. Sign-in heading 30px. Modal and drawer titles 15px uppercase 0.06em.
- **Title** (600, 13px, uppercase, 0.08-0.1em): panel and section headers, channel labels (12px mobile), tab keys (0.06em), empty-state titles.
- **Body** (400/500, 14px, 1.5): prose, table cells, names. Context lines 12px muted; secondary lines 11px. Subtitles cap at `max-w-3xl`.
- **Label** (600, 11px, uppercase, 0.1-0.14em): field labels, table column heads, state tags, nav group names, key-value terms.

### Named Rules
**The Readout Face Rule.** Anything a clinician compares or scans - labels, units, counts, times, codes on alarms - is set in Barlow Semi Condensed. Sentences never are.

**The Tabular Rule.** Tables, `<time>` and every `.tabular` value use tabular figures so digits align down a column and do not jitter on refresh.

## Layout

A fixed 240px navigation rail on the left (hidden below `md`, replaced by a 256px slide-in drawer) and a sticky 56px top bar holding patient search and the station clock. Directly beneath the top bar sits the standing synthetic-data advisory band, full width. Content is centred to a 1560px maximum with 16px gutters on mobile and 24px from `md`.

Instruments stack with 16px between them. Inside an instrument, cells sit flush on a `gap: 1px` grid over the rule colour inside a small-radius border, so the rules are shared rather than doubled. The station strip is 2 columns, 4 from `xl`; the admin strip 3 from `sm`; census and discharges split two thirds and one third from `xl`; alarm entries 2 columns from `sm`, 4 from `xl`, with only the first three shown on mobile and a "+ N more" link.

Rhythm: panel headers 16px x 10px; panel bodies 16px; list rows 16px x 10px; controls 32px (sm) or 36px (md) tall. Every channel cell reserves a fixed 20px label row so numerics share a baseline.

**Every value declares its state.** Channels and the page stamp carry a square lamp and one of: **Live** (green lamp), **Stale** (older than 3 minutes, yellow), **No timestamp** (faint), **Not permitted** (the value becomes an em dash, the rule goes neutral, context reads "Requires clinical access"). The station refreshes every 60 seconds.

**Hospital time.** All clock and schedule times render in hospital time, which is UTC in this demo, and are always labelled "UTC". This is a recorded deferral: showing IST requires a backend timezone change.

## Elevation & Depth

The system is flat. Depth comes from tonal planes (rail below field below panel below raised) and 1px rules; resting instruments, cards, tags and buttons cast no shadow. Only layers that float over content cast one, and those overlays sit on a 60-70% black scrim with no blur.

### Shadow Vocabulary
- **Float** (`box-shadow: 0 18px 44px -12px rgba(0,0,0,0.75), 0 4px 10px -4px rgba(0,0,0,0.6)`): modal, drawer, mobile navigation drawer, patient search results.
- **e1** (`0 1px 0 rgba(255,255,255,0.02)`) and **e2** (`0 2px 6px -1px rgba(0,0,0,0.45)`) are defined tokens with no sanctioned resting use.

### Named Rules
**The Shared Rule Rule.** Instruments are flush cells sharing hairlines, never gapped cards with individual borders or shadows.

**The Only Floaters Cast Rule.** A shadow means the layer is above the page. If it is not a modal, drawer or popover result list, it is flat.

## Shapes

Hard-edged and small. Radii run 0.25rem (sm: status tags, instrument outlines, alarm bar, ward codes, skeleton bars, key hints) to 0.375rem (md: buttons, inputs, notices, avatar) to 0.5rem (lg: panels, tab strips, modals, search results); 0.625rem (xl) is the ceiling. Status tags are rectangular and lettered; lamps are unrounded squares (6px in tags and rows, 8-10px on bands). Channel cells carry a 1px coloured top rule; the selected tab carries a 2px cyan bottom rule. The only gradient in the system is the readmission-risk scale, where the green-yellow-red ramp is the data.

## Components

### Buttons
Monitor keys: flat, hard-edged, lit only by meaning.
- **Shape:** gently squared (0.375rem), 36px tall with 14px sides (32px / 10px small), 14px medium Inter.
- **Primary:** the one lit key - cyan face with dark on-signal text; lightens on hover, deepens on press.
- **Secondary:** raised plane with an inset strong-rule ring; steps to raised-2 on hover.
- **Ghost:** ink-2 text, raised plane on hover.
- **Danger:** high tint with red text and a red-edge inset ring.
- **Icon key:** square 32/36px, muted glyph, raised on hover; always carries an accessible label.
- **Hover / Focus:** 150ms colour transition only, no lift. Focus is a 2px cyan outline offset 2px, globally. Disabled at 45% opacity.

### Status Tags
- **Style:** 11px uppercase Barlow at 0.06em on the channel tint, signal-colour text, 1px inset edge ring, 0.25rem radius, optional square lamp.
- **Mapping:** status words resolve through one table (active/completed/indexed green; admitted/processing/abnormal yellow; scheduled/discharged/uploading cyan; critical/failed/denied/no-show red; inactive/cancelled neutral). Route tags use mono at 10px: SQL cyan, RAG violet, ML yellow, SIMILARITY accent, LLM neutral.

### Cards / Containers
- **Corner Style:** 0.5rem for standalone panels; 0.25rem for multi-cell instruments.
- **Background:** panel on field.
- **Shadow Strategy:** none (see Elevation & Depth).
- **Border:** 1px rule; header separated by a rule.
- **Internal Padding:** 16px; header 16px x 10px with a 13px uppercase title in ink-2. Wide content scrolls inside the panel.

### Inputs / Fields
- **Style:** sunken fill, 1px strong-rule stroke, 0.375rem radius, 36px tall, faint placeholder. Selects are native with a drawn chevron.
- **Focus:** stroke turns cyan, fill lifts to panel, 2px cyan ring at 25%.
- **Labels:** 11px uppercase Barlow in muted above; hints 11px muted; errors 11px red.
- **Native chrome:** date-picker indicators are inverted to read on dark; the caret is cyan; selection is cyan edge with ink text; `.scroll-thin` scrollbars use a strong-rule thumb.

### Navigation
- **Rail:** rail-black column, 17px uppercase wordmark (CareFlow in ink, AI in cyan), 11px faint uppercase group names, 13px Inter items with 16px line icons.
- **States:** muted at rest, panel on hover, raised with ink text and a cyan icon when active, plus a square cyan lamp at the right edge.
- **Tabs:** a flat strip of labelled keys on sunken, divided by rules; selected key raised, ink, count in cyan, 2px cyan underline.
- **Mobile:** the rail becomes a slide-in drawer over a 70% scrim.

### Channel Cell (signature)
A fixed-position readout: 1px top rule in the channel colour, a 20px row with the coloured label and state tag, a 60px near-white tabular numeric with a unit beside it, and one muted context line. On each refresh a sweep line in the channel colour crosses the cell left to right (1.1s, ease-out-expo) and a changed value settles from the channel colour to ink (1.2s, ease-out-quart). Linked cells step to raised on hover.

### Alarm Bar (signature)
A red-tint band with a red edge listing every critical result, ordered by distance outside the reference range: code and value in 18px bold red Barlow, patient and MRN, reference range and age. Its lamp flashes at 2 Hz with a 50% duty cycle (0.5s, stepped), inside the IEC 60601-1-8 high-priority band. With no criticals the band turns green-tint "No critical results"; for non-clinical roles it is a neutral "Alarm feed" notice. Census rows with an alarm carry the same flashing lamp and value.

### Advisory Band
The synthetic-data notice under the top bar: warn tint, warn-edge bottom rule, square yellow lamp, 12px uppercase yellow Barlow. Always present on authenticated screens and never dismissible.

### Motion
Motion is limited to the sweep, value-settle, the alarm lamp, overlay entry (fade 160ms, rise 200ms, slide 220ms) and loading (shimmer, spinner, dot pulse). Under `prefers-reduced-motion` every animation and transition collapses to 0.01ms and the alarm lamp stops flashing, holding steady.

## Do's and Don'ts

### Do:
- **Do** take every hue from the channel table and use it for its one meaning; pair fills with the matching -tint and rules with the matching -edge.
- **Do** build instruments from flush cells on a 1px gap over the rule colour inside a 0.25rem border.
- **Do** keep numerics near-white in Barlow Semi Condensed with tabular figures; put the colour on the label and top rule.
- **Do** declare each value's state (Live, Stale after 3 minutes, No timestamp, Not permitted) with a square lamp.
- **Do** label every displayed time "UTC" while hospital time is UTC.
- **Do** keep the synthetic-data advisory visible and non-dismissible under the top bar.
- **Do** refresh in place with the sweep and value-settle; never reflow the grid on refresh.
- **Do** honour reduced motion by stopping the alarm lamp and collapsing all animation.

### Don't:
- **Don't** add hues outside the channel table or use neutral greys with a blue cast.
- **Don't** use red for model error, wrong predictions or decoration.
- **Don't** give resting panels, cards or buttons a shadow; shadows belong to modal, drawer and popover results only.
- **Don't** build same-size KPI cards with icon tiles.
- **Don't** place eyebrow labels above headings.
- **Don't** use gradient text, decorative blur or glow; the risk scale is the only gradient because the ramp is the data.
- **Don't** use pill-shaped tags or round lamps; tags are rectangular and lamps are square.
- **Don't** flash anything other than a high-priority alarm lamp.
