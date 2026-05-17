#!/usr/bin/env python3
"""
Render extracted timeline JSON into a self-contained interactive HTML diagram.

Usage:
    python3 render.py <input.json> <output.html>

The input JSON must conform to the schema in references/schema.md
(produced by the legal-timeline-extraction skill).
"""

import json
import sys
from pathlib import Path


def html_escape(s):
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render(input_path: Path, output_path: Path) -> None:
    data = json.loads(input_path.read_text())

    template_path = Path(__file__).resolve().parent.parent / "assets" / "template.html"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found at {template_path}")
    template = template_path.read_text()

    case = data.get("case", {})
    substitutions = {
        "__CASE_CAPTION__": html_escape(case.get("caption", "Case Timeline")),
        "__CASE_COURT__": html_escape(case.get("court", "")),
        "__CASE_DOCKET__": html_escape(case.get("docket", "")),
        "__CASE_SUMMARY__": html_escape(case.get("summary", "")),
    }
    for token, value in substitutions.items():
        template = template.replace(token, value)

    data_json = json.dumps(data, indent=2)
    template = template.replace("/* __TIMELINE_DATA__ */", data_json)

    output_path.write_text(template)
    print(f"Wrote {output_path} ({len(template):,} bytes)")
    print(f"Open in a browser: file://{output_path.resolve()}")


def main():
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        sys.exit(1)
    render(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
