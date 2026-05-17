# Interaction Behavior

The visual mechanics that make the chart readable under real-world density. Read this when you need to understand *why* the chart looks the way it does, or when you're tuning a constant.

## Why these mechanics exist

A real legal case has clusters: eight events in six months around the litigation trigger, then long stretches with no activity. A continuous time axis with all labels rendered inline produces a wall of overlapping text in dense regions and waste in sparse ones. The chart resolves this through five interlocking mechanisms:

1. Fixed-width month-column grid (replaces continuous time axis)
2. Month-bucketed event clusters (collapses multi-event months by default)
3. Hover-expansion with 1-hop neighbor reveal (interactive disclosure)
4. Vertical dot-slot staggering (prevents adjacent label collisions)
5. Curved-arc dispute markers (keeps dispute annotation out of the lane)

Each one has a small set of tunable constants in `assets/template.html`. The defaults below are tuned for typical case densities (15–30 events over 5–15 years). For unusually dense cases, the cluster behavior absorbs the load; for extremely sparse cases, the chart still renders cleanly.

## 1. Fixed-width month-column grid

**The change:** Instead of `d3.scaleTime()` mapping dates linearly to pixels, every calendar month in `case.date_range` gets a column of equal width.

```
COL_WIDTH = 28        // pixels per month
innerW    = months.length * COL_WIDTH
width     = innerW + margin.left + margin.right
```

**`xScale(date)`** is a custom function (not a d3 scale instance) that floors the date to the start of its month and returns the center of that month's column:

```js
function xScale(date) {
  const t = +d3.timeMonth.floor(date);
  const idx = monthIndex.get(t);   // monthIndex is a Map from epoch-ms → column index
  return idx * COL_WIDTH + COL_WIDTH / 2;
}
```

**Why this matters:**
- Dec 23, 2013 and Jan 1, 2014 are 9 days apart on a continuous time axis but they're now in **adjacent month columns** — visually one column apart, no accidental overlap from being temporally close.
- Every dot sits at a column center. Day-of-month no longer affects placement.
- The user can scan year by year and the chart reads like a Gantt sheet.

**Trade-off:** the chart becomes wider than the viewport for any case spanning more than ~40 months. **Horizontal scrolling is intentional and required.** The chart container has `overflow-x: auto`. Don't try to make the chart fit a single screen by shrinking `COL_WIDTH` below ~24 — labels start to clip.

## 2. Month-bucketed event clusters

**Cluster key:** `${lane_id}|${YYYY-MM}`. Every event in the same lane and the same calendar month forms one cluster.

```js
const clusters = [];                          // {id, key, events, lane_id, x, size, month, dotSlotY}
const eventToCluster = new Map();             // event.id → {cluster, index}
```

**Default rendering:**
- **Single-event clusters** (`size === 1`) render as a normal event dot at the column center.
- **Multi-event clusters** (`size > 1`) render as one **cluster marker** by default: a colored circle (`r = 12`) with the event count inside (`"3"`) and the month label below (`"Dec 2013"`).

The cluster marker is **larger than a regular dot** (`r = 12` vs `r = 5`) so it visibly signals "this is a group, not a single event."

## 3. Hover expansion with 1-hop neighbor reveal

**Trigger:** `mouseenter` on a cluster marker (or click). The renderer:

1. Hides the cluster marker.
2. Renders each event in the cluster vertically stacked at the column's x position. Each event row takes `STACK_STEP = 52 px` (enough for dot + label + date + buffer).
3. Computes the **1-hop neighbors** of the cluster — every other cluster that shares at least one relationship or dispute version with an event in the hovered cluster — and expands them too.
4. Re-renders relationships and dispute arcs. Only edges between **currently visible** events are drawn.

**Collapse behavior:**
- `mouseleave` on a cluster marker (or on any event in an expanded cluster) starts a 280 ms collapse timer.
- `mouseenter` on any other cluster marker or any event in an expanded cluster **cancels** the pending collapse.
- So the user can move the mouse between a cluster, its neighbor, and the events inside both without anything snapping shut. Stop moving for ~300 ms and everything collapses back to overview.

**The 1-hop neighbor reveal is what makes the chart usable for legal narratives.** Expanding a single cluster while hiding the events on the other side of an edge would defeat the purpose. The point of a relationship is that both ends matter; the renderer treats expansion as a graph operation, not a per-cluster toggle.

**Implementation note:** dispute versions are treated as a neighbor-edge too. Hovering one disputed event expands both versions and draws the connecting arc.

## 4. Vertical dot-slot staggering

The single biggest readability win for dense lanes.

**The problem:** Adjacent month columns are only 28 px apart, but a truncated label is ~125 px wide. Two adjacent column dots both centered on the lane line would have labels that collide horizontally.

**The fix:** When two clusters in the same lane are within `MIN_X_GAP = 150 px` of each other, the renderer assigns them different vertical **slots**. The dot itself moves vertically; the label follows.

```js
const DOT_SLOTS_Y = [0, 80, -80, 140, -140];   // y-offsets from lane centerline
const MIN_X_GAP   = 150;                        // px
```

**Assignment is greedy and chronological per lane:**

```js
const lastX = DOT_SLOTS_Y.map(() => -Infinity);
sortedClusters.forEach(cluster => {
  let chosen = 0;
  for (let i = 0; i < DOT_SLOTS_Y.length; i++) {
    if (cluster.x - lastX[i] > MIN_X_GAP) { chosen = i; break; }
  }
  cluster.dotSlotY = DOT_SLOTS_Y[chosen];
  lastX[chosen] = cluster.x;
});
```

**Visual result:**
- Sparse regions: most clusters sit at slot 0 (lane centerline).
- Dense regions: clusters stair-step into ±80 and ±140 slots, so labels never share a y-coordinate with a horizontally-close neighbor's label.

**Labels are now always rendered at a single fixed offset below their dot** (`y_label = 22`). The 5-slot label-staggering system from earlier iterations is gone — moving the *dot* covers the same need more reliably.

**Slot offset rationale:**
- `±80` is wide enough that a 2-event expanded cluster (spanning ±26 from its slot center) at slot 0 doesn't collide with a single dot at slot 1 (y=80).
- `±140` is the safety net for very dense lanes (5+ clusters within 150 px), though hitting slot 4 is rare in practice.

If you tune these, keep `STACK_STEP * (max_events_in_cluster / 2) + label_height < adjacent_slot_offset` to preserve clearance.

## 5. Curved-arc dispute marker

**The change from earlier versions:** previously a rectangular bracket connected disputed event pairs. The bracket's vertical lines crossed event labels that happened to sit between the two endpoints. Now disputes use a smooth curved arc that rises into the **top margin** (above the time axis), so it never touches the lane area.

```js
const arcTopY = -32;  // y in the chart's coordinate space (above the time axis at y=0)
disputeG.append("path")
  .attr("d", `M${x1},${y1-10} C${x1},${arcTopY} ${x2},${arcTopY} ${x2},${y2-10}`)
  .attr("class", "dispute-bracket");
```

**The label:** at the arc's peak. Wraps to two lines if longer than 70 characters (uses `<tspan>` elements). A red diamond marker `◆` sits at the peak as a clear "this is a dispute" indicator.

**Multiple disputes:** stack on tiers. Each new dispute's arc sits 22 px higher than the previous one (`tierTop = arcTopY - i * 22`). So if a case has 3 disputes, the highest arc is 76 px above the time axis. Plan `margin.top` accordingly (default `95 px`).

## Constants reference

The constants the renderer cares about, with their current defaults and tuning notes:

| Constant | Default | What it controls | When to tune |
|---|---|---|---|
| `COL_WIDTH` | `28` px | Width of each month column | Wider columns for very short timelines; narrower for 20+ year cases |
| `STACK_STEP` | `52` px | Distance between rows in an expanded cluster | Increase if event labels are long (decrease only with caution) |
| `DOT_SLOTS_Y` | `[0, 80, -80, 140, -140]` | Vertical positions for staggered dots | Wider gaps for very dense lanes |
| `MIN_X_GAP` | `150` px | Min horizontal distance before triggering vertical stagger | Lower (e.g., 100) if labels can be shorter |
| `MAX_LABEL_CHARS` | `22` | Where label text is truncated | Lower for narrower COL_WIDTH |
| `laneHeight` | `340` px | Height per lane | Bump if you increase any slot offset |
| `margin.top` | `95` px | Top margin (room for axis + dispute arcs) | Bump for 3+ disputes |
| `arcTopY` | `-32` | Where dispute arc apex sits (negative = into top margin) | Move higher (more negative) for crowded disputes |
| Collapse timeout | `280 ms` | How long after mouseleave before clusters collapse | Bump if users have slower trackpad reactions |

## What got dropped along the way

For future debugging: a few approaches were tried and rejected during the tuning process. Don't re-introduce them without good reason.

- **5-slot label staggering** (positioning labels at multiple y-offsets relative to a centerline dot) — solved the wrong half of the problem. Adjacent dots sitting at the same y position can't have their labels staggered enough to avoid overlap when columns are 28 px apart. Dot staggering supersedes it.
- **X-jitter for same-date events** — produced side-by-side dots that visually competed for the same "spot in time" without making the legal facts any clearer. Replaced with vertical stacking inside the cluster (which is what users expect when two events happened "on the same day").
- **Rectangular dispute brackets** — their vertical sides crossed through event labels in the lane. Replaced with the curved arc that lives in the top margin.
- **Responsive SVG (`width: 100%`)** — caused horizontal labels to overlap when the iframe was narrower than the chart's natural width. Replaced with fixed-width SVG + horizontal scroll inside the chart container.
- **Inlining the chart into a parent HTML page with namespaced CSS** — works but is brittle. Use `<iframe srcdoc="...">` instead (see SKILL.md "Embedding the chart").
