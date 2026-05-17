---
name: legal-timeline-chart
description: Renders structured legal-timeline data into interactive, self-contained HTML timeline diagrams. Supports three chart styles — swimlane (parties-as-lanes), dual-track (facts vs procedure), and centered-axis (thin axis through the middle with density-weighted time, facts above and procedure below, and a width-aware label packer that guarantees no two event labels overlap horizontally). Auto-selects a style based on the case's event composition, validates input, and gracefully handles incomplete data. Use this skill whenever the user has timeline data (JSON, or a structured list of events) and asks to render, visualize, chart, diagram, draw, plot, or display it. Especially trigger when the user has just run the legal-timeline-extraction skill and wants to see the result visualized, or when they ask to "build the chart", "show me the timeline", "make a swimlane", "draw the diagram", "render this", or "turn this into a visual." Also use if a user wants to compare the same case in two views (e.g., switch from a parties-as-lanes view to a facts-vs-procedure view). Complements legal-timeline-extraction: that skill produces the data; this skill produces the visual. For non-legal data visualization, prefer d3-viz instead.
---

# Legal Timeline Chart

Turns structured timeline data into an interactive, self-contained HTML chart. The output is a single file with embedded D3.js — open it in any browser, no server required.

## Why this exists

Once you have structured timeline data (from legal-timeline-extraction or any compatible source), there's a real design question about *how* to render it. The same data can be charted as parties-as-lanes, facts-vs-procedure, gantt-style for durations, or a network of relationships. Each emphasizes a different aspect of the case. This skill encodes the judgment about which view fits which question, plus the rendering pipeline.

It also handles two messy realities:
1. **Incoming data is often incomplete** — missing lane assignments, no party records, inconsistent date formats. Rather than failing, this skill validates, warns, and fills in sensible defaults before rendering.
2. **Real legal cases are visually dense** — eight events in a six-month window, multiple events on the same day, disputes spanning years. The renderer handles density through month-bucketed clustering with hover-expansion, vertical dot staggering, and edge-filtered relationships.

## When to use

Trigger whenever a user:

- Has timeline data (JSON conforming to the legal-timeline-extraction schema, or close to it) and wants a visualization
- Just ran legal-timeline-extraction and asks to render the output
- Asks to "chart this", "diagram this", "render the timeline", "build the swimlane", "make the centered axis chart", "draw it out", or similar
- Wants to switch between chart styles (e.g., "show me the same case as facts vs procedure" — that's a dual-track view request)
- Has a partial event list and wants something charted from it (handle gracefully — don't reject for missing fields)

Don't trigger for:
- Initial extraction from a legal document (that's legal-timeline-extraction)
- General data visualization or non-legal charts (use d3-viz)
- Static images / non-interactive charts (this skill produces interactive HTML)

## The three chart styles

This skill supports three chart patterns. Pick deliberately based on the question being asked:

### Centered-axis (recommended for most cases)

**Use when:** the user wants a clean linear story of the case, suitable for a presentation slide, brief exhibit, or one-page case summary. Especially good when the case has both factual events and procedural events but is fundamentally a single narrative (one plaintiff, one defendant) rather than a multi-party comparison.

Layout: a thin amber date bar runs through the *middle* of the chart. **Facts** (`kind ∈ {fact, external}`) sit above the axis; **procedure** (`kind ∈ {filing, ruling, discovery, settlement}`) sits below. The time axis itself is **density-weighted** — months with many events expand, empty months compress (target ratio derived per case: ~1:4 for dense cases, up to ~1:15 for sparse). A width-aware row packer guarantees no two event labels on the same side ever overlap horizontally. Lane color is preserved on each dot so party identity is still legible.

Best for: 10–30 events spanning multiple years with both factual and procedural arcs; readers who consume the chart visually rather than interactively querying it.

### Swimlane

**Use when:** the user cares about *who did what when* — which party took which action, who responded to whom, and how the procedural arc unfolded across multiple parties.

Layout: one horizontal track per Party (or Lane), with the court on its own track. Events render as colored dots on a fixed-width **month-column grid**; arrows connect related events across lanes. Disputed events are hollow with a curved red arc linking competing versions (the arc rises into the top margin so it never crosses any event label).

Best for: multi-party cases, co-defendant differentiation, third-party witnesses, parallel-proceeding tracks.

### Dual-track (facts vs procedure)

**Use when:** the user wants the strict facts-vs-procedure separation without the centered axis's density weighting — e.g., for printed appellate exhibits where uniform horizontal scaling matters.

Layout: two horizontal tracks on a uniform month-column grid — top = factual events, bottom = procedural events. Disputed-fact branching still works within the factual track.

Best for: appellate briefs, SoL/accrual analysis, comparison charts where x-axis time must be linear.

### How to choose

If the user specifies a style, use it. Otherwise the renderer's `--style auto` mode (the default) picks one:

- **Choose dual-track** if `≥ 30%` of events are factual AND `≥ 30%` are procedural AND the user signals a need for linear time (appellate brief, SoL clock).
- **Choose centered-axis** when both tracks would have content and the case is a single-narrative arc (no multi-party comparison emphasis), especially for visual / presentation use.
- **Choose swimlane** when the user emphasizes parties, multi-defendant comparison, or "who did what when."

When in doubt, render the centered-axis first and offer the swimlane as a follow-up. See `references/chart-patterns.md` for fuller guidance.

## Layout and interaction model

The renderer uses a few interlocking design decisions. Some apply to all styles; some are specific to swimlane / dual-track or to centered-axis. Full mechanics are in `references/interaction-behavior.md`; short version:

### Common to all styles

- **Source-citation tooltips.** Every event dot reveals its sources, `jurisdictional_significance`, and lane on hover.
- **Self-contained HTML output.** Each chart is one file with embedded D3.js — no server, no build step, no relative dependencies.

### Swimlane / dual-track specifics

- **Fixed-width month-column grid.** Each calendar month in `case.date_range` gets its own column of equal width (`COL_WIDTH = 28 px`). Events sit at the horizontal center of their month's column. Total chart width = `months × 28 + margins`. The chart **scrolls horizontally** for dense cases.
- **Month-bucketed event clusters.** Multiple events in the same month and lane collapse by default into a single colored marker showing the event count.
- **Hover expansion.** Hovering a cluster marker expands it vertically into its constituent events. The renderer also expands any **1-hop neighbor clusters** so the edges between them render live.
- **Vertical dot staggering.** Five y-slots `[0, +80, −80, +140, −140]` prevent adjacent month-columns from having horizontally-colliding labels.
- **Curved-arc dispute markers.** Disputed event pairs are connected by a smooth Bezier arc that rises into the top margin and never crosses event labels.

### Centered-axis specifics

- **Density-weighted time axis.** Each calendar month is given a weight derived from its event count (`BASE_WEIGHT + count × PER_EVENT`, capped). The axis is then sliced in proportion to those weights, so busy stretches expand and empty stretches compress. The target empty-to-busy ratio (between 1:4 and 1:15) is itself computed from the case's overall empty-month fraction — sparse cases compress more aggressively.
- **Facts above / procedure below.** Side is fixed by `event.kind`: `fact`/`external` → above; `filing`/`ruling`/`discovery`/`settlement` → below. Small **FACTS** and **PROCEDURE** track labels appear at the left edge when both sides have events.
- **Width-aware row packing.** Each label's pixel width is estimated from its wrapped text; events get assigned to rows on their side such that no two labels overlap horizontally. The chart adds rows only as needed — sparse cases stay shallow, dense ones grow vertically.
- **Per-row dynamic stem length.** Row N+1's stem is placed cumulatively above row N using the geometry-exact formula `MARKER_RADIUS + MARKER_TO_LABEL + (lines_N − 1) × LINE_H + LABEL_TO_DATE + DATE_ASCENT + ROW_GAP`, so a 1-line row only takes ~63 px before the next row starts and a 3-line row takes ~91 px — never less than what the label-block actually occupies, never more.
- **Greedy three-pass month-label placement.** Every label reserves a slot of width `clamp(avgPxPerMonth × 1.6, 26..56)`. Pass 1 places all Januaries, pass 2 places busy months sorted by event count, pass 3 fills sparse regions at a cadence. A candidate is accepted only if its slot doesn't overlap any already-placed slot — so month names never collide.
- **Color = party, position = kind.** Lane color flows through to each dot's fill, so party identity is still legible even though events aren't on per-party lanes.

### Year-prominent / month-quiet axis (all styles)

Year labels are emphasized. In centered-axis style, busy months are labeled in bold and sparse months in muted gray; in swimlane / dual-track, every 3rd month gets a quiet label and Januaries get a prominent year label above.

## Workflow

### Step 1: Load the input

The input is a JSON object. The full schema is documented in the legal-timeline-extraction skill at `legal-timeline-extraction/references/schema.md`. The minimum viable input is:

```json
{
  "case": { "date_range": ["2020-01-01", "2024-12-31"] },
  "events": [
    { "id": "e1", "label": "...", "date": "2023-01-15", "lane_id": "..." }
  ],
  "lanes": [
    { "id": "...", "label": "..." }
  ]
}
```

`case.date_range` is now load-bearing: it determines the month columns the chart renders. If omitted, the renderer derives it from the events with 3 months of padding on each side.

Other fields are optional but enrich the output. Read `references/data-preparation.md` for the full set of fields the renderer reads and how it falls back when they're missing.

### Step 2: Validate and prepare the data

Run validation before rendering. The `scripts/render.py` script does this automatically:

- Verifies each event has a `date` (or `date_range`) that parses as ISO format
- Verifies each event's `lane_id` matches a Lane (or infers a Lane from `party_ids`)
- Defaults missing `date_certainty` to `exact`
- Defaults missing `kind` to `fact`
- Warns when sources are missing (doesn't reject — legal data is often incomplete)

If validation surfaces issues, report them to the user before rendering. Don't silently fix things that change the legal meaning of the data (e.g., don't guess at a disputed-event flag).

### Step 3: Pick a chart style

Decide between centered-axis, swimlane, and dual-track per the heuristic above, or honor the user's stated preference.

### Step 4: Render

```bash
python3 scripts/render.py <input.json> <output.html> [--style centered-axis|swimlane|dual-track|auto]
```

The script substitutes data into the appropriate template (`assets/template.html` for swimlane/dual-track, `assets/template-centered-axis.html` for centered-axis) and writes a self-contained HTML file. Tooltips include source citations and jurisdictional significance when present.

### Step 5: Report

Tell the user:
- Which chart style was used and why
- How many events / lanes / disputes / relationships render
- How many month-clusters formed (especially if any contain multiple events that the user can hover to expand)
- Any validation warnings worth knowing about (missing citations, dropped events, etc.)
- Where the output file is saved
- That the chart scrolls horizontally — the user shouldn't expect everything to fit in a single screen for dense cases

## Embedding the chart in another HTML document

A frequent follow-up is to embed the rendered chart inside a larger report or comparison page. Two patterns work; one fails:

- **`<iframe srcdoc="..." sandbox="allow-scripts allow-same-origin">`** — preferred. The chart HTML is embedded inline as a string in the `srcdoc` attribute (HTML-escape `&`, `<`, `>`, and `"`). The iframe runs the chart in an isolated document context, bypassing both file:// cross-origin issues and parent-CSS conflicts.
- **Inlined fragment with namespaced CSS/IDs** — works, but requires renaming the chart's element IDs and prefixing every CSS selector with a scope (e.g., `#nc-root`). The output is brittle.
- **`<iframe src="chart.html">`** — fails on file://. Browsers treat file:// iframes as cross-origin to their file:// parent, blocking scripts. Don't use this.

## Common pitfalls

- **Don't silently drop data to make the chart look clean.** If an event has no date, surface it to the user rather than discarding. They may want to fix the source data.
- **Don't auto-fix disputed events.** If two events share a date and label but are flagged as disputed versions, that's a legal fact the renderer must preserve. Don't dedupe them.
- **Don't strip source citations.** Citation tooltips are the difference between a chart and an exhibit. Always include them when present.
- **Don't pick dual-track just because the case has both fact and procedural events.** Most cases do. Use the 30%/30% heuristic, or ask.
- **Don't try to make the chart fit a single screen width for dense cases.** The chart is designed for horizontal scrolling — that's how it stays readable.
- **Don't shrink `STACK_STEP` to compact expanded clusters.** Each row in an expanded cluster needs ~52 px to fit its dot, label, and date without colliding with the next row.

## See also

- `references/chart-patterns.md` — when to use each style, with examples
- `references/interaction-behavior.md` — the column grid, clustering, hover expansion, dot staggering, dispute arc — the visual mechanics in detail
- `references/data-preparation.md` — validation rules, default inference, edge cases
- `assets/template.html` — HTML/D3 template for the swimlane and dual-track styles (one template, data-driven for both)
- `assets/template-centered-axis.html` — HTML/D3 template for the centered-axis style (thin axis, density-weighted time, width-aware label packing, per-row dynamic vertical spacing)
- `scripts/render.py` — the main rendering pipeline with validation, style selection, and data transformation
- Sister skill: `legal-timeline-extraction` — produces the input JSON
