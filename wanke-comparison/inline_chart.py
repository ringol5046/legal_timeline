#!/usr/bin/env python3
"""
Convert a standalone chart HTML (produced by legal-timeline-chart) into an
embeddable snippet that can be pasted inside another HTML document.

- Namespaces all CSS selectors under #nc-root so they don't conflict.
- Renames element IDs (chart-wrap, controls, tooltip, show-*) with an nc- prefix.
- Strips <html>/<head>/<body> tags so the result is a fragment.

Usage:
    python3 inline_chart.py <chart.html> <output.snippet.html>
"""

import re
import sys
from pathlib import Path


def transform(chart_html: str) -> str:
    # ---- Extract <style> and <body> contents ----
    style_match = re.search(r"<style>(.*?)</style>", chart_html, re.DOTALL)
    body_match = re.search(r"<body>(.*?)</body>", chart_html, re.DOTALL)
    if not style_match or not body_match:
        raise ValueError("Couldn't find <style> or <body> blocks")

    css = style_match.group(1)
    body = body_match.group(1)

    # ---- Rename element IDs ----
    id_renames = {
        "controls": "nc-controls",
        "chart-wrap": "nc-chart-wrap",
        "tooltip": "nc-tooltip",
        "show-disputed": "nc-show-disputed",
        "show-response": "nc-show-response",
        "show-causal": "nc-show-causal",
        "show-tolls": "nc-show-tolls",
    }
    for old, new in id_renames.items():
        # In HTML attribute: id="old"
        body = body.replace(f'id="{old}"', f'id="{new}"')
        # In JS: getElementById("old") and "#old" (CSS selector in JS)
        body = body.replace(f'getElementById("{old}")', f'getElementById("{new}")')
        body = body.replace(f'"#{old}"', f'"#{new}"')
        # Array of IDs in the bottom event binding loop
        body = body.replace(f'"{old}"', f'"{new}"') if old.startswith("show-") else body

    # ---- Namespace CSS selectors under #nc-root ----
    out_css_lines = []
    for line in css.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("/*") or stripped.startswith("*/") or stripped.startswith("@"):
            out_css_lines.append(line)
            continue
        if "{" in stripped:
            # Extract selector(s) before the {
            selector_part, brace_rest = line.split("{", 1)
            selectors = [s.strip() for s in selector_part.split(",")]
            new_selectors = []
            for sel in selectors:
                if not sel:
                    continue
                if sel == ":root" or sel == "*":
                    # Keep as-is so CSS vars and box-sizing still work
                    new_selectors.append(sel)
                elif sel == "body":
                    # Body styling should target our scoped wrapper instead
                    new_selectors.append("#nc-root")
                elif sel.startswith("#nc-"):
                    # Already namespaced from id_renames above
                    new_selectors.append(sel)
                elif sel.startswith("#chart-wrap"):
                    # Already renamed in CSS too — wait, it's not. Let me handle it.
                    new_selectors.append(sel.replace("#chart-wrap", "#nc-chart-wrap"))
                else:
                    # Prefix with #nc-root for scoping
                    new_selectors.append(f"#nc-root {sel}")
            # Indent preservation
            leading = line[: len(line) - len(line.lstrip())]
            out_css_lines.append(f"{leading}{', '.join(new_selectors)} {{{brace_rest}")
        else:
            out_css_lines.append(line)
    css = "\n".join(out_css_lines)

    # CSS may still reference #chart-wrap before the JS gets a chance to run
    css = css.replace("#chart-wrap", "#nc-chart-wrap")

    # ---- Wrap body content in #nc-root and rebuild ----
    snippet = f"<style>\n{css}\n</style>\n<div id=\"nc-root\">\n{body}\n</div>"
    return snippet


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    snippet = transform(src.read_text())
    dst.write_text(snippet)
    print(f"Wrote {dst} ({len(snippet):,} bytes)")


if __name__ == "__main__":
    main()
