#!/usr/bin/env python3
"""
Render legal-timeline JSON into a self-contained interactive HTML chart.

Usage:
    python3 render.py <input.json> <output.html> [--style swimlane|dual-track|centered-axis|auto]

Styles:
    swimlane        Parties-as-lanes (default; best for "who did what when")
    dual-track      Facts (top) vs Procedure (bottom) (best for appellate/SoL framing)
    centered-axis   Thin centered date bar with zigzag events above/below (best for
                    linear, chronological narratives with ≤ ~25 events; lane colors
                    are preserved on dots so party identity is still legible)
    auto            Picks based on event composition (see chart-patterns.md)

The script validates and auto-completes the input before rendering, and prints
a report of the choices it made + any warnings to stdout.
"""

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


# ---------- Defaults ----------

VALID_DATE_CERTAINTY = {"exact", "approximate", "disputed", "unknown"}
VALID_KIND = {"fact", "filing", "ruling", "discovery", "settlement", "external"}
FACTUAL_KINDS = {"fact", "external"}
PROCEDURAL_KINDS = {"filing", "ruling", "discovery", "settlement"}

DEFAULT_PALETTE = ["#2b6cb0", "#b04a2b", "#6b46c1", "#d69e2e", "#319795", "#805ad5"]
COURT_COLOR = "#4a5568"
ROLE_PRIORITY = ["plaintiff", "counter_defendant", "defendant", "counterclaimant",
                 "cross_defendant", "intervenor", "third_party", "witness", "expert",
                 "regulator", "non_party", "court", "judge", "magistrate"]


# ---------- Validation + preparation ----------

def parse_iso(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def event_date(event):
    if event.get("date"):
        return parse_iso(event["date"])
    if event.get("date_range") and len(event["date_range"]) >= 1:
        return parse_iso(event["date_range"][0])
    return None


def validate_and_prepare(data, warnings):
    """Validate input and fill in defaults. Mutates data in place. Returns the data."""

    # Ensure top-level arrays
    for key in ["events", "parties", "lanes", "relationships", "disputes", "sources"]:
        if key not in data or not isinstance(data[key], list):
            data[key] = []
    if "case" not in data or not isinstance(data["case"], dict):
        data["case"] = {}
        warnings.append("No `case` block in input; using defaults.")

    # --- Validate events ---
    valid_events = []
    for i, ev in enumerate(data["events"]):
        eid = ev.get("id", f"event_{i}")
        d = event_date(ev)
        if d is None:
            warnings.append(f"Dropped event <strong>{eid}</strong>: no valid date.")
            continue

        if not ev.get("label"):
            ev["label"] = "(unlabeled event)"
            warnings.append(f"Event <strong>{eid}</strong>: missing label, defaulted to '(unlabeled event)'.")

        cert = ev.get("date_certainty")
        if cert not in VALID_DATE_CERTAINTY:
            if cert is not None:
                warnings.append(f"Event <strong>{eid}</strong>: invalid date_certainty '{cert}', defaulted to 'exact'.")
            ev["date_certainty"] = "exact"

        kind = ev.get("kind")
        if kind not in VALID_KIND:
            if kind is not None:
                warnings.append(f"Event <strong>{eid}</strong>: invalid kind '{kind}', defaulted to 'fact'.")
            ev["kind"] = "fact"

        if "party_ids" not in ev or not isinstance(ev["party_ids"], list):
            ev["party_ids"] = []
        if "source_ids" not in ev or not isinstance(ev["source_ids"], list):
            ev["source_ids"] = []

        valid_events.append(ev)

    data["events"] = valid_events

    if not valid_events:
        raise ValueError("No valid events to render. All events were dropped during validation.")

    # --- Infer lanes if missing ---
    if not data["lanes"]:
        data["lanes"] = infer_lanes_from_parties(data, warnings)

    # --- Assign lane_id to events without one ---
    lane_ids = {l.get("id") for l in data["lanes"]}
    for ev in data["events"]:
        if ev.get("lane_id") in lane_ids:
            continue
        original = ev.get("lane_id")
        inferred = None
        for pid in ev.get("party_ids", []):
            for lane in data["lanes"]:
                if lane.get("party_id") == pid:
                    inferred = lane.get("id")
                    break
            if inferred:
                break
        if inferred:
            ev["lane_id"] = inferred
            if original and original != inferred:
                warnings.append(f"Event <strong>{ev['id']}</strong>: lane_id '{original}' not in lanes; reassigned to '{inferred}'.")
        else:
            ev["lane_id"] = "unassigned"
            warnings.append(f"Event <strong>{ev['id']}</strong>: no lane match; placed on 'unassigned' lane.")
    # Add unassigned lane if needed
    if any(ev.get("lane_id") == "unassigned" for ev in data["events"]):
        if not any(l.get("id") == "unassigned" for l in data["lanes"]):
            data["lanes"].append({"id": "unassigned", "label": "Unassigned", "color": "#9ca3af", "order": 999})

    # --- Date range ---
    if "date_range" not in data["case"] or not isinstance(data["case"].get("date_range"), list):
        dates = [event_date(ev) for ev in data["events"]]
        dates = [d for d in dates if d]
        if dates:
            start = (min(dates) - timedelta(days=90)).strftime("%Y-%m-%d")
            end = (max(dates) + timedelta(days=90)).strftime("%Y-%m-%d")
            data["case"]["date_range"] = [start, end]
            warnings.append(f"Derived case.date_range from events: [{start}, {end}].")

    # --- Validate relationships ---
    event_ids = {ev["id"] for ev in data["events"] if "id" in ev}
    valid_rels = []
    for r in data["relationships"]:
        if r.get("from_event_id") in event_ids and r.get("to_event_id") in event_ids:
            valid_rels.append(r)
        else:
            warnings.append(f"Dropped relationship <strong>{r.get('id', '?')}</strong>: references missing event.")
    data["relationships"] = valid_rels

    # --- Source references (warn only) ---
    source_ids = {s.get("id") for s in data["sources"]}
    for ev in data["events"]:
        for sid in ev.get("source_ids", []):
            if sid not in source_ids:
                warnings.append(f"Event <strong>{ev['id']}</strong>: source_id '{sid}' not found in sources.")
                break  # one warning per event is enough

    # --- Disputes: warn if a dispute has only one version ---
    for d in data["disputes"]:
        versions = d.get("versions", [])
        if len(versions) < 2:
            warnings.append(f"Dispute <strong>{d.get('id', '?')}</strong>: only {len(versions)} version(s); bracket won't render.")

    return data


def infer_lanes_from_parties(data, warnings):
    """Build lanes from parties when no lanes were provided."""
    parties = data.get("parties", [])
    events = data.get("events", [])

    referenced = set()
    for ev in events:
        for pid in ev.get("party_ids", []):
            referenced.add(pid)

    parties = [p for p in parties if p.get("id") in referenced] or parties

    def role_rank(party):
        roles = party.get("role", [])
        if isinstance(roles, str):
            roles = [roles]
        for i, r in enumerate(ROLE_PRIORITY):
            if any(r in str(role).lower() for role in roles):
                return i
        return len(ROLE_PRIORITY)

    parties.sort(key=role_rank)

    lanes = []
    palette = iter(DEFAULT_PALETTE)
    for p in parties:
        roles = p.get("role", [])
        if isinstance(roles, str):
            roles = [roles]
        is_court = any("court" in str(r).lower() or "judge" in str(r).lower() for r in roles)
        color = COURT_COLOR if is_court else next(palette, DEFAULT_PALETTE[-1])
        lanes.append({
            "id": p["id"],
            "label": p.get("short_name") or p.get("name", p["id"]),
            "sub": ", ".join(str(r).title() for r in roles) if roles else "",
            "party_id": p["id"],
            "color": color,
            "order": len(lanes),
        })

    # Add Court lane if any procedural events but no court party
    has_procedural = any(ev.get("kind") in PROCEDURAL_KINDS for ev in events)
    has_court_lane = any("court" in str(l.get("label", "")).lower() for l in lanes)
    if has_procedural and not has_court_lane:
        lanes.append({"id": "court", "label": "Court", "sub": "", "color": COURT_COLOR, "order": len(lanes)})

    if not lanes:
        # Fallback: single timeline lane
        lanes.append({"id": "timeline", "label": "Timeline", "sub": "", "color": DEFAULT_PALETTE[0], "order": 0})

    warnings.append(f"Lanes not provided; inferred {len(lanes)} lane(s) from parties.")
    return lanes


# ---------- Style selection ----------

def pick_style(data, requested):
    if requested and requested != "auto":
        return requested, f"user-specified ({requested})"

    events = data["events"]
    total = len(events)
    if total == 0:
        return "swimlane", "no events; defaulting to swimlane"

    fact_count = sum(1 for ev in events if ev.get("kind") in FACTUAL_KINDS)
    proc_count = sum(1 for ev in events if ev.get("kind") in PROCEDURAL_KINDS)
    fact_pct = fact_count / total
    proc_pct = proc_count / total

    if fact_pct >= 0.30 and proc_pct >= 0.30:
        return "dual-track", f"auto: {fact_pct:.0%} factual, {proc_pct:.0%} procedural"
    return "swimlane", f"auto: {fact_pct:.0%} factual, {proc_pct:.0%} procedural (below 30/30 threshold)"


# ---------- Data transformation for dual-track ----------

def transform_for_dual_track(data):
    """Replace lanes with [Facts, Procedure] and reassign event lane_ids by kind."""
    data = copy.deepcopy(data)

    data["lanes"] = [
        {"id": "facts",     "label": "Facts",     "sub": "What happened",         "color": "#2b6cb0", "order": 0},
        {"id": "procedure", "label": "Procedure", "sub": "What the court did",    "color": COURT_COLOR, "order": 1},
    ]

    for ev in data["events"]:
        ev["lane_id"] = "procedure" if ev.get("kind") in PROCEDURAL_KINDS else "facts"

    return data


# ---------- Output ----------

def html_escape(s):
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def render_warnings(warnings, max_display=10):
    if not warnings:
        return ""
    items = warnings[:max_display]
    rest = len(warnings) - max_display
    items_html = "".join(f"<li>{w}</li>" for w in items)
    extra = f"<li><em>… and {rest} more</em></li>" if rest > 0 else ""
    return f'<div class="warnings"><strong>Validation notes ({len(warnings)}):</strong><ul>{items_html}{extra}</ul></div>'


def render(input_path, output_path, style_requested):
    raw = json.loads(input_path.read_text())
    warnings = []
    data = validate_and_prepare(raw, warnings)

    style, reason = pick_style(data, style_requested)
    rendered_data = transform_for_dual_track(data) if style == "dual-track" else data

    # Pick template by style: centered-axis uses a different layout
    template_name = "template-centered-axis.html" if style == "centered-axis" else "template.html"
    template_path = Path(__file__).resolve().parent.parent / "assets" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    template = template_path.read_text()

    case = data.get("case", {})
    template = (template
        .replace("__CASE_CAPTION__", html_escape(case.get("caption", "Case Timeline")))
        .replace("__CASE_COURT__",   html_escape(case.get("court", "")))
        .replace("__CASE_DOCKET__",  html_escape(case.get("docket", "")))
        .replace("__CASE_SUMMARY__", html_escape(case.get("summary", "")))
        .replace("__CHART_STYLE__",  html_escape(style.replace("-", " ").title()))
        .replace("__WARNINGS_HTML__", render_warnings(warnings)))

    template = template.replace("/* __TIMELINE_DATA__ */", json.dumps(rendered_data, indent=2))
    output_path.write_text(template)

    # ---- Report ----
    n_ev = len(data["events"])
    n_la = len(rendered_data["lanes"])
    n_dis = len(data.get("disputes", []))
    n_rel = len(data.get("relationships", []))
    print(f"Rendered: {output_path}")
    print(f"  Style: {style} ({reason})")
    print(f"  Events: {n_ev} · Lanes: {n_la} · Disputes: {n_dis} · Relationships: {n_rel}")
    if warnings:
        print(f"  Warnings: {len(warnings)} (see chart header for details)")
    print(f"  Open: file://{output_path.resolve()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input", type=Path, help="Input JSON file")
    parser.add_argument("output", type=Path, help="Output HTML file")
    parser.add_argument("--style", choices=["swimlane", "dual-track", "centered-axis", "auto"], default="auto",
                        help="Chart style (default: auto)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    render(args.input, args.output, args.style)


if __name__ == "__main__":
    main()
