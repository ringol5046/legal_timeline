#!/usr/bin/env python3
"""
Grade eval outputs against assertions.

Usage:
    python3 grade.py <iteration-dir>

For each eval, grades both the with_skill and without_skill outputs.
Writes grading.json into each output directory.
"""

import json
import re
import sys
from pathlib import Path


def load_output(output_dir: Path):
    """Find the output file. Returns (data, raw_text, file_path) or (None, None, None)."""
    if not output_dir.exists():
        return None, None, None
    candidates = sorted(output_dir.glob("timeline.*"))
    if not candidates:
        candidates = sorted(p for p in output_dir.iterdir() if p.is_file() and p.suffix != ".html")
    if not candidates:
        return None, None, None
    path = candidates[0]
    raw = path.read_text()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    return data, raw, path


def check_field_exists(data, field, container_path=()):
    obj = data
    for p in container_path:
        obj = obj.get(p, {}) if isinstance(obj, dict) else {}
    return field in obj if isinstance(obj, dict) else False


def text_contains_any(text: str, needles) -> bool:
    if text is None:
        return False
    return any(n in text for n in needles)


def text_contains_all(text: str, needles) -> bool:
    if text is None:
        return False
    return all(n in text for n in needles)


def grade_eval_1(data, raw, render_path) -> list:
    """Eval 1: Wells v. Drayton — FLSA opinion."""
    results = []

    valid_json = data is not None
    results.append({"id": "valid-json", "text": "Output is valid JSON parseable by json.loads", "passed": valid_json, "evidence": "json.loads succeeded" if valid_json else "json.loads failed"})

    if not valid_json:
        # All structural assertions fail when JSON is invalid
        for aid, txt in [
            ("has-six-arrays", "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes"),
            ("captures-disputed-date", "Captures the Sept 8 / Oct 3, 2022 disputed date as a Dispute with two version Events"),
            ("disputed-events-count", "Has at least 2 Events with date_certainty='disputed' linked by the same dispute_id"),
            ("dispute-materiality", "Dispute record's materiality field mentions temporal proximity, cure period, or causation"),
            ("events-min-count", "Has at least 10 Events total covering factual + procedural"),
            ("procedural-events", "Includes Complaint (Apr 11, 2023), Answer (May 22, 2023), MSJ (Aug 8, 2024), and oral argument (Nov 14, 2024)"),
            ("factual-events", "Includes hire date (Mar 4, 2019), Sept 8, 2022 email, Oct 14, 2022 PIP, and Dec 19, 2022 termination"),
            ("sources-verbatim", "Sources preserve citation format verbatim"),
            ("every-event-has-source", "At least 80% of Events have non-empty source_ids"),
        ]:
            # Fall back to text check for some of these
            passed = False
            evidence = "JSON not parseable; checking raw text"
            if aid == "captures-disputed-date":
                passed = text_contains_all(raw, ["2022-09-08", "2022-10-03"]) or text_contains_all(raw, ["September 8", "October 3"]) or text_contains_all(raw, ["Sept 8", "Oct 3"])
                evidence = "Found both dispute dates in raw text" if passed else "Did not find both dates"
            elif aid == "procedural-events":
                passed = text_contains_all(raw, ["2023-04-11", "2023-05-22", "2024-08-08"]) or text_contains_all(raw, ["April 11", "May 22", "August 8"])
                evidence = "Found procedural dates in raw text" if passed else "Did not find all procedural dates"
            elif aid == "factual-events":
                passed = text_contains_all(raw, ["2019-03-04", "2022-09-08", "2022-10-14", "2022-12-19"]) or text_contains_all(raw, ["March 4", "September 8", "October 14", "December 19"])
                evidence = "Found factual dates in raw text" if passed else "Did not find all factual dates"
            elif aid == "sources-verbatim":
                passed = text_contains_any(raw, ["Dkt. 1", "Wells Dep.", "Ex. P-4"])
                evidence = "Found verbatim citation format" if passed else "No verbatim citations found"
            results.append({"id": aid, "text": txt, "passed": passed, "evidence": evidence})
        results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_path is not None and render_path.exists() and render_path.stat().st_size > 0, "evidence": f"diagram.html size: {render_path.stat().st_size if render_path and render_path.exists() else 'missing'}"})
        return results

    # Six arrays
    required = ["case", "parties", "events", "relationships", "disputes", "sources", "lanes"]
    missing = [k for k in required if k not in data]
    results.append({"id": "has-six-arrays", "text": "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes", "passed": len(missing) == 0, "evidence": f"missing: {missing}" if missing else "all present"})

    events = data.get("events", [])
    disputes = data.get("disputes", [])
    sources = data.get("sources", [])

    # Disputed date capture
    disputed_evs = [e for e in events if e.get("date_certainty") == "disputed"]
    has_sept = any("2022-09-08" in str(e.get("date", "")) or "2022-09-08" in str(e.get("date_range", [])) for e in disputed_evs)
    has_oct = any("2022-10-03" in str(e.get("date", "")) or "2022-10-03" in str(e.get("date_range", [])) for e in disputed_evs)
    captures_disputed = has_sept and has_oct and len(disputes) >= 1
    results.append({"id": "captures-disputed-date", "text": "Captures the Sept 8 / Oct 3, 2022 disputed date as a Dispute with two version Events", "passed": captures_disputed, "evidence": f"disputed Events found: Sept 8={has_sept}, Oct 3={has_oct}, disputes count={len(disputes)}"})

    # Disputed events count + linked by dispute_id
    by_dispute = {}
    for e in disputed_evs:
        did = e.get("dispute_id")
        if did:
            by_dispute.setdefault(did, []).append(e)
    has_pair = any(len(v) >= 2 for v in by_dispute.values())
    results.append({"id": "disputed-events-count", "text": "Has at least 2 Events with date_certainty='disputed' linked by the same dispute_id", "passed": has_pair, "evidence": f"dispute groups: {[(k, len(v)) for k,v in by_dispute.items()]}"})

    # Dispute materiality
    materiality_words = ["temporal proximity", "cure", "causation", "causal", "proximate", "retaliat", "FLSA", "protected activity", "inference"]
    materiality_hit = any(any(w.lower() in str(d.get("materiality", "")).lower() for w in materiality_words) for d in disputes)
    results.append({"id": "dispute-materiality", "text": "Dispute record's materiality field mentions temporal proximity, cure period, or causation", "passed": materiality_hit, "evidence": f"materiality fields: {[d.get('materiality','')[:80] for d in disputes]}"})

    # Min event count
    results.append({"id": "events-min-count", "text": "Has at least 10 Events total covering factual + procedural", "passed": len(events) >= 10, "evidence": f"event count: {len(events)}"})

    # Procedural events
    proc_dates = ["2023-04-11", "2023-05-22", "2024-08-08", "2024-11-14"]
    event_dates = [str(e.get("date", "")) for e in events]
    proc_hits = sum(1 for d in proc_dates if any(d in ed for ed in event_dates))
    results.append({"id": "procedural-events", "text": "Includes Complaint (Apr 11, 2023), Answer (May 22, 2023), MSJ (Aug 8, 2024), and oral argument (Nov 14, 2024)", "passed": proc_hits >= 3, "evidence": f"procedural dates hit: {proc_hits}/4"})

    # Factual events
    fact_dates = ["2019-03-04", "2022-09-08", "2022-10-14", "2022-12-19"]
    fact_hits = sum(1 for d in fact_dates if any(d in ed for ed in event_dates))
    results.append({"id": "factual-events", "text": "Includes hire date (Mar 4, 2019), Sept 8, 2022 email, Oct 14, 2022 PIP, and Dec 19, 2022 termination", "passed": fact_hits >= 3, "evidence": f"factual dates hit: {fact_hits}/4"})

    # Sources verbatim
    citations = [s.get("citation", "") for s in sources]
    verbatim_patterns = [r"Dkt\.\s*\d", r"Dep\.\s*\d+:\d+", r"Ex\.\s*[A-Z\-]*\d", r"\bCompl\.\s*¶"]
    verbatim_hits = sum(1 for p in verbatim_patterns if any(re.search(p, c) for c in citations))
    results.append({"id": "sources-verbatim", "text": "Sources preserve citation format verbatim (e.g., 'Wells Dep. 42:18-43:7', 'Ex. P-4', 'Dkt. 1', not normalized)", "passed": verbatim_hits >= 2, "evidence": f"verbatim pattern hits: {verbatim_hits}/4"})

    # Every event has source
    with_sources = sum(1 for e in events if e.get("source_ids"))
    src_pct = with_sources / max(len(events), 1)
    results.append({"id": "every-event-has-source", "text": "At least 80% of Events have non-empty source_ids", "passed": src_pct >= 0.8, "evidence": f"{with_sources}/{len(events)} events have sources ({src_pct:.0%})"})

    # Render
    render_ok = render_path is not None and render_path.exists() and render_path.stat().st_size > 0
    results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_ok, "evidence": f"diagram.html size: {render_path.stat().st_size if render_ok else 'missing'}"})

    return results


def grade_eval_2(data, raw, render_path) -> list:
    """Eval 2: Northstar v. Pelham — complaint + counterclaim."""
    results = []

    valid_json = data is not None
    results.append({"id": "valid-json", "text": "Output is valid JSON parseable by json.loads", "passed": valid_json, "evidence": "json.loads succeeded" if valid_json else "json.loads failed"})

    if not valid_json:
        # Fall back to text checks
        results.append({"id": "has-six-arrays", "text": "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes", "passed": False, "evidence": "not JSON"})
        results.append({"id": "pelham-multi-role", "text": "Pelham appears as ONE Party with role array containing both 'defendant' and 'counterclaimant'", "passed": False, "evidence": "not JSON; cannot verify structurally"})
        results.append({"id": "three-lanes-min", "text": "Has at least 3 lanes", "passed": text_contains_all(raw or "", ["Plaintiff", "Defendant", "Court"]), "evidence": "checked raw text for lane names"})
        sub_completion = text_contains_all(raw or "", ["October 22, 2023", "January 30, 2024"]) or text_contains_all(raw or "", ["2023-10-22", "2024-01-30"]) or text_contains_all(raw or "", ["Oct. 22, 2023", "Jan. 30, 2024"])
        results.append({"id": "substantial-completion-disputed", "text": "Captures the disputed substantial-completion date", "passed": sub_completion, "evidence": "found both dates in raw text" if sub_completion else "missing one or both dates"})
        co_hits = text_contains_all(raw or "", ["November 4, 2022", "February 28, 2023"]) or text_contains_all(raw or "", ["2022-11-04", "2023-02-28"]) or text_contains_all(raw or "", ["Nov. 4", "Feb. 28"])
        results.append({"id": "change-orders-captured", "text": "Includes both Change Order No. 1 and No. 2", "passed": co_hits, "evidence": "found change order dates in raw text" if co_hits else "missing"})
        cc_events = text_contains_any(raw or "", ["Wexford", "Notice of Defective Work", "Defective Work"])
        results.append({"id": "counterclaim-events", "text": "Includes counterclaim-specific events", "passed": cc_events, "evidence": "found counterclaim-specific event refs" if cc_events else "missing"})
        results.append({"id": "filing-relationships", "text": "Has at least one 'response' Relationship", "passed": False, "evidence": "no structured relationships in non-JSON output"})
        lien = text_contains_any(raw or "", ["Mechanic's Lien", "Mechanic Lien", "December 18, 2023", "2023-12-18"])
        results.append({"id": "mechanics-lien-event", "text": "Includes the Mechanic's Lien recording", "passed": lien, "evidence": "found Mechanic's Lien reference" if lien else "missing"})
        verbatim_hits = sum(1 for p in [r"Ex\.\s*[A-Z]", r"Ex\.\s*P-CC-\d"] if re.search(p, raw or ""))
        results.append({"id": "sources-verbatim", "text": "Sources preserve citation format verbatim", "passed": verbatim_hits >= 1, "evidence": f"verbatim pattern hits: {verbatim_hits}/2"})
        results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_path is not None and render_path.exists() and render_path.stat().st_size > 0, "evidence": "diagram.html present" if (render_path and render_path.exists()) else "missing"})
        return results

    required = ["case", "parties", "events", "relationships", "disputes", "sources", "lanes"]
    missing = [k for k in required if k not in data]
    results.append({"id": "has-six-arrays", "text": "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes", "passed": len(missing) == 0, "evidence": f"missing: {missing}" if missing else "all present"})

    parties = data.get("parties", [])
    events = data.get("events", [])
    relationships = data.get("relationships", [])
    disputes = data.get("disputes", [])
    sources = data.get("sources", [])
    lanes = data.get("lanes", [])

    # Pelham multi-role
    pelham = next((p for p in parties if "pelham" in str(p.get("id", "")).lower() or "pelham" in str(p.get("name", "")).lower()), None)
    if pelham:
        roles = pelham.get("role", [])
        if isinstance(roles, str):
            roles = [roles]
        has_def = any("defendant" in r.lower() for r in roles)
        has_cc = any("counterclaim" in r.lower() for r in roles)
        passed = has_def and has_cc
        evidence = f"Pelham roles: {roles}"
    else:
        passed = False
        evidence = "No Pelham party record found"
    results.append({"id": "pelham-multi-role", "text": "Pelham appears as ONE Party with role array containing both 'defendant' and 'counterclaimant' (not two separate parties)", "passed": passed, "evidence": evidence})

    # Three lanes minimum
    results.append({"id": "three-lanes-min", "text": "Has at least 3 lanes: plaintiff/Northstar, defendant/Pelham, court (additional lanes acceptable)", "passed": len(lanes) >= 3, "evidence": f"lane count: {len(lanes)}; ids: {[l.get('id') for l in lanes]}"})

    # Substantial completion dispute
    event_dates = [str(e.get("date", "")) for e in events]
    has_oct22 = any("2023-10-22" in d for d in event_dates)
    has_jan30 = any("2024-01-30" in d for d in event_dates)
    sub_dispute = any("substantial" in str(d.get("subject", "")).lower() or "completion" in str(d.get("subject", "")).lower() for d in disputes)
    passed = has_oct22 and has_jan30 and (sub_dispute or len(disputes) >= 1)
    results.append({"id": "substantial-completion-disputed", "text": "Captures the disputed substantial-completion date (Oct 22, 2023 per Northstar vs Jan 30, 2024 per Pelham) as a Dispute with two version Events", "passed": passed, "evidence": f"Oct 22={has_oct22}, Jan 30={has_jan30}, dispute about completion={sub_dispute}, total disputes={len(disputes)}"})

    # Change orders
    has_co1 = any("2022-11-04" in d for d in event_dates)
    has_co2 = any("2023-02-28" in d for d in event_dates)
    results.append({"id": "change-orders-captured", "text": "Includes both Change Order No. 1 (Nov 4, 2022) and Change Order No. 2 (Feb 28, 2023) as Events", "passed": has_co1 and has_co2, "evidence": f"Change Order 1={has_co1}, Change Order 2={has_co2}"})

    # Counterclaim events
    event_labels = " ".join(str(e.get("label", "")) + " " + str(e.get("detail", "")) for e in events)
    has_wexford = "wexford" in event_labels.lower()
    has_notice = "notice of defective" in event_labels.lower() or "defective work" in event_labels.lower()
    results.append({"id": "counterclaim-events", "text": "Includes counterclaim-specific events: Wexford report (Aug 4, 2023), Notice of Defective Work (Dec 4, 2023)", "passed": has_wexford and has_notice, "evidence": f"Wexford={has_wexford}, Notice of Defective Work={has_notice}"})

    # Filing relationships
    response_rels = [r for r in relationships if r.get("type") == "response"]
    results.append({"id": "filing-relationships", "text": "Has at least one 'response' Relationship linking Complaint -> Answer/Counterclaim", "passed": len(response_rels) >= 1, "evidence": f"response relationship count: {len(response_rels)}"})

    # Mechanic's Lien
    has_lien = any("lien" in str(e.get("label", "")).lower() or "lien" in str(e.get("detail", "")).lower() for e in events) and any("2023-12-18" in d for d in event_dates)
    results.append({"id": "mechanics-lien-event", "text": "Includes the Mechanic's Lien recording (Dec 18, 2023) as an Event", "passed": has_lien, "evidence": "found Mechanic's Lien event on Dec 18" if has_lien else "missing or date mismatch"})

    # Verbatim citations
    citations = [s.get("citation", "") for s in sources]
    has_ex_a = any(re.search(r"Ex\.\s*A\b", c) for c in citations)
    has_ex_pcc = any(re.search(r"Ex\.\s*P-CC", c) for c in citations)
    has_any_ex_short = any(re.search(r"Ex\.\s*[A-Z]|Ex\.\s*P-?CC-?\d", c) for c in citations)
    results.append({"id": "sources-verbatim", "text": "Sources preserve citation format verbatim (e.g., 'Ex. A', 'Ex. P-CC-2', not 'Plaintiff's Counterclaim Exhibit 2')", "passed": has_any_ex_short, "evidence": f"Ex. A found={has_ex_a}, Ex. P-CC found={has_ex_pcc}"})

    render_ok = render_path is not None and render_path.exists() and render_path.stat().st_size > 0
    results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_ok, "evidence": f"diagram.html size: {render_path.stat().st_size if render_ok else 'missing'}"})

    return results


def grade_eval_3(data, raw, render_path) -> list:
    """Eval 3: Smith deposition contradictions."""
    results = []

    valid_json = data is not None
    results.append({"id": "valid-json", "text": "Output is valid JSON parseable by json.loads", "passed": valid_json, "evidence": "json.loads succeeded" if valid_json else "json.loads failed"})

    if not valid_json:
        # Fallback text checks
        results.append({"id": "has-six-arrays", "text": "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes", "passed": False, "evidence": "not JSON"})
        two_versions = (text_contains_all(raw or "", ["2024-05-03", "2024-05-10"]) or text_contains_all(raw or "", ["May 3", "May 10"]))
        results.append({"id": "two-meeting-versions", "text": "Captures BOTH meeting dates", "passed": two_versions, "evidence": "found both dates in raw text" if two_versions else "missing"})
        has_dispute_or_contradict = text_contains_any(raw or "", ["contradict", "Dispute", "dispute", "conflict"])
        results.append({"id": "dispute-or-contradicts", "text": "Encodes the conflict", "passed": has_dispute_or_contradict, "evidence": "found conflict language in raw text" if has_dispute_or_contradict else "missing"})
        smith_emails = text_contains_any(raw or "", ["no emails", "no scheduling", "scheduling email"])
        results.append({"id": "smith-no-emails-flagged", "text": "Captures Smith's 'no emails' testimony", "passed": smith_emails, "evidence": "found no-emails testimony reference" if smith_emails else "missing"})
        dep_format = bool(re.search(r"Dep\.\s*\d+:\d+", raw or "") or re.search(r"\d+:\d+-\d+", raw or ""))
        results.append({"id": "citation-format-deposition", "text": "Source citations preserve deposition line-range format", "passed": dep_format, "evidence": "found dep. line-range" if dep_format else "missing"})
        ex_format = bool(re.search(r"Ex\.\s*[47]\b", raw or ""))
        results.append({"id": "citation-format-exhibits", "text": "Source citations preserve 'Ex. 4' / 'Ex. 7' format verbatim", "passed": ex_format, "evidence": "found Ex. 4 or Ex. 7" if ex_format else "missing"})
        removal_notice = (text_contains_all(raw or "", ["May 6", "May 13"]) or text_contains_all(raw or "", ["2024-05-06", "2024-05-13"]))
        results.append({"id": "removal-notice-event", "text": "Captures the removal notice date conflict (May 6 vs May 13)", "passed": removal_notice, "evidence": "found both notice dates" if removal_notice else "missing"})
        results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_path is not None and render_path.exists() and render_path.stat().st_size > 0, "evidence": "rendered" if (render_path and render_path.exists()) else "missing"})
        return results

    required = ["case", "parties", "events", "relationships", "disputes", "sources", "lanes"]
    missing = [k for k in required if k not in data]
    results.append({"id": "has-six-arrays", "text": "Top-level JSON contains case, parties, events, relationships, disputes, sources, lanes", "passed": len(missing) == 0, "evidence": f"missing: {missing}" if missing else "all present"})

    events = data.get("events", [])
    relationships = data.get("relationships", [])
    disputes = data.get("disputes", [])
    sources = data.get("sources", [])

    event_dates = [str(e.get("date", "")) for e in events]
    has_may3 = any("2024-05-03" in d for d in event_dates)
    has_may10 = any("2024-05-10" in d for d in event_dates)
    results.append({"id": "two-meeting-versions", "text": "Captures BOTH meeting dates — Smith's May 3, 2024 version and the documentary May 10, 2024 version — as separate Events", "passed": has_may3 and has_may10, "evidence": f"May 3 event={has_may3}, May 10 event={has_may10}"})

    contradicts_rels = [r for r in relationships if r.get("type") == "contradicts"]
    has_dispute = len(disputes) >= 1
    has_contradicts = len(contradicts_rels) >= 1
    results.append({"id": "dispute-or-contradicts", "text": "Encodes the conflict either as a Dispute linking the two versions OR as a 'contradicts' Relationship between Smith's testimony and the email evidence (or both)", "passed": has_dispute or has_contradicts, "evidence": f"disputes={len(disputes)}, contradicts relationships={len(contradicts_rels)}"})

    event_text = " ".join(str(e.get("label", "")) + " " + str(e.get("detail", "")) for e in events)
    smith_no_emails = "no emails" in event_text.lower() or "scheduling" in event_text.lower()
    results.append({"id": "smith-no-emails-flagged", "text": "Captures Smith's testimony that 'no emails relating to scheduling existed' and contradicts it with Ex. 4 (which is exactly such an email)", "passed": smith_no_emails, "evidence": "found 'no emails'/scheduling testimony reference" if smith_no_emails else "missing"})

    citations = [s.get("citation", "") for s in sources]
    has_dep_lines = any(re.search(r"Dep\.\s*\d+:\d+", c) or re.search(r"\d+:\d+(?:-\d+)?", c) for c in citations)
    results.append({"id": "citation-format-deposition", "text": "Source citations preserve deposition line-range format (e.g., 'Smith Dep. 88:5-10', not 'page 88')", "passed": has_dep_lines, "evidence": f"deposition line-range citations: {sum(1 for c in citations if re.search(r'Dep\\.\\s*\\d+:\\d+|\\b\\d+:\\d+', c))}/{len(citations)}"})

    has_ex_short = any(re.search(r"\bEx\.\s*[47]\b", c) for c in citations)
    results.append({"id": "citation-format-exhibits", "text": "Source citations preserve 'Ex. 4' / 'Ex. 7' format verbatim (not 'Exhibit 4')", "passed": has_ex_short, "evidence": f"'Ex. 4' or 'Ex. 7' format found: {has_ex_short}"})

    has_may6 = any("2024-05-06" in d for d in event_dates)
    has_may13 = any("2024-05-13" in d for d in event_dates)
    removal_noted = "removal notice" in event_text.lower() or "removal" in event_text.lower()
    results.append({"id": "removal-notice-event", "text": "Captures the removal notice sent date — Smith testifies May 6 but Ex. 7 says May 13", "passed": (has_may6 and has_may13) or (removal_noted and (has_may6 or has_may13)), "evidence": f"May 6={has_may6}, May 13={has_may13}, removal-event present={removal_noted}"})

    render_ok = render_path is not None and render_path.exists() and render_path.stat().st_size > 0
    results.append({"id": "render-succeeds", "text": "diagram.html exists and is non-empty", "passed": render_ok, "evidence": f"diagram.html size: {render_path.stat().st_size if render_ok else 'missing'}"})

    return results


def main():
    iteration_dir = Path(sys.argv[1])
    graders = {1: grade_eval_1, 2: grade_eval_2, 3: grade_eval_3}

    for eval_dir in sorted(iteration_dir.iterdir()):
        if not eval_dir.is_dir() or not eval_dir.name.startswith("eval-"):
            continue
        metadata_path = eval_dir / "eval_metadata.json"
        if not metadata_path.exists():
            continue
        metadata = json.loads(metadata_path.read_text())
        eval_id = metadata["eval_id"]
        grader = graders.get(eval_id)
        if not grader:
            continue

        for cond in ["with_skill", "without_skill"]:
            output_dir = eval_dir / cond / "outputs"
            data, raw, _ = load_output(output_dir)
            render_path = output_dir / "diagram.html"
            results = grader(data, raw, render_path)
            passed_count = sum(1 for r in results if r["passed"])
            grading = {
                "eval_id": eval_id,
                "condition": cond,
                "passed": passed_count,
                "total": len(results),
                "pass_rate": passed_count / len(results) if results else 0,
                "expectations": results,
            }
            grading_path = eval_dir / cond / "grading.json"
            grading_path.write_text(json.dumps(grading, indent=2))
            print(f"  {eval_dir.name} / {cond}: {passed_count}/{len(results)} passed")


if __name__ == "__main__":
    main()
