# Legal Timeline

Three Claude Code skills that turn legal documents — court opinions, complaints, motions, briefs, depositions — into interactive HTML timeline charts.

## The skills

- **`legal-case-timeline`** — Master skill. Asks for a case file, then chains the two skills below to produce both the structured JSON and the rendered chart in one workflow.
- **`legal-timeline-extraction`** — Parses a legal document into a structured 6-entity JSON: `Case`, `Party`, `Event`, `Relationship`, `Dispute`, `Source`. Date precision is a first-class field (`exact | approximate | disputed | unknown`); disputed events are encoded as separate version-events linked by a `Dispute` record; every Event traces to a `Source` citation (verbatim, e.g. `Dkt. 42 at 7`).
- **`legal-timeline-chart`** — Renders the JSON as an interactive, self-contained HTML chart. Features:
  - **Three chart styles** with auto-selection by event composition:
    - **Centered-axis** (default for single-narrative cases) — thin amber time bar through the middle, **facts above / procedure below**, with a **density-weighted axis** (empty stretches compress, busy stretches expand; ratio derived per case, ~1:4 to ~1:15) and a **width-aware label packer** that guarantees no two event labels overlap horizontally.
    - **Swimlane** (parties-as-lanes) — one horizontal track per Party / Lane, month-column grid, hover-expandable event clusters, curved-arc dispute markers.
    - **Dual-track** (facts vs procedure) — uniform linear month-column grid with one factual track on top and one procedural track on the bottom; good for appellate exhibits.
  - **Per-row dynamic vertical spacing** in centered-axis: each row's stem length is computed from its actual label height (date + wrapped lines + marker clearance) so labels never overlap markers.
  - Month-bucketed event clusters that collapse by default and hover-expand vertically (swimlane / dual-track); connected 1-hop neighbor clusters expand together so edges and dispute arcs render live.
  - Source-citation tooltips, jurisdictional-significance overlays, party-color-coded dots, and self-contained HTML output with embedded D3.js — no server, no build step.

## Quick start

1. Install Claude Code: <https://claude.com/claude-code>
2. Copy the three skill folders to your Claude skills directory:
   ```bash
   cp -r legal-case-timeline legal-timeline-extraction legal-timeline-chart ~/.claude/skills/
   ```
3. In Claude Code, say something like:
   > "I have a court opinion at `~/Downloads/case.pdf` — make a timeline chart from it."

   The master skill picks it up, confirms the file with you, runs the extraction, and renders the chart.

## What you get

The pipeline produces two artifacts:

```
<case-short-name>-timeline/
├── extraction.json     ← structured 6-entity data; portable, analyzable
└── chart.html          ← interactive chart, open in any browser
```

In **centered-axis** style (default), the chart fits in a single 1800-px-wide canvas. The time bar is density-weighted: empty months compress to as little as 1/15 the width of busy months, so a 12-year case with sporadic activity stays readable without horizontal scrolling. Hover any event dot for source citations and jurisdictional significance.

In **swimlane / dual-track** styles, the chart uses a fixed-width month-column grid (~28 px per month) and scrolls horizontally for dense cases. Hover any colored cluster badge (`2`, `3`, …) to expand it vertically into its constituent events; connected clusters expand together so you can see the relationship arrows live between them.

## Worked example: *Wanke v. AV Builder Corp.*

[`wanke-comparison/`](wanke-comparison) contains an end-to-end demonstration on a real California Court of Appeal opinion (D074392, filed 2020-02-19, 22 pages):

- [`wanke-extraction.json`](wanke-comparison/wanke-extraction.json) — full 21-event extraction in the 6-entity schema
- [`wanke-chart-centered.html`](wanke-comparison/wanke-chart-centered.html) — **centered-axis** rendering (canonical default, used in the comparison report)
- [`wanke-chart-auto.html`](wanke-comparison/wanke-chart-auto.html) — `--style auto` rendering (picks dual-track on this case: 62% factual / 38% procedural)
- [`wanke-chart-swimlane.html`](wanke-comparison/wanke-chart-swimlane.html) and [`wanke-chart-dualtrack.html`](wanke-comparison/wanke-chart-dualtrack.html) — explicit `--style swimlane` and `--style dual-track` variants for comparison
- [`report.html`](wanke-comparison/report.html) — side-by-side comparison report showing this skill's centered-axis chart next to an older Mermaid-based extractor's 7-event and 13-event outputs, with capability and event-by-event tables. Click any chart card to enlarge in a modal.

Open `wanke-comparison/report.html` in a browser to see all three charts inline plus the comparison tables.

## Evals

[`legal-timeline-extraction-workspace/iteration-1/`](legal-timeline-extraction-workspace/iteration-1) contains three synthesized test cases (FLSA opinion, complaint + counterclaim, deposition contradiction) with both with-skill and baseline runs. Aggregate benchmark: **100% pass on 31/31 assertions** for the with-skill runs vs **48.8% baseline**.

## Repository structure

```
.
├── legal-case-timeline/                          # Master skill: orchestrates extraction + chart
│   └── SKILL.md
├── legal-timeline-extraction/                    # Skill: legal document → JSON
│   ├── SKILL.md
│   ├── references/schema.md                      # 6-entity field-by-field spec
│   ├── assets/example-output.json                # Worked example (Acme v. Beta)
│   ├── scripts/render.py                         # Basic renderer
│   └── evals/evals.json
├── legal-timeline-chart/                         # Skill: JSON → interactive HTML
│   ├── SKILL.md
│   ├── references/
│   │   ├── chart-patterns.md                     # When to use swimlane vs dual-track vs centered-axis
│   │   ├── interaction-behavior.md               # Column grid, clusters, hover expansion, dot staggering
│   │   └── data-preparation.md                   # Validation rules and defaults
│   ├── assets/
│   │   ├── template.html                         # D3 template for swimlane / dual-track styles
│   │   └── template-centered-axis.html           # D3 template for centered-axis (density-weighted axis,
│   │                                             #   width-aware label packing, per-row dynamic spacing)
│   ├── scripts/render.py                         # Main rendering pipeline (--style centered-axis|swimlane|dual-track|auto)
│   └── evals/evals.json
├── legal-timeline-extraction-workspace/          # Eval workspace
│   └── iteration-1/                              # Test prompts, runs, grading, benchmark
├── wanke-comparison/                             # End-to-end worked example
└── index.html                                    # Original prototype (Acme v. Beta hypothetical)
```

## How the skills relate

The two leaf skills are independent and usable on their own:

- Use **`legal-timeline-extraction`** alone if you want the structured data for analysis (e.g., querying events by category, feeding into another tool, building a comparison chart).
- Use **`legal-timeline-chart`** alone if you already have schema-conforming JSON and just want the visualization.

The master **`legal-case-timeline`** is a thin orchestrator for the common end-to-end case. It reads each sub-skill's `SKILL.md` and follows it verbatim, so tuning either leaf skill propagates automatically — no duplicated methodology in the master.

## Design notes

The chart's visual mechanics are non-obvious and worth a read if you plan to fork or tune them.

For swimlane and dual-track, see [`legal-timeline-chart/references/interaction-behavior.md`](legal-timeline-chart/references/interaction-behavior.md):
- Why those styles use a fixed-width month-column grid instead of a continuous time axis
- How month clusters and hover expansion work, including 1-hop neighbor reveal via relationships and disputes
- The dot-slot vertical staggering algorithm (5 slots, greedy chronological assignment)
- Why disputes are rendered as curved arcs in the top margin, not as brackets through the lane
- A tunable-constants table with current defaults and "when to tune" guidance

For centered-axis, see [`legal-timeline-chart/references/chart-patterns.md`](legal-timeline-chart/references/chart-patterns.md) and the heavily-commented template at [`legal-timeline-chart/assets/template-centered-axis.html`](legal-timeline-chart/assets/template-centered-axis.html):
- How the density-weighted axis weights are derived (per-case TARGET_RATIO ∈ [4, 15] from `emptyFraction`, PER_EVENT calibrated so the busiest month hits the cap)
- The width-aware row-packer that guarantees no two same-side labels overlap horizontally
- The geometry-exact per-row stem-step formula (MARKER_RADIUS + MARKER_TO_LABEL + lines × LINE_H + LABEL_TO_DATE + DATE_ASCENT + ROW_GAP) — so markers never collide with the next row's date text
- The greedy three-pass month-label placement (Januaries → busy months sorted by event count → sparse fill at a cadence) that prevents axis label collisions in compressed regions

## Credits

Co-developed with [Claude](https://claude.com) (Anthropic, Opus 4.7).
