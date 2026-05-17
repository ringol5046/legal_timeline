# Legal Timeline

Three Claude Code skills that turn legal documents — court opinions, complaints, motions, briefs, depositions — into interactive HTML timeline charts.

## The skills

- **`legal-case-timeline`** — Master skill. Asks for a case file, then chains the two skills below to produce both the structured JSON and the rendered chart in one workflow.
- **`legal-timeline-extraction`** — Parses a legal document into a structured 6-entity JSON: `Case`, `Party`, `Event`, `Relationship`, `Dispute`, `Source`. Date precision is a first-class field (`exact | approximate | disputed | unknown`); disputed events are encoded as separate version-events linked by a `Dispute` record; every Event traces to a `Source` citation (verbatim, e.g. `Dkt. 42 at 7`).
- **`legal-timeline-chart`** — Renders the JSON as an interactive, self-contained HTML chart. Features:
  - Swimlane (parties-as-lanes) and dual-track (facts vs procedure) styles, with auto-selection by event composition (30/30 heuristic).
  - Fixed-width month-column grid (one column per calendar month).
  - Month-bucketed event clusters that collapse by default and hover-expand vertically; connected 1-hop neighbor clusters expand together so edges and dispute arcs render live.
  - Vertical dot staggering across five y-slots so adjacent column labels never overlap horizontally.
  - Curved-arc dispute markers that rise into the top margin (no crossings through lane labels).
  - Self-contained HTML output with embedded D3.js — no server, no build step.

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

The chart scrolls horizontally for dense cases (~28 px per month column). Hover any colored cluster badge (`2`, `3`, …) to expand it vertically into its constituent events; connected clusters expand together so you can see the relationship arrows live between them.

## Worked example: *Wanke v. AV Builder Corp.*

[`wanke-comparison/`](wanke-comparison) contains an end-to-end demonstration on a real California Court of Appeal opinion (D074392, filed 2020-02-19, 22 pages):

- [`wanke-extraction.json`](wanke-comparison/wanke-extraction.json) — full 21-event extraction in the 6-entity schema
- [`wanke-chart-auto.html`](wanke-comparison/wanke-chart-auto.html) — auto-picked dual-track (62% factual / 38% procedural)
- [`wanke-chart-swimlane.html`](wanke-comparison/wanke-chart-swimlane.html) and [`wanke-chart-dualtrack.html`](wanke-comparison/wanke-chart-dualtrack.html) — explicit style variants
- [`report.html`](wanke-comparison/report.html) — side-by-side comparison report showing this skill's chart next to an older Mermaid-based extractor's 7-event and 13-event outputs, with capability and event-by-event tables

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
│   │   ├── chart-patterns.md                     # When to use swimlane vs dual-track
│   │   ├── interaction-behavior.md               # Column grid, clusters, hover expansion, dot staggering
│   │   └── data-preparation.md                   # Validation rules and defaults
│   ├── assets/template.html                      # D3 template
│   ├── scripts/render.py                         # Main rendering pipeline
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

The chart's visual mechanics are non-obvious and worth a read if you plan to fork or tune them. See [`legal-timeline-chart/references/interaction-behavior.md`](legal-timeline-chart/references/interaction-behavior.md) — it documents:

- Why the chart uses a fixed-width month-column grid instead of a continuous time axis
- How month clusters and hover expansion work, including 1-hop neighbor reveal via relationships and disputes
- The dot-slot vertical staggering algorithm (5 slots, greedy chronological assignment)
- Why disputes are rendered as curved arcs in the top margin, not as brackets through the lane
- A tunable-constants table with current defaults and "when to tune" guidance
- A "what got dropped along the way" section so you don't re-introduce approaches that were tried and rejected

## Credits

Co-developed with [Claude](https://claude.com) (Anthropic, Opus 4.7).
