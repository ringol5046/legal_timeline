---
name: legal-case-timeline
description: End-to-end pipeline that turns a legal case document (court opinion, complaint, motion, brief, deposition transcript, docket) into an interactive HTML timeline diagram. Chains two skills in sequence — legal-timeline-extraction (parses the document into a structured 6-entity JSON with parties, events, relationships, disputes, and source citations) followed by legal-timeline-chart (renders the JSON as an interactive month-column timeline with hover-expandable event clusters, swimlane or dual-track layout, and curved-arc dispute markers). Use this skill whenever the user has a legal document and wants the final chart, not the intermediate JSON — phrases like "make a timeline from this opinion", "chart this case", "I have a slip opinion, generate the diagram", "PDF to timeline", "give me the visual for this case", "process this opinion into a chart", or even just sharing a case PDF with "give me a timeline" should trigger it. The skill always begins by asking the user for the case file path (PDF, .docx, .md, .txt, or pasted text) if one wasn't already provided. Saves both the extraction JSON and the rendered HTML to a new sibling output folder so the user can inspect either layer.
---

# Legal Case Timeline (master skill)

End-to-end pipeline: legal document → structured timeline JSON → interactive HTML chart.

## Why this exists

The two underlying skills (`legal-timeline-extraction` and `legal-timeline-chart`) are independently useful, but the most common request is "I have a case — give me the chart." Users don't want to think about the intermediate JSON unless something goes wrong. This skill chains the two together, asks for the input once, picks sensible output paths, and produces the final interactive chart.

This skill **does not duplicate logic** from the two sub-skills. It reads their `SKILL.md` files and follows them as instructed. If you change either sub-skill's methodology, this one picks up the change automatically.

## When to use

Trigger whenever a user:
- Shares a legal document (PDF, opinion, complaint, motion, brief, deposition) AND wants a visualization
- Asks: "make a timeline chart from this opinion", "chart this case", "process this opinion", "PDF to timeline", "give me the visual for this case"
- Provides a file path and says they want the diagram
- Mentions both extraction and rendering in one breath (e.g., "extract and chart")

Don't trigger when:
- The user only wants the extraction (structured data, no visualization) — use **legal-timeline-extraction** directly
- The user already has an extraction JSON and wants to render it — use **legal-timeline-chart** directly
- The user wants to compare multiple extractions or render variants of the same data — handle as a follow-up, not via this skill

## Workflow

### Step 0: Ensure we have a case file (always ask first)

**The first thing this skill does is ask for the case file.** Even if the user said something like "make a timeline", don't guess at what document they mean. Use `AskUserQuestion`:

```
Question: "Which case file should I process?"
Options:
  1. "Paste a file path"  — user provides absolute or relative path
  2. "Paste the document text"  — user pastes text directly
  3. "I'll attach it to the chat"  — wait for the user to drop the file
```

Or just ask conversationally if it feels less formal:

> "What's the path to the case document? PDF, .docx, .md, .txt all work — or paste the text directly."

Common file locations to suggest: `~/Downloads`, `~/Desktop`, or somewhere in the current working directory. Don't proceed without input.

### Step 1: Read the case file

Use the right tool for the file type:

- **PDF** — use the `Read` tool with the `pages` parameter (max 20 pages per request). For long opinions, read in chunks (1–7, 8–15, 16–22, etc.). Confirm with the user that you're reading the right document by mentioning the case caption from page 1.
- **.docx** — check if an extraction tool is available; otherwise ask the user to convert or paste the text.
- **.md / .txt** — read directly with `Read`.
- **Pasted text** — already in context; no read needed.

Briefly confirm: "Reading [caption] — [court], [filed date]. Continuing with extraction."

### Step 2: Run the extraction

Read `legal-timeline-extraction/SKILL.md` and follow its full 6-step methodology. **Do not skip this even if you've done similar cases before** — the schema and examples encode judgment about how to handle edge cases (disputed dates, multi-version events, citation format).

Specifically:
1. Read `legal-timeline-extraction/SKILL.md` (entry methodology)
2. Read `legal-timeline-extraction/references/schema.md` (full field-by-field schema)
3. Read `legal-timeline-extraction/assets/example-output.json` (a worked example)
4. Apply the methodology: Case + Party → Events → Disputes → Relationships → Sources
5. Build the JSON output as a single object matching the schema

**Save the JSON** to a new output folder. The folder should be a sibling of the input file (or in the current working directory if the input was inline text). Default naming:
- Folder: `<case-short-name>-timeline/` (e.g., `wanke-v-avbuilder-timeline/`)
- File: `<case-short-name>-timeline/extraction.json`

Derive the short name from `case.caption` — lowercase, hyphenate, drop "Corp.", "Inc.", "LLC", etc. If you can't infer a clean short name, ask the user or fall back to `case-timeline/`.

### Step 3: Render the chart

Read `legal-timeline-chart/SKILL.md` for context on auto style selection, then run the renderer:

```bash
python3 legal-timeline-chart/scripts/render.py \
  <output-folder>/extraction.json \
  <output-folder>/chart.html
```

Add `--style swimlane` or `--style dual-track` only if the user expressed a preference. Otherwise the auto-selector (30/30 heuristic — see `legal-timeline-chart/references/chart-patterns.md`) picks the right view.

The renderer prints which style it chose and why, plus counts of events/lanes/disputes/relationships and any validation warnings. **Surface this output to the user** so they know what got rendered.

### Step 4: Report to the user

Summarize concisely:
- The case caption (so they know you got the right document)
- Chart style chosen and why (e.g., "auto: 62% factual, 38% procedural → dual-track")
- Key counts (events, lanes, disputes, relationships)
- The two file paths (the extraction JSON and the rendered HTML)
- Any validation warnings worth surfacing inline (missing source citations, unmapped lane IDs, etc.)
- Suggest: "Open `<output-folder>/chart.html` in a browser — hover the colored cluster markers to expand months that contain multiple events."

If the user immediately wants something else (e.g., "try swimlane instead", "I want more detail on the procedural arc"), re-run **only the affected step**, not the full pipeline.

## Output structure

After a successful run, the user has:

```
<case-short-name>-timeline/
├── extraction.json     ← structured 6-entity data; can be re-rendered or analyzed
└── chart.html          ← self-contained interactive HTML; open in any browser
```

Both files are durable — the user can keep them, share them, or iterate on either layer later. Don't auto-delete intermediate state.

## Common pitfalls

- **Don't skip Step 0.** Always ask for the case file even if you suspect what the user means. Saves a lot of "wait, that wasn't the document I meant" round-trips.
- **Don't skip the extraction methodology.** The chart is only as good as the JSON. If a disputed event isn't encoded as two version events with a Dispute record, the chart can't render the dispute arc — and `legal-timeline-chart` won't infer it.
- **Don't choose an output folder buried in a temp directory.** Put it where the user can find it (next to the input file or in their working directory).
- **Don't show the user the raw JSON unless they ask.** They wanted the chart. Mention the JSON exists so they know it's there.
- **Don't auto-run the renderer if the extraction surfaced major warnings** (e.g., "13 events dropped: missing date"). Show the warnings first; let the user decide whether to fix the source data or proceed.
- **Don't render with both styles by default.** It's an extra ~30s and most users only need one. Offer the second style as a follow-up if the user wants to compare.

## See also

- `legal-timeline-extraction/SKILL.md` — extraction methodology and schema; this skill follows it verbatim
- `legal-timeline-chart/SKILL.md` — chart rendering, style selection, and the month-column / cluster-expansion interaction model
- Both sub-skills work standalone; use this master skill only for the common end-to-end case
