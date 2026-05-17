#!/usr/bin/env python3
"""
Re-inline wanke-chart-centered.html into the "new" chart card of report.html
via the iframe's srcdoc attribute.

Why: opening report.html standalone (or via file:// with iframe sandbox) can't
reach a sibling chart via src="...". Inlining keeps the report self-contained.

Usage: python3 rebuild_report_chart.py
"""
import html as html_mod
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
REPORT = BASE / "report.html"
CHART = BASE / "wanke-chart-centered.html"


def main() -> None:
    report_html = REPORT.read_text()
    chart_html = CHART.read_text()
    escaped = html_mod.escape(chart_html, quote=True)

    pattern = re.compile(
        r'<iframe class="chart-frame" (?:src="[^"]*"|srcdoc="[\s\S]*?") '
        r'title="New chart \(centered-axis\)" sandbox="[^"]*"></iframe>'
    )
    new_iframe = (
        f'<iframe class="chart-frame" srcdoc="{escaped}" '
        'title="New chart (centered-axis)" sandbox="allow-scripts allow-same-origin"></iframe>'
    )
    new_html, n = pattern.subn(lambda _: new_iframe, report_html, count=1)
    if n != 1:
        raise SystemExit("Did not find the 'New chart (centered-axis)' iframe in report.html")
    REPORT.write_text(new_html)
    print(f"Inlined {CHART.name} -> {REPORT.name} ({len(new_html):,} bytes)")


if __name__ == "__main__":
    main()
