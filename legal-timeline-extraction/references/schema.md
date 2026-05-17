# Schema Reference

Complete field-by-field specification for the six entity types plus the derived `lanes` view. Read this whenever you need to know what fields are required, what enum values are valid, or how to handle edge cases.

## Table of contents
1. [Case](#1-case)
2. [Party](#2-party)
3. [Lane (derived view)](#3-lane-derived-view)
4. [Event](#4-event)
5. [Relationship](#5-relationship)
6. [Dispute](#6-dispute)
7. [Source](#7-source)
8. [Top-level output shape](#top-level-output-shape)
9. [ID conventions](#id-conventions)

---

## 1. Case

Root metadata. Exactly one `Case` per output.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier, snake_case (e.g., `acme_v_beta_2023`) |
| `caption` | string | yes | Full caption: `"Acme Corp. v. Beta LLC"` |
| `court` | string | yes | Court name, e.g., `"S.D.N.Y."`, `"9th Cir."`, `"Del. Ch."` |
| `docket` | string | no | Docket number, e.g., `"1:23-cv-04567"` |
| `jurisdiction` | string | no | Free text: `"federal"`, `"New York state"`, etc. |
| `date_range` | [string, string] | yes | `[start, end]` ISO dates (YYYY-MM-DD) bounding the chart axis. Pad ~3 months on either side of the earliest/latest event |
| `cause_of_action` | string[] | no | Primary claims: `["breach of contract", "fraud"]` |
| `status` | enum | yes | One of: `pending`, `settled`, `judgment`, `appeal`, `closed` |
| `summary` | string | no | One-paragraph description of the dispute. Useful as a tooltip / header. |

---

## 2. Party

Every named actor in the case. Use one record per actor, even if they play multiple roles.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier (`acme_corp`, `judge_smith`) |
| `name` | string | yes | Full legal name |
| `short_name` | string | no | Display label for the chart (often the party's "doing-business-as" or first word) |
| `role` | enum[] | yes | Array of roles. Common values: `plaintiff`, `defendant`, `counterclaimant`, `cross_defendant`, `intervenor`, `court`, `judge`, `magistrate`, `third_party`, `witness`, `expert`, `regulator`, `non_party`. Use array because one Party often holds multiple roles. |
| `type` | enum | yes | One of: `individual`, `corporation`, `partnership`, `llc`, `government`, `court`, `agency`, `unknown` |
| `representation` | string[] | no | Counsel names if mentioned |

---

## 3. Lane (derived view)

Lanes are *visual tracks*, not data — they tell a renderer how to arrange parties on screen. Default to one lane per primary Party plus one Court lane. Use multiple lanes for the same Party only when role-separation aids clarity (e.g., a defendant's counterclaim and original-defense activity on different lanes).

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Lane identifier (`plaintiff`, `defendant`, `court`, `witness_smith`) |
| `label` | string | yes | Header label shown on the chart (e.g., `"Plaintiff"`) |
| `sub` | string | no | Subheader (e.g., `"Acme Corp."`) |
| `party_id` | string | no | The Party this lane represents (omit for procedural lanes like `court`) |
| `proceeding` | string | no | If multiple proceedings (civil/criminal/bankruptcy), which one this lane belongs to |
| `color` | string | no | CSS color token. Renderer will assign defaults if omitted |
| `order` | number | no | Vertical order on the chart (smaller = higher). Default: render in array order |

Heuristic for choosing lanes:
- Two parties + court = 3 lanes (the default).
- Multi-defendant cases: one lane per defendant if their activity diverges; one combined lane if they act in lockstep.
- Parallel proceedings: add lanes per proceeding (e.g., `bankruptcy_court`, `criminal`).
- Witness lanes only when the witness's appearances are dispositive enough to warrant the visual real estate.

---

## 4. Event

The core unit. A point in time (or duration) with metadata about what, who, when, and what evidence supports it.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier (`e_complaint_filed`, `e_notice_beta_version`) |
| `label` | string | yes | Short label for the chart (~30-60 chars). Don't bury dates here — use `date_certainty` |
| `detail` | string | yes | One-paragraph description for the tooltip. Includes parties' assertions, key quote, or context |
| `date` | string | one of date/date_range required | ISO date (YYYY-MM-DD) for point events |
| `date_range` | [string, string] | one of date/date_range required | `[start, end]` for durations (employment period, discovery window) |
| `date_certainty` | enum | yes | `exact` \| `approximate` \| `disputed` \| `unknown`. Use `disputed` only when paired with a Dispute record |
| `lane_id` | string | yes | Which lane this event renders on |
| `party_ids` | string[] | yes | Parties involved (can be empty for purely procedural events on the court lane, but prefer at least one) |
| `kind` | enum | yes | `fact` \| `filing` \| `ruling` \| `discovery` \| `settlement` \| `external`. Drives visual styling (icon, color saturation) |
| `category` | enum | yes | Legal sub-type. Common values: `contract`, `breach`, `notice`, `payment`, `meeting`, `communication`, `motion`, `pleading`, `order`, `testimony`, `deposition`, `production`, `injury`, `transaction`, `legislation`, `regulation`, `media_event`. Drives filtering |
| `jurisdictional_significance` | string | no | Why this date matters legally: `"begins 4-year contract SoL clock"`, `"triggers 30-day cure period"`, `"satisfies condition precedent under §4.1"`. Leave null when not applicable rather than padding |
| `source_ids` | string[] | yes | Source records supporting this event. Empty array is acceptable but signals the user should add citations |
| `disputed` | boolean | no | True when the event is one party's version of a contested fact. Pair with a Dispute record |
| `dispute_id` | string | no | Pointer to the Dispute record this version belongs to |
| `asserting_party_id` | string | no | For disputed events: which party asserts this version |
| `confidence` | enum | no | Extractor's confidence: `high` \| `medium` \| `low`. Default `high`. Use `low` to flag inferences for user review |

### `kind` ↔ `category` cheat sheet

| If kind is... | Typical categories |
|---|---|
| `fact` | `contract`, `breach`, `notice`, `payment`, `meeting`, `communication`, `injury`, `transaction` |
| `filing` | `pleading`, `motion`, `response`, `reply`, `notice` |
| `ruling` | `order`, `judgment`, `opinion`, `dismissal`, `summary_judgment` |
| `discovery` | `deposition`, `production`, `interrogatory`, `subpoena`, `protective_order` |
| `settlement` | `mediation`, `settlement_agreement`, `release`, `dismissal_with_prejudice` |
| `external` | `legislation`, `regulation`, `media_event`, `related_proceeding`, `bankruptcy_filing` |

---

## 5. Relationship

Typed edge between two Events.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier |
| `from_event_id` | string | yes | The earlier or causing event |
| `to_event_id` | string | yes | The later or resulting event |
| `type` | enum | yes | `response` \| `causal` \| `tolls` \| `supersedes` \| `contradicts` \| `references` |
| `strength` | enum | yes | `alleged` \| `undisputed` \| `adjudicated`. Drives line weight in the diagram |
| `detail` | string | no | One-line note: `"Beta's MTD addresses each count of the Complaint"` |
| `clock_id` | string | no | For `tolls` relationships: identifier of the clock (e.g., `sol_breach_contract`, `cure_period_§7_2`) |
| `clock_effect` | enum | no | For `tolls` only: `start` \| `pause` \| `resume` \| `extend` \| `expire` |

### Relationship type semantics

- **response** — Procedural answer (filing-to-filing). Use for Complaint→Answer, Motion→Opposition→Reply, Order→Notice of Appeal.
- **causal** — Factual causation. Use when one party's action triggered another's, in the real world (not in court). Breach → demand letter is causal; demand letter → complaint may be causal *or* response depending on framing.
- **tolls** — Touches a clock. Use for notice of breach (triggers cure period), tolling agreement (pauses SoL), bankruptcy stay (halts proceedings), accrual events (starts SoL). Set `clock_id` and `clock_effect`.
- **supersedes** — Replacement. Use for amended pleadings, restated contracts, vacated orders. The superseded event still exists in the data but downstream renderers may fade it.
- **contradicts** — Evidentiary tension. Use when one piece of evidence/event is inconsistent with another (e.g., a witness's deposition contradicting an earlier email). Distinct from a Dispute (which is about a *single* event with multiple versions); this is about *two* events that can't both be true.
- **references** — Citation chain. Use when an order cites prior testimony, a brief quotes a deposition, an opinion cites a precedent event. Helpful for tracing how the record builds up.

---

## 6. Dispute

A disagreement among parties about a single event — its date, its occurrence, its meaning, or its attribution.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier |
| `subject` | string | yes | What is disputed: `"date defect notice was given"`, `"whether the March 5 meeting took place"` |
| `type` | enum | yes | `date` \| `occurrence` \| `meaning` \| `attribution`. See below |
| `versions` | array | yes | Array of `{event_id, asserting_party_id, basis}` objects (≥2 required) |
| `resolution` | enum | yes | `unresolved` \| `stipulated` \| `adjudicated_for_<party_id>` |
| `materiality` | string | no | Why the dispute matters legally: `"determines whether cure period was triggered"` |

### `type` semantics

- **date** — Parties agree something happened, disagree on when. Most common in cure-period / SoL fights.
- **occurrence** — Parties disagree whether the event happened at all. Plaintiff says meeting occurred; defendant says it didn't.
- **meaning** — Event indisputably happened, but its legal effect is contested ("the email was a 'notice' under §7.2" vs "it was casual correspondence").
- **attribution** — Event happened, but parties disagree on who caused it or whose statement it was.

### `versions` entry shape

```json
{
  "event_id": "e_notice_beta_version",
  "asserting_party_id": "beta_llc",
  "basis": "Beta points to Jan 10, 2023 email at Ex. 8"
}
```

---

## 7. Source

Evidentiary citation. Preserve original format.

| Field | Type | Req | Description |
|---|---|---|---|
| `id` | string | yes | Stable identifier (`s_dkt42`, `s_smith_dep_88`) |
| `type` | enum | yes | `pleading` \| `motion` \| `brief` \| `order` \| `opinion` \| `exhibit` \| `deposition` \| `declaration` \| `transcript` \| `contract` \| `email` \| `other` |
| `citation` | string | yes | **Preserve verbatim**: `"Dkt. 42 at 7"`, `"Smith Dep. 88:3-12"`, `"Ex. 14"`, `"Compl. ¶ 23"` |
| `url` | string | no | Hyperlink if available |
| `page` | string | no | Page or paragraph reference if not in citation |
| `line_range` | string | no | Line range for deposition citations (e.g., `"88:3-12"`) — fine to duplicate from citation |
| `authenticity` | enum | no | `stipulated` \| `challenged` \| `not_yet_offered` \| `admitted` \| null |
| `produced_by` | string | no | Party ID of producing party (for exhibits) |

---

## Top-level output shape

```json
{
  "case": { ... },
  "parties": [ { ... }, ... ],
  "events": [ { ... }, ... ],
  "relationships": [ { ... }, ... ],
  "disputes": [ { ... }, ... ],
  "sources": [ { ... }, ... ],
  "lanes": [ { ... }, ... ]
}
```

Order within arrays:
- `events` — chronological by `date` (or `date_range[0]`)
- `relationships` — by `from_event_id` order, then `to_event_id` order
- `lanes` — by `order`, then array order
- Other entities — extraction order is fine; arrays are unordered semantically

---

## ID conventions

- snake_case throughout
- Prefix optional but helps readability:
  - `e_` for Events: `e_complaint_filed`, `e_notice_acme_version`
  - `s_` for Sources: `s_dkt42`, `s_compl_para23`
  - `d_` for Disputes: `d_defect_notice_date`
  - `r_` for Relationships: `r_complaint_to_mtd`
- Party IDs: name-based (`acme_corp`, `judge_smith`)
- Lane IDs: role-based (`plaintiff`, `defendant`, `court`, `bankruptcy_court`)
- IDs are stable references — once assigned, don't change them within an output
