# Chart Patterns

When to use each chart style, what data shape each needs, and what each one emphasizes (and de-emphasizes) about the case.

## Pattern 1: Swimlane

### What it looks like

Horizontal tracks, one per party (or per lane), running left-to-right along a **fixed-width month-column grid**. Events render as colored dots positioned at the center of their month column. Connector arrows between dots show response or causal relationships. Disputed events appear hollow with a curved red arc (in the top margin) linking the two parties' versions.

Multiple events in the same month and lane **collapse into a single cluster marker** by default; hovering the marker expands the cluster into its constituent events stacked vertically, and also expands any other clusters connected via relationships or disputes. See `interaction-behavior.md` for the full mechanics.

### When to use it

- The user asks **"who did what when?"**
- There are 2+ parties with substantial activity on each side
- Procedural responsiveness matters (motion → opposition → reply → order)
- You want to show **parallel activity** — both sides preparing for trial, or two defendants taking different positions

### What it shows well

- Cross-party responses (filings answering filings)
- Procedural rhythm: who moved, who answered, when the court ruled
- Multi-defendant divergence (when defendants act differently)
- Asymmetric activity (one side filing constantly, the other barely responding)

### What it underplays

- The factual story leading up to litigation (because facts and filings share lanes — facts feel ancillary)
- Duration-heavy events (employment periods, ongoing breaches) — point-style dots flatten time
- Relationships between events on the **same** lane (they're harder to see than cross-lane relationships)

### Data requirements

- At least one Lane (the renderer can infer from Parties if missing, but explicit is better)
- Events with `lane_id` set
- Optional but enriches the chart: Relationships (typed edges), Disputes (with versions), Sources (for tooltip citations)

---

## Pattern 2: Dual-track (facts vs procedure)

### What it looks like

Two fixed horizontal tracks on the same month-column grid: top = factual events, bottom = procedural events. Events are color-coded by party but assigned to the appropriate track based on `kind`. Disputed-fact arcs still appear, rising into the top margin above the factual track.

Multi-event months still collapse into cluster markers (one per lane per month). Hovering a cluster on either track can also expand a neighbor cluster on the *other* track when they're linked by a relationship or dispute — which is exactly the visual you want for, e.g., "the factual breach triggered the procedural filing four months later."

### When to use it

- The user asks **"what happened, and how did the litigation respond?"**
- Appellate briefs (especially statement of the case)
- Statute of limitations analysis (when did the claim accrue? when did it get filed?)
- Explaining the case to non-lawyer audiences (judges in unrelated specialties, clients, juries)
- Cases where the procedural arc is long and you want to separate it from the underlying events

### What it shows well

- **Accrual** — the gap between what happened and when suit was filed
- **Tolling** — periods when the SoL clock paused (tolling arrows render across the gap between the factual event that triggered tolling and the procedural events that followed)
- The narrative arc — facts at top read as the "story", procedure at bottom reads as the "case"
- Cases with sparse procedural activity but dense facts (or vice versa)

### What it underplays

- Per-party activity (because parties don't get their own lanes; you lose the "Plaintiff's lane vs Defendant's lane" framing)
- Cross-defendant differences (everything defendants do collapses into the procedural track)
- Multi-proceeding parallelism (criminal + civil + bankruptcy — there's no good place to put each)

### Data requirements

Same as swimlane, but `kind` field becomes load-bearing. Every event needs a meaningful `kind`:
- Factual track: `kind ∈ {fact, external}`
- Procedural track: `kind ∈ {filing, ruling, discovery, settlement}`

If `kind` is missing on many events, the renderer should default and warn — but the chart will be less informative.

---

## Pattern 3: Centered-axis

A thin horizontal date axis runs through the middle of the chart. Events are placed above OR below the axis as colored markers connected to the axis by short vertical stems. There are no lanes — every event sits on the same time axis. Lane colors are preserved on the dots so party identity is still legible without giving each party its own track.

### Use when

- The case is a single linear narrative (one plaintiff, one defendant) — no per-party divergence to highlight
- Event count is moderate (~10–30) — too few looks empty, too many overflows even with the packer
- The story matters more than the actor — e.g., a medical-treatment chronology for a personal-injury complaint, a single-arc procedural history
- The reader is consuming the chart visually (presentation slide, exhibit, brief illustration) rather than interactively querying it

### Avoid when

- Multi-party comparison is the point (use **Swimlane**)
- Facts-vs-procedure separation is the point (use **Dual-track**)
- You have > 30 events with long labels (the packer can place them, but the chart gets very tall)

### Layout invariants

The renderer uses a width-aware row packer to guarantee no two event labels overlap horizontally:

1. Each event's label width is estimated from its wrapped text (`LABEL_WRAP_CHARS = 26` chars per line).
2. For each event in chronological order, the packer finds the lowest-index row on each side (above / below the axis) whose previous label's right edge clears this event's left edge with a small gap (`MIN_LABEL_GAP_PX = 10`).
3. The event is placed on whichever side has the lower best-fit row; ties alternate, so balanced data zigzags.
4. The chart height is derived from the deepest row actually used on each side, so sparse timelines stay compact and dense ones grow vertically.

### Data requirements

Same as swimlane. Lane colors flow through to dot fill. If `lanes` is empty, every event renders in the same color.

---

## Decision guide

| If the user emphasizes... | Use |
|---|---|
| "Who did what" / "the parties' positions" / "responses to filings" | **Swimlane** |
| "The story of the case" / "what happened then sued" / "accrual" / "statute of limitations" | **Dual-track** |
| "An appellate brief" / "the statement of the case" | **Dual-track** |
| "Multiple parties" / "co-defendants" / "third-party witness" | **Swimlane** |
| "A visual for a slide / brief exhibit" / "linear chronology" / "medical timeline" | **Centered-axis** |
| Nothing in particular | **Swimlane** (safer default) |

### The 30/30 heuristic for auto-style

When `--style auto`, the renderer picks dual-track only if:
- `≥ 30%` of events are factual (`kind ∈ {fact, external}`) AND
- `≥ 30%` of events are procedural (`kind ∈ {filing, ruling, discovery, settlement}`)

Otherwise, default to swimlane. This avoids dual-track in cases where one track would be nearly empty.

### When to render both

If the case is important and the user has time, render both. They're cheap and emphasize different things. Show the swimlane first (it answers more questions) and offer the dual-track as a follow-up.

---

## Sizing and scrolling

The chart is laid out on a fixed-width month-column grid (`COL_WIDTH = 28 px` per month). The total chart width is therefore proportional to the case's date range, not to the viewport. For typical legal cases:

- **5-year case:** ~60 months → ~1680 px wide. Fits most monitors but scrolls on narrow viewports.
- **12-year case** (typical for appellate work): ~144 months → ~4000 px wide. Always scrolls horizontally.
- **20+ year case** (estate, IP, regulatory): consider tightening `COL_WIDTH` to 20–22, accepting some label-clipping risk.

**The chart container has `overflow-x: auto`**. This is intentional. Do not redesign to "fit a single screen" — labels and event spacing depend on the column grid having room.

## Patterns this skill does NOT (yet) render

The following patterns exist in the design vocabulary but aren't implemented here. If the user explicitly asks for them, explain that and offer the closest available substitute.

- **Gantt** — events as bars showing duration. Useful for employment cases, ongoing breaches, contract terms. Closest substitute: swimlane with `date_range` on duration-events (the existing template uses `date_range[0]` as the anchor month).
- **Dependency network** — events as nodes, edges as relationships, no strict time axis. Useful for fraud schemes, complex causal chains. Closest substitute: a swimlane with all clusters expanded and only causal/response edges visible.
- **Multi-proceeding parallel tracks** — one lane per proceeding (civil/criminal/bankruptcy/regulatory). Closest substitute: a swimlane with one Lane per `proceeding` (the schema supports this via `Lane.proceeding`).

Future iterations may add Gantt and multi-proceeding as first-class styles.
