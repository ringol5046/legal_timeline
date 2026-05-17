# Data Preparation

How `render.py` validates and prepares input data before rendering. Read this when you need to understand what the renderer reads, what it tolerates, and what it warns about.

## Validation passes

The renderer runs these checks in order. A check that fails *blocks* rendering only if the data would be unsalvageable; otherwise the renderer warns and proceeds with a best-effort fix.

### 1. Top-level shape

- **Required**: at least `events` array with one or more entries.
- **Strongly recommended**: `lanes`, `case`, `sources`. The renderer fills in defaults for any missing top-level array.
- **If missing**: warn, default to empty arrays, continue.

### 2. Per-event checks

For each event:

| Check | Behavior on failure |
|---|---|
| Has `date` or `date_range` parseable as ISO (YYYY-MM-DD) | Drop event with warning |
| Has `lane_id` matching a Lane | Try to infer from `party_ids[0]` → matching Lane's party_id; if no match, place on a synthetic "unassigned" lane and warn |
| Has `label` | Default to `"(unlabeled event)"` and warn |
| `date_certainty` in {exact, approximate, disputed, unknown} | Default to `exact` |
| `kind` in {fact, filing, ruling, discovery, settlement, external} | Default to `fact` |
| `source_ids` references existing Sources | Warn (don't drop the event; legal data is often incomplete) |

### 3. Lane inference

If the input has events with `party_ids` but no `lanes` array, the renderer derives lanes from Parties:

1. Take all unique parties referenced by events
2. Sort by role priority: plaintiff → defendant → counterclaimant → third_party → witness → court
3. Add a Court lane at the bottom if any event has `kind ∈ {filing, ruling, discovery, settlement}`
4. Assign colors from the default palette (`#2b6cb0`, `#b04a2b`, `#6b46c1`, `#4a5568`)

This is a best-effort inference. If the user has specific lane needs (e.g., separating a counterclaimant onto their own lane), they should provide `lanes` explicitly.

### 4. Date range (now load-bearing)

`case.date_range` is more important than it used to be — it directly determines **how many month columns** the chart renders. The renderer floors the start to the beginning of its month and offsets the end to the start of the month *after* its month, then generates one column per calendar month in between.

If `case.date_range` is missing, derive it from event dates:

- Start: earliest event date minus 3 months
- End: latest event date plus 3 months

This gives the chart room to breathe at the edges *and* keeps the chart from looking lopsided when all the action happens at the start or end.

**Events whose date falls outside `case.date_range`** still render — they get clamped to the first or last month column (rather than being dropped). Warn so the user can fix the source data if the date is a typo.

### 5. Month-column granularity

Day-of-month no longer affects horizontal position. Two events on different days of the same month land at the *same column center*. If two events in the same lane are in the same month, they form a **cluster** (see `interaction-behavior.md`) — they don't try to render side-by-side or pixel-jittered.

This means:
- Don't bother with precise day-level date precision in source data; month-level is sufficient for rendering.
- If multiple events on the same day must be visually distinguished, they appear in the cluster's vertical stack when expanded.

### 6. Source references

Events reference Sources via `source_ids[]`. If an `source_id` doesn't match an actual Source record, warn (the citation tooltip will fall back to just the event detail). Don't drop the event.

### 7. Relationship references

Relationships reference events via `from_event_id` and `to_event_id`. If either doesn't match an event, drop the relationship with a warning.

**Relationships are now relevant to layout, not just visuals**: when a user hovers a cluster, the renderer expands every other cluster that shares a relationship with this one. So accurate relationship data improves the chart's interactive readability — be conservative about adding speculative edges.

### 8. Dispute versions

A Dispute should have at least 2 versions pointing to distinct Events. If only 1 version exists (or the version events don't have `disputed: true`), warn but render — the dispute arc simply won't appear.

Disputes also participate in cluster-expansion: hovering a cluster that contains a disputed event expands every cluster holding another version of the same dispute, so the arc is drawn live.

## Field defaults summary

When a field is missing, the renderer uses:

```
event.date_certainty     -> "exact"
event.kind               -> "fact"
event.category           -> null (no filter applied)
event.party_ids          -> []
event.source_ids         -> []
event.detail             -> ""
event.disputed           -> false
event.lane_id            -> inferred from party_ids[0], else "unassigned"

lane.color               -> assigned from default palette
lane.sub                 -> "" (just shows main label)
lane.order               -> array index

case.date_range          -> derived from event dates with 3-month padding
case.caption             -> "Case Timeline"
case.court               -> ""
case.summary             -> ""
```

## Handling minimal input

A user may hand the skill data that doesn't conform to the full 6-entity schema — for example, just a list of events from a spreadsheet:

```json
{
  "events": [
    { "label": "Contract signed", "date": "2022-03-15" },
    { "label": "Breach", "date": "2023-04-20" },
    { "label": "Complaint filed", "date": "2023-08-01" }
  ]
}
```

The renderer should handle this gracefully:
1. Derive lanes — without `party_ids`, fall back to a single "Timeline" lane
2. Derive date range from events
3. Default all missing fields
4. Render with whatever it has, and report to the user what was filled in

Don't reject minimal input. The user can iterate by adding more fields.

## Edge cases worth warning the user about

- **All events on one date.** Renders as one cluster marker (size = N). Hovering expands them vertically — still readable, but the user may want to check the data for date precision.
- **Events outside the case `date_range`.** Clamped to the first or last month column with a warning. Usually indicates a typo in the data.
- **More than 50 events.** Charts get crowded *horizontally* — the chart can be 5000+ pixels wide. The clustering absorbs vertical density well, but consider filtering (e.g., procedural-only) for narrower outputs.
- **More than 8 events in the same month and lane.** They'll all stack vertically when the cluster expands; the expansion gets tall (8 × 52 = ~420 px). Consider whether the events are really in the same month or whether the dates are imprecise.
- **No relationships.** The chart still renders, just without connector arrows *and* without the 1-hop expansion behavior on hover. Note this — the user may want to add edges to get the most out of the interactive disclosure.
- **Disputed event with only one version.** Single hollow dot, no arc. Note this — the user probably meant to encode both versions but missed one.
- **Very long date range (>20 years).** Chart becomes very wide (>5500 px). Consider trimming the range or tightening `COL_WIDTH` (in `assets/template.html`).

## Output the renderer adds

Beyond rendering the chart itself, `render.py` prints a short report to stdout:

```
Rendered: <output.html>
  Style: dual-track (auto: 62% factual, 38% procedural)
  Events: 21 · Lanes: 2 · Disputes: 1 · Relationships: 12
  Open: file:///.../output.html
```

The chart itself also embeds a yellow **warnings banner** at the top when validation surfaced issues, so the user sees them next to the visualization. The banner lists each issue inline (e.g., "Event e_orphan: lane_id 'wexford' not found in lanes; placed on 'unassigned'").

This report-on-the-chart pattern lets the user see what got rendered, what got fixed up, and what to clean up in the source data — all in one place.
