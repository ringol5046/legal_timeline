---
name: legal-timeline-chart
description: Renders structured legal-timeline data into interactive, self-contained HTML timeline diagrams on a fixed-width month-column grid with hover-expandable event clusters, vertical dot staggering for readability, and curved-arc dispute markers. Supports swimlane (parties-as-lanes) and dual-track (facts vs procedure) chart styles, smart style selection, data validation, and graceful handling of incomplete inputs. Use this skill whenever the user has timeline data (JSON, or a structured list of events) and asks to render, visualize, chart, diagram, draw, plot, or display it. Especially trigger when the user has just run the legal-timeline-extraction skill and wants to see the result visualized, or when they ask to "build the chart", "show me the timeline", "make a swimlane", "draw the diagram", "render this", or "turn this into a visual." Also use if a user wants to compare the same case in two views (e.g., switch from a parties-as-lanes view to a facts-vs-procedure view). Complements legal-timeline-extraction: that skill produces the data; this skill produces the visual. For non-legal data visualization, prefer d3-viz instead.
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
- Asks to "chart this", "diagram this", "render the timeline", "build the swimlane", "draw it out", or similar
- Wants to switch between chart styles (e.g., "show me the same case as facts vs procedure" — that's a dual-track view request)
- Has a partial event list and wants something charted from it (handle gracefully — don't reject for missing fields)

Don't trigger for:
- Initial extraction from a legal document (that's legal-timeline-extraction)
- General data visualization or non-legal charts (use d3-viz)
- Static images / non-interactive charts (this skill produces interactive HTML)

## The two chart styles

This skill supports two chart patterns. Pick deliberately based on the question being asked:

### Swimlane (default)

**Use when:** the user cares about *who did what when* — which party took which action, who responded to whom, and how the procedural arc unfolded.

Layout: one horizontal track per Party (or Lane), with the court on its own track. Events render as colored dots on a fixed-width **month-column grid**; arrows connect related events across lanes. Disputed events are hollow with a curved red arc linking competing versions (the arc rises into the top margin so it never crosses any event label).

Best for: most cases. The "who" axis is usually what trial lawyers and clients want to see.

### Dual-track (facts vs procedure)

**Use when:** the user wants to separate *what happened in the world* from *what happened in court*. Common for appellate briefs, SoL analysis, or explaining the case to non-lawyer audiences.

Layout: two horizontal tracks — top = factual events (`kind ∈ {fact, external}`), bottom = procedural events (`kind ∈ {filing, ruling, discovery, settlement}`). Disputed-fact branching still works within the factual track.

Best for: appellate work, where the *accrual* of the claim (factual track) is conceptually distinct from the *litigation* of the claim (procedural track), and you want to show how the procedural clock relates to the underlying events.

### How to choose

If the user specifies a style, use it. Otherwise the renderer's `--style auto` mode (the default) picks one:

- **Choose dual-track** if `≥ 30%` of events are factual AND `≥ 30%` are procedural — meaning both tracks would have meaningful content. Also choose dual-track if the user mentions appellate brief, statute of limitations, accrual, claim ripeness, or "story of the case."
- **Choose swimlane** otherwise. It's the safer default — most cases have a clear party structure and benefit from the who-did-what framing.

When in doubt, render both. They're cheap to produce. See `references/chart-patterns.md` for fuller guidance.

## Layout and interaction model

The renderer uses a few interlocking design decisions that the user will notice. The full mechanics are in `references/interaction-behavior.md`; the short version:

- **Fixed-width month-column grid.** Each calendar month in `case.date_range` gets its own column of equal width (`COL_WIDTH = 28 px`). Events sit at the horizontal center of their month's column. Total chart width = `months × 28 + margins`. For a 12-year case, the chart is ~4000 px wide and **scrolls horizontally** inside the chart container — this is intentional and aids readability for dense cases.
- **Month-bucketed event clusters.** Multiple events in the same month and lane collapse by default into a single colored marker showing the event count (`2`, `3`, etc.) with the month label below it.
- **Hover expansion.** Hovering a cluster marker expands it vertically into its constituent events. The renderer also expands any **1-hop neighbor clusters** — clusters connected by a relationship or by a shared dispute — so the edges drawn live between them are immediately visible.
- **Vertical dot staggering.** When two events or clusters in the same lane are within `MIN_X_GAP = 150 px` of each other, the second one gets pushed onto a different y-slot (the dot itself moves vertically, not just its label). Five slots are available: `[0, +80, −80, +140, −140]`. This means adjacent month-columns never have horizontally-colliding labels — they're always at different y positions.
- **Curved-arc dispute markers.** Disputed event pairs are connected by a smooth Bezier arc that rises into the top margin and never crosses event labels. A red diamond (◆) marker sits at the arc's peak with the dispute subject as the label.
- **Year-prominent / month-quiet axis.** Year labels (e.g., `2014`) are bold above each January column; quarter month labels (`Apr`, `Jul`, `Oct`) are muted between years. Vertical gridlines: light per-month, darker per-year.

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

Decide between swimlane and dual-track per the heuristic above, or honor the user's stated preference.

### Step 4: Render

```bash
python3 scripts/render.py <input.json> <output.html> [--style swimlane|dual-track|auto]
```

The script substitutes data into the template and writes a self-contained HTML file. Tooltips include source citations and jurisdictional significance when present.

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
- `assets/template.html` — the HTML/D3 template (single template, data-driven for both styles)
- `scripts/render.py` — the main rendering pipeline with validation, style selection, and data transformation
- Sister skill: `legal-timeline-extraction` — produces the input JSON
