#!/usr/bin/env python3
"""Rebuild the profile README and dossier card from resume.json.

The same gist feeds nicpjones.com and the PDF resume, so this file never
needs hand edits when something new lands. Standard library only.

Usage:
    python scripts/build_readme.py            # fetch the gist
    python scripts/build_readme.py local.json # use a local copy (testing)
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
TEMPLATE = ROOT / "assets" / "dossier.template.svg"
OUTPUT = ROOT / "assets" / "dossier.svg"

GIST_RAW = "https://gist.githubusercontent.com/NicPWNs/5489290125ff3707caf8d51cb6cdc8a0/raw/resume.json"
CREDLY = "https://www.credly.com/users/nicpjones/badges"
GITHUB_JOINED = date(2016, 10, 22)


def load_resume(arg: str | None) -> dict:
    if arg:
        return json.loads(Path(arg).read_text(encoding="utf-8"))
    with urllib.request.urlopen(GIST_RAW, timeout=30) as resp:
        return json.load(resp)


def parse(d: str | None) -> date:
    if not d:
        return date.min
    for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(d, fmt).date()
        except ValueError:
            continue
    return date.min


def month_year(d: str | None) -> str:
    p = parse(d)
    return p.strftime("%b %Y") if p != date.min else ""


def latest(items: list[dict], key: str) -> dict:
    return max(items, key=lambda x: parse(x.get(key)))


def md_escape(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").strip()


def build_latest_table(resume: dict) -> str:
    award = latest(resume.get("awards", []), "date")
    pub = latest(resume.get("publications", []), "releaseDate")
    cert = latest(resume.get("certificates", []), "date")

    def cell(title: str, url: str | None, sub: str) -> str:
        head = f"[{md_escape(title)}]({url})" if url else md_escape(title)
        return f"{head}<br><sub>{md_escape(sub)}</sub>"

    award_cell = cell(
        award["title"],
        award.get("url"),
        " · ".join(x for x in (award.get("summary"), month_year(award.get("date"))) if x),
    )
    pub_cell = cell(
        pub["name"],
        pub.get("url"),
        " · ".join(x for x in (pub.get("summary"), month_year(pub.get("releaseDate"))) if x),
    )
    cert_cell = cell(
        cert["name"],
        cert.get("url") or CREDLY,
        " · ".join(x for x in (cert.get("issuer"), month_year(cert.get("date"))) if x),
    )

    return "\n".join(
        [
            "| 🏆 Latest win | 🔓 Latest CVE | 📜 Latest cert |",
            "| :-- | :-- | :-- |",
            f"| {award_cell} | {pub_cell} | {cert_cell} |",
        ]
    )


def stats(resume: dict, today: date) -> dict[str, str]:
    wins = sum(
        1 for a in resume.get("awards", []) if str(a.get("summary", "")).lower().startswith("1st")
    )
    years = today.year - GITHUB_JOINED.year - (
        (today.month, today.day) < (GITHUB_JOINED.month, GITHUB_JOINED.day)
    )
    return {
        "STAT_WINS": str(wins),
        "STAT_CVES": str(len(resume.get("publications", []))),
        "STAT_CERTS": str(len(resume.get("certificates", []))),
        "STAT_YEARS": str(years),
        "UPDATED": today.isoformat(),
    }


def render_svg(values: dict[str, str]) -> str:
    svg = TEMPLATE.read_text(encoding="utf-8")
    for key, val in values.items():
        svg = svg.replace("{{" + key + "}}", escape(val))
    leftover = re.findall(r"{{\w+}}", svg)
    if leftover:
        raise SystemExit(f"unfilled template tokens: {leftover}")
    return svg


def replace_block(text: str, name: str, body: str) -> str:
    start, end = f"<!-- {name} starts -->", f"<!-- {name} ends -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pattern.search(text):
        raise SystemExit(f"README is missing the {name!r} markers")
    return pattern.sub(lambda _: f"{start}\n{body}\n{end}", text)


def previous_stamp_date() -> str | None:
    if not OUTPUT.exists():
        return None
    m = re.search(r'class="mono stampdate">(\d{4}-\d{2}-\d{2})<', OUTPUT.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def main() -> None:
    resume = load_resume(sys.argv[1] if len(sys.argv) > 1 else None)
    today = date.today()

    old_readme = README.read_text(encoding="utf-8")
    new_readme = replace_block(old_readme, "latest", build_latest_table(resume))

    # The stamp shows when the file's content last changed, not when the job
    # last ran. Re-render with the previous date first; if nothing else moved,
    # leave both files alone so the nightly job makes no empty commits.
    values = stats(resume, today)
    old_date = previous_stamp_date()
    if old_date:
        unchanged_svg = render_svg({**values, "UPDATED": old_date})
        if unchanged_svg == OUTPUT.read_text(encoding="utf-8") and new_readme == old_readme:
            print(f"no changes since {old_date}")
            return

    OUTPUT.write_text(render_svg({**values, "UPDATED": today.isoformat()}), encoding="utf-8")
    README.write_text(new_readme, encoding="utf-8")
    print(f"built {OUTPUT.relative_to(ROOT)} and {README.name} for {today}")


if __name__ == "__main__":
    main()
