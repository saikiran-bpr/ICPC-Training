"""
Crawl https://icpcarchive.github.io/  – walks every regional / championship
category page (skipping World Finals), pulls the contest table from each,
and writes one JSON per row with {name, region, year, problem_pdf, practice,
solution_pdf}.

Usage (local; sandbox can't reach github.io):
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 fetch_icpc_archive.py

Outputs:
    ../icpc_archive_raw.json
"""
from __future__ import annotations
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, List

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
INDEX_URL   = "https://icpcarchive.github.io/"
SKIP_TITLES = {"icpc world finals"}    # case-insensitive


def fetch(url: str, retries: int = 2) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  !! fetch failed for {url}: {e}", file=sys.stderr)
            return None


# Pull every link that points at an .html page on icpcarchive.github.io.
# Accepts:
#   <a href="https://icpcarchive.github.io/Hangzhou.html">Hangzhou</a>
#   <a href="Hangzhou.html">Hangzhou</a>
#   <a href="/Hangzhou.html">Hangzhou</a>
#   <a href='Hangzhou.html'>Hangzhou</a>     (single quotes)
INDEX_LINK_RE = re.compile(
    r"""<a\s+[^>]*?href=['"]([^'"]+?\.html)['"][^>]*>\s*([^<]+?)\s*</a>""",
    re.IGNORECASE,
)

# Pages on icpcarchive.github.io render the contest table as native HTML
# (markdown → HTML via the static-site generator).  We pull each <tr> and
# then each <td>; the first cell is the contest name, cells 2/3/4 are the
# Problem-Set / Practice / Solution links.
ROW_RE   = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
CELL_RE  = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE | re.DOTALL)
HREF_RE  = re.compile(r'href=[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
TAGS_RE  = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return TAGS_RE.sub("", s or "").replace("&amp;", "&").strip()


def _first_href(s: str):
    m = HREF_RE.search(s or "")
    return m.group(1).strip() if m else None


def parse_contest_table(html: str, region: str) -> List[dict]:
    out = []
    for tr in ROW_RE.findall(html):
        cells = CELL_RE.findall(tr)
        if len(cells) < 4:
            continue
        name_cell = _strip_tags(cells[0])
        # Skip header row
        if not name_cell or name_cell.lower().startswith("contest"):
            continue
        out.append({
            "name":         name_cell,
            "region":       region,
            "year":         _extract_year(name_cell),
            "problems_pdf": _first_href(cells[1]),
            "practice":     _first_href(cells[2]),
            "solution_pdf": _first_href(cells[3]),
        })
    return out


def _extract_year(s: str) -> Optional[int]:
    m = re.search(r"\b(20\d{2})\b", s or "")
    return int(m.group(1)) if m else None


def _absolutize(href: str) -> str:
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return INDEX_URL.rstrip("/") + href
    return INDEX_URL + href.lstrip("./")


def main():
    print(f"[idx] fetching {INDEX_URL}")
    idx = fetch(INDEX_URL)
    if not idx:
        print("!! could not fetch index")
        sys.exit(1)
    # Always dump the raw index for debugging the link-extraction regex.
    dbg = PROJECT_DIR / "icpc_archive_index_debug.html"
    dbg.write_text(idx)
    print(f"[debug] saved index HTML → {dbg}")

    cats = []
    for href, title in INDEX_LINK_RE.findall(idx):
        if title.strip().lower() in SKIP_TITLES:
            continue
        # Skip non-content pages like '#' anchors
        if href.startswith("#"):
            continue
        cats.append({"url": _absolutize(href), "title": title.strip()})

    # de-dup, prefer the first occurrence
    seen, deduped = set(), []
    for c in cats:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        deduped.append(c)
    cats = deduped
    print(f"[idx] {len(cats)} category links found (excluding World Finals)")
    if not cats:
        print("    !! no links matched. First 1000 chars of the index follow:")
        print(idx[:1000])
        sys.exit(2)

    rows = []
    for i, cat in enumerate(cats, start=1):
        print(f"[{i:>2}/{len(cats)}] {cat['title']}  →  {cat['url']}")
        html = fetch(cat["url"])
        if not html:
            continue
        rows.extend(parse_contest_table(html, region=cat["title"]))
        time.sleep(0.4)

    OUT = PROJECT_DIR / "icpc_archive_raw.json"
    OUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print(f"[out] wrote {len(rows)} contest rows → {OUT}")
    have_practice = sum(1 for r in rows if r.get("practice"))
    have_solution = sum(1 for r in rows if r.get("solution_pdf"))
    print(f"      with Practice link:  {have_practice}/{len(rows)}")
    print(f"      with Solution PDF:   {have_solution}/{len(rows)}")


if __name__ == "__main__":
    main()
