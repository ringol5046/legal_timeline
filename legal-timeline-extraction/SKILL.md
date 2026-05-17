---
name: legal-timeline-extraction
description: Extracts timeline data from legal documents (court opinions, complaints, motions, briefs, deposition transcripts, dockets, scheduling orders, declarations) into a structured 6-entity JSON schema covering Case, Party, Event, Relationship, Dispute, and Source. The output is built to drive a swimlane + disputed-fact timeline diagram. Use this skill whenever the user shares a legal document and asks about a timeline, chronology, sequence of events, procedural history, dispute over dates, statute-of-limitations analysis, who-did-what-when, or wants to visualize the case as a diagram, swimlane, or gantt — even if they don't explicitly say "extract." Phrases like "build a timeline of this case", "chart the procedural history", "when did things happen", "map out this dispute", or "I want a visual of this case" should trigger it. This skill complements legal-issue-extraction (which extracts legal issues and holdings) — use both when the user wants both *what was decided* and *what happened when*.
---

# Legal Timeline Extraction

This skill converts narrative legal documents into a structured timeline data model designed for analysis and visualization.

## Why this exists

Legal narratives mix procedural and factual events, contain genuine disputes over dates and occurrences, and rely on citations that get lost when summarized. A flat chronological list of bullets loses three things that matter:

- **Who** an event belongs to (which party, which proceeding — i.e. which swimlane on a chart)
- **How** events relate (a filing answering a motion is different from a fact causing another fact, which is different from a notice that tolls a deadline)
- **What** is contested (Plaintiff says X happened on Tuesday; Defendant says Wednesday — both belong in the data, not one collapsed entry that papers over the dispute)

The schema captures all three so the data is both analyzable (queries like "what triggered the SoL clock?") and renderable (the JSON drops directly into a timeline diagram).

## When to use

Trigger this skill whenever a user:

- Shares a court opinion, complaint, motion, brief, deposition transcript, declaration, docket, or scheduling order
- Asks about the chronology, timeline, sequence of events, or procedural history of a case
- Wants to compare what happened on different dates, or wants statute-of-limitations / laches / accrual analysis
- Asks for a visual or chartable representation of the case events (timeline, swimlane, gantt, network)
- Mentions disputes over when something happened or who did what when
- Wants the output of legal-issue-extraction grounded in a chronology

Use this skill *in addition* to legal-issue-extraction when the user wants both *what was decided* (issues, holdings) and *what happened when* (events, dates, relationships).

## The six entities at a glance

The output JSON has six top-level arrays plus a derived `lanes` view. Read `references/schema.md` for the full field-by-field specification including enum values, required vs optional, and examples. The summary:

| Entity | What it captures | Anchors |
|---|---|---|
| **Case** | Root metadata: caption, court, docket, axis bounds, status | The whole document |
| **Party** | Every actor: plaintiff, defendant, court, witness, third party. Role + type | Events, Disputes |
| **Event** | A point or duration in time. Has lane, party_ids, date_certainty, kind, category, sources | The chart itself |
| **Relationship** | Typed edges between events: response, causal, tolls, supersedes, contradicts, references | Two Events |
| **Dispute** | A disagreement about when/whether an event happened. Links competing versions | Two or more Events |
| **Source** | An evidentiary citation: Dkt., Ex., Dep. line ranges. Authenticity status | Events, Disputes |

## Extraction methodology

Follow these steps in order. The order matters: parties anchor events; events anchor relationships and disputes; sources anchor everything as evidence.

### Step 1: Read the whole document first

Skim once to identify document type (opinion vs complaint vs brief), the major actors, and the citation conventions in use ("Dkt. 42 at 7", "Ex. A", "Smith Dep. 88:3-12"). Preserve these verbatim later — they are how lawyers and judges navigate the record, and normalizing them destroys their utility.

Note that opinions and motions often describe the same events from different vantage points. An opinion is usually the safest source for procedural events; underlying filings and depositions are the safest sources for factual events.

### Step 2: Extract Case and Party records

Pull the caption, court, docket number, and the date range that bounds the case. Identify every named actor and give each a stable, snake_case `id` (e.g., `acme_corp`, `beta_llc`, `court_sdny`, `judge_smith`). 

Don't conflate Party with Lane. A single defendant who countersues is one Party — they may appear on two lanes later (Defendant and Counterclaimant), but they remain one Party record.

### Step 3: Extract Events

For each event the document mentions:

- Capture the date with appropriate `date_certainty`:
  - `exact` — a specific date is given
  - `approximate` — "late March 2023", "Q2 2024", "spring of that year"
  - `disputed` — only when parties affirmatively disagree on the date (see Step 4)
  - `unknown` — referenced but undated
- Use `date_range: [start, end]` instead of `date` for durations (period of employment, ongoing breach, discovery window).
- Assign `kind` (broad type, drives visual styling): `fact | filing | ruling | discovery | settlement | external`
- Assign `category` (legal sub-type, drives filtering): e.g., `contract | breach | notice | motion | order | testimony | payment | meeting`
- Set `jurisdictional_significance` when the event tolls a clock, satisfies a condition precedent, or triggers a notice/cure period. This is the "why does this date matter legally" field — leave it blank when not applicable rather than padding it.
- Always attach `source_ids` pointing to one or more Source records that support the event.

A common trap: don't paraphrase dates into the `label`. "Around March 2023" should be encoded as `date_certainty: "approximate"` with an estimated date, not stuffed into the label text where downstream tools can't reason about it.

### Step 4: Extract Disputes and disputed Events

When parties disagree on whether or when an event happened — this is the heart of contested litigation:

1. Create **one Event per party's version**. Each version's `lane_id` is that party's lane. Each carries its own `source_ids` (because each side relies on different exhibits / testimony).
2. Create a **Dispute** record listing:
   - `subject` — what is disputed ("date defect notice was given", "whether meeting occurred")
   - `type` — `date | occurrence | meaning | attribution`
   - `versions` — pointers to each Event with the asserting party
   - `resolution` — `unresolved | stipulated | adjudicated_for_<party_id>`
3. Set `date_certainty: "disputed"` on each version Event.

Why this matters: a single merged event ("Defect notice (date disputed)") loses the evidentiary independence of each version. Each side may rely on different exhibits, witnesses, and inferences — and the dispute itself may be the dispositive question (e.g., for cure-period analysis).

### Step 5: Extract Relationships

For each pair of related events, create a Relationship with a typed edge. The six types are not arbitrary — each has distinct legal meaning:

- **response** — a filing answers another filing (Complaint → MTD → Order on MTD). Drives the procedural arc.
- **causal** — Event B happened because of Event A as a factual matter (breach → demand letter). Drives the factual arc.
- **tolls** — Event A starts, pauses, or extends a clock (notice triggers cure period; tolling agreement pauses SoL; bankruptcy stay halts proceedings). Critical for limitations analysis.
- **supersedes** — Event B replaces Event A (amended complaint supersedes original; superseding contract). Downstream renderers may visually fade the superseded event.
- **contradicts** — used when one side cites A and the other cites B as inconsistent. Note: this is a *meta* relationship about the evidence, distinct from a Dispute about a single event.
- **references** — A is cited by B (an order that cites prior testimony; a brief that quotes a deposition). Useful for tracing how the record is built up.

Set `strength` to `alleged | undisputed | adjudicated` so downstream code can render strength of inference. Only encode relationships explicitly stated or obviously implied — when in doubt, leave it out and let the user add edges by hand.

### Step 6: Extract Sources

Every Event should be traceable to at least one Source. Preserve the original citation format **exactly** — `Dkt. 42 at 7`, `Smith Dep. 88:3-12`, `Ex. 14`. Don't normalize.

Record `authenticity` when the document reveals it: `stipulated | challenged | not_yet_offered`. If unknown, leave it null.

An Event with no Source isn't necessarily wrong — sometimes facts are recited without citation — but `source_ids: []` is a signal that the user may want to add a citation before relying on the entry.

## Output format

Return a single JSON object with this top-level shape:

```json
{
  "case": { ... },
  "parties": [ ... ],
  "events": [ ... ],
  "relationships": [ ... ],
  "disputes": [ ... ],
  "sources": [ ... ],
  "lanes": [ ... ]
}
```

`lanes` is a derived view — a suggested mapping from parties (and optionally proceedings) to swimlanes for diagram rendering. Default to one lane per Party with role ∈ {plaintiff, defendant} plus a "court" lane. See `references/schema.md` for how to populate it.

See `assets/example-output.json` for a complete worked example covering a contract dispute with parties, disputed dates, and the full procedural arc.

## Rendering as a diagram

The output JSON can be rendered as a self-contained interactive HTML timeline:

```bash
python3 scripts/render.py <input.json> <output.html>
```

This produces a file using the swimlane + disputed-fact pattern: parties as lanes, events as dots (hollow + red bracket for disputed), typed connector arrows between events. Open in any browser.

## Common pitfalls

- **Don't drop sources to save time.** A timeline without citations is a story, not evidence. If a citation isn't in the document, set `source_ids: []` rather than fabricating one.
- **Don't merge disputed events.** Two versions of "when defect notice was given" are *two events*, not one event with a flag.
- **Don't invent relationships.** Only encode edges the document supports. The user can add inferred edges later.
- **Don't collapse Party / Lane.** Defendants who counterclaim are one Party shown on two lanes — not two parties.
- **Don't paraphrase dates into labels.** Use `date_certainty` instead.
- **Preserve citation format exactly.** "Dkt. 42 at 7" is not the same as "Docket entry 42, page 7" to a lawyer scanning a brief.

## See also

- `references/schema.md` — full schema with enums, required fields, and per-field notes
- `assets/example-output.json` — complete worked example (Acme v. Beta contract dispute)
- `scripts/render.py` — renders extracted JSON into a self-contained HTML timeline
