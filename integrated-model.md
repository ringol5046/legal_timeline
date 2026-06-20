# Integrated Legal Case Visualization — Data Model & Diagram

How to fuse four views — **entity-relation diagram**, **timeline**, **mind map**, and **comparison chart** — into one coordinated artifact, and exactly what data feeds it.

---

## 1. The core insight: you already have two data spines

Your project is built on two independent extraction schemas. They are not competitors — they are two halves of one model.

| Spine | Schema | Unit | Feeds |
|---|---|---|---|
| **Event spine** | `legal-timeline-extraction` (6-entity) | one **Event** in time | Timeline, Entity-Relation diagram |
| **Issue spine** | `legal-issue-extraction` (34-field C-V P4.1) | one **Issue** decided | Mind map, Comparison chart |

The issue schema *already anticipated* the merge: field 8 `show_in_views` enumerates `["comparison_chart", "appellate_issue_map", "trial_issue_diagram", "mind_map", "reasoning_tree", "oral_outline", "citation_panel"]`. The design intent was always one record set → many views.

The two spines **already share three entity types**: `Case`, `Party`, `Source`. So unification is not a rewrite — it's adding **one bridge table**.

---

## 2. The unified data model

```
                    ┌─────────────────────────────┐
                    │           Case (1)          │   ← shared root
                    └─────────────────────────────┘
                                  │
        ┌─────────────────────────┴─────────────────────────┐
   SHARED CORE                                          
        │                                                     
   ┌─────────┐   ┌─────────┐                                 
   │ Party[] │   │ Source[]│   (referenced by BOTH spines)   
   └─────────┘   └─────────┘                                 
        │             │                                       
   ┌────┴─────────────┴────┐                ┌────────────────────────┐
   │   EVENT SPINE         │                │     ISSUE SPINE         │
   │  Event[]              │                │  Issue[]  (34 fields)   │
   │  Relationship[]       │                │   party_a_* / party_b_* │
   │  Dispute[]            │                │   court_* / amount_*    │
   │  Lane[]  (view hint)  │                │   show_in_views (hint)  │
   └──────────┬───────────┘                └───────────┬─────────────┘
              │                                         │
              └──────────────┐         ┌────────────────┘
                             ▼         ▼
                    ┌─────────────────────────────┐
                    │   BRIDGE  (the new part)    │
                    │  issue_event_links[]        │
                    │  { issue_id, event_id,      │
                    │    role: trigger | evidence | ruling } │
                    └─────────────────────────────┘
```

### What's already there (no change needed)

- **Case** — root metadata, date range, status. Shared.
- **Party** — every actor, with `role[]` and `type`. Shared by both spines. The issue schema's `party_a_reference` / `party_b_reference` are *prose* identities; link them to `party.id` for true integration (see §3).
- **Source** — verbatim citations. Event spine uses `source_ids[]`; issue spine uses `source_references[]`. Same pool.
- **Event / Relationship / Dispute / Lane** — the timeline + ER substrate.
- **Issue (34 fields)** — the mind-map + comparison substrate.

### What you add — three small things

1. **`issue_event_links[]`** — the bridge. The only genuinely new table.
   ```json
   { "issue_id": "ISSUE-002",
     "event_id": "e_license_suspended",
     "role": "trigger" }       // trigger | evidence | ruling
   ```
   - `trigger` — the event that raised this issue (e.g., the license suspension that powers AVB's SoL theory).
   - `evidence` — an event offered to prove a position (a subcontract, a deposition).
   - `ruling` — the event where the issue was decided (trial judgment, appellate opinion).

2. **`party_a_id` / `party_b_id`** on each Issue — resolve the prose `party_*_reference` to a `party.id`. Turns "Defendant/Appellant AVB" into `"avb"` so a click on AVB lights up every panel.

3. **`dispute_id`** on an Issue (optional) — link an Issue to the `Dispute` record that encodes its contested fact (e.g., ISSUE-002 ↔ `d_sol_anchor`). Lets the timeline's dispute arc and the issue's reasoning chain reference each other.

That's the whole model. Everything below is derived from it.

---

## 3. How each view reads the model

| View | Reads | Key fields |
|---|---|---|
| **Entity-Relation** | `Party[]` as nodes; structural edges derived from `Relationship[]` + `role[]` | `party.role`, `party.type`, creditor/debtor/third-party chain |
| **Timeline** | `Event[]` positioned by `date`, grouped by `Lane[]`; `Relationship[]` as connectors; `Dispute[]` as arcs | `event.date`, `lane_id`, `kind`, `party_ids` |
| **Mind map** | `Issue[]` as branches; `party_a_*` / `party_b_*` / `court_holding` as leaves | `issue_title`, positions, holding |
| **Comparison chart** | `Issue[]` as rows; positions/amounts as columns | `party_a_position`, `party_b_position`, `court_holding`, `amount_*` |

The **bridge + shared keys** (`party.id`, `event.id`, `issue_id`, `source.id`) are what let the four views light each other up.

---

## 4. The integration method: timeline as the spine, satellites connected to it

The four views are fused into **one canvas with the timeline as the base/spine**, and the other three connected to it both *positionally* and *interactively* (the "anchored satellites" pattern):

- **Entity-Relation** is the **left rail**, welded to the spine by **row alignment** — each party node sits at the vertical center of the lane it owns, with a connector stub running into that lane. (Lanes *are* the entities; the rail draws the creditor/debtor/third-party edges.)
- **Mind map** issue cards sit in a **top band**; each card drops a **bold line to the exact event where that issue was decided** (`issue.ruling`), and fans lines to its other bridge events on hover. The drop-lines are the literal, at-rest connection from issues to the spine.
- **Comparison chart** is the HTML **table below**, tied to the spine by shared issue color and a **▲ marker strip on the same time-axis** (a ▲ under each issue's decision event, vertically aligned with the timeline above).

On top of the positional wiring, a **shared selection state** brushes-and-links all four:

```
state = { hoverIssue, hoverParty, selectedEvent, selectedParty }   // focus() ranks them
```

Every element carries `data-issue` / `data-event` / `data-party`; one `applyHighlight()` toggles dim/highlight + draws on-hover beams across all regions:

- **Hover an Issue** (card or comparison row) → fan-beams to its `issue_event_links` events, bold its drop-line, light its parties on the rail.
- **Hover/click a Party** (rail node or chip) → beams from the rail node to that party's events; dim non-touching events/issues/edges.
- **Click an Event** (timeline dot) → reverse-traverse the bridge to light the issue card(s) it feeds and beam up to them.

Guard rails learned from review: empty key-sets must **not** dim everything (gate on set size); every connector endpoint reads one live `ePos` table so nothing drifts; issues sharing a ruling event are fanned a few px so their markers don't overprint.

---

## 5. Pipeline

```
court opinion (PDF/text)
        │
        ├── legal-timeline-extraction ──► event-spine JSON  (Case, Party, Event, …)
        │
        └── legal-issue-extraction ─────► issue-spine JSON   (Issue × 34 fields)
                                                │
        ┌───────────────────────────────────────┘
        ▼
   link step:  emit issue_event_links[] + resolve party_*_id  (one small pass)
        ▼
   unified.json   ──►   integrated-diagram.html   (4 linked panels)
```

The link step is the one new piece of skill logic: given both JSONs, for each Issue, match its `key_supporting_facts` / `legal_basis` / `court_reasoning_chain` to Event labels and emit the bridge rows. This is a natural extension to the `legal-case-timeline` master skill.

See [`wanke-integrated.html`](wanke-integrated.html) for the working artifact built from the real *Wanke v. AV Builder* data.
