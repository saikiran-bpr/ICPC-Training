"""
Walk any qoj.ac listing page and harvest every contest entry, then for each
fetch the contest dashboard for likes / tutorial language / problems.  Same
parser as fetch_ucup_metadata.py — qoj.ac and contest.ucup.ac share the UOJ
backend so the markup is identical.

Default target is the ICPC-rules listing on qoj.ac:
    https://qoj.ac/contests?tab=icpc

Usage (on your local machine):
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 fetch_qoj_category.py                 # default = ?tab=icpc
    .venv/bin/python3 fetch_qoj_category.py --debug         # dump first page HTML
    .venv/bin/python3 fetch_qoj_category.py 17              # fall back to /category/17
    .venv/bin/python3 fetch_qoj_category.py "/contests?tab=all"

Outputs (in the project folder):
    qoj_listing_<slug>_raw.json
    qoj_listing_<slug>_filtered.json
"""
from __future__ import annotations
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent

QOJ_BASE = "https://qoj.ac"


def fetch(url: str, retries: int = 2) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.read().decode("utf-8", errors="ignore")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"  !! fetch failed for {url}: {e}", file=sys.stderr)
            return None


# Same patterns as the UCup fetcher
SCORE_PATTERNS = [
    re.compile(r'class="uoj-click-zan-block"[^>]*\bdata-cnt="(-?\d+)"', re.IGNORECASE),
    re.compile(r'\bdata-cnt="(-?\d+)"[^>]*class="uoj-click-zan-block"', re.IGNORECASE),
]
TUT_RE = re.compile(
    r'href="[^"]*download\.php\?[^"]*\bid=\d+[^"]*\br=1"[^>]*>\s*Tutorials\s*\(([a-zA-Z\-]+)\)',
    re.IGNORECASE,
)
PROBLEM_RE = re.compile(
    r'href="(/contest/\d+/problem/(\d+))[^"]*">([^<]+)</a>',
    re.IGNORECASE,
)


def parse_contest_page(html: str) -> dict:
    out = {"likes": None, "tutorial_lang": None, "problems": []}
    for marker in ('id="tab_dashboard"', 'class="nav nav-tabs', '<ul class="nav', 'Standings'):
        if marker in html:
            head = html.split(marker, 1)[0]
            break
    else:
        head = html
    for pat in SCORE_PATTERNS:
        m = pat.search(head)
        if m:
            try:
                out["likes"] = int(m.group(1))
                break
            except ValueError:
                pass
    m = TUT_RE.search(html)
    if m:
        out["tutorial_lang"] = m.group(1)
    seen = set()
    for href, pid, name in PROBLEM_RE.findall(html):
        if pid in seen:
            continue
        seen.add(pid)
        out["problems"].append({"url": QOJ_BASE + href, "id": int(pid), "name": name.strip()})
    return out


# Listing-page parser ------------------------------------------------------
# QOJ's listing pages render contests as <a href="/contest/<id>">name</a>.
CONTEST_LINK_RE = re.compile(
    r'href="(/contest/(\d+)(?:\?[^"]*)?)"[^>]*>\s*([^<]+?)\s*</a>',
    re.IGNORECASE,
)
# Pagination — `?page=N` or `&page=N` (UOJ supports both depending on the URL).
PAGE_RE = re.compile(r'[?&]page=(\d+)', re.IGNORECASE)


def _slugify(path: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", path).strip("_") or "root"
    return s.lower()


def _resolve_target(arg: str) -> str:
    """Accept either a numeric category id, a path, or a full URL.
    Returns a path beginning with '/'."""
    if arg.startswith("http://") or arg.startswith("https://"):
        return arg.split("qoj.ac", 1)[-1] or "/"
    if arg.startswith("/"):
        return arg
    if arg.isdigit():
        return f"/category/{arg}"
    return "/" + arg


def _add_page(path: str, page: int) -> str:
    if "?" in path:
        # use & if there's already a query string
        if "page=" in path:
            return re.sub(r"page=\d+", f"page={page}", path)
        return f"{path}&page={page}"
    return f"{path}?page={page}"


def iter_listing_pages(path: str, debug: bool = False):
    """Yield each (page, html) for the listing path, walking pagination."""
    page = 1
    visited = set()
    while True:
        url = QOJ_BASE + (path if page == 1 else _add_page(path, page))
        if url in visited:
            return
        visited.add(url)
        print(f"[cat] fetching page {page}: {url}")
        html = fetch(url)
        if not html:
            return
        if debug and page == 1:
            dbg = PROJECT_DIR / f"qoj_listing_{_slugify(path)}_page1_debug.html"
            dbg.write_text(html)
            print(f"  [debug] wrote page-1 HTML → {dbg}")
        yield page, html
        pages = sorted({int(p) for p in PAGE_RE.findall(html)})
        if not pages or page >= max(pages):
            return
        page += 1
        time.sleep(0.4)


def extract_contests(path: str, debug: bool = False):
    seen = {}
    for _page, html in iter_listing_pages(path, debug):
        for href, cid, name in CONTEST_LINK_RE.findall(html):
            cid_i = int(cid)
            if cid_i in seen:
                continue
            seen[cid_i] = {
                "qoj_id":   cid_i,
                "name":     name.strip(),
                "qoj_url":  QOJ_BASE + href.split("?")[0],
            }
    return list(seen.values())


# ICPC-style filter (mirrors what we used for UCup)
ICPC_KEYS = [
    "icpc", "ccpc", "中国大学生程序设计竞赛",
    "north america championship", "europe championship",
    "latin america championship", "asia east continent final",
    "ec-final", "cerc", "amppz", "seerc",
    "regional contest", "regional programming",
    "invitational", "polish collegiate", "zhejiang province",
]


def looks_icpc(name: str) -> bool:
    n = (name or "").lower()
    return any(k in n for k in ICPC_KEYS)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    debug = "--debug" in sys.argv
    target = args[0] if args else "/contests?tab=icpc"
    path   = _resolve_target(target)
    slug   = _slugify(path)
    out_raw      = PROJECT_DIR / f"qoj_listing_{slug}_raw.json"
    out_filtered = PROJECT_DIR / f"qoj_listing_{slug}_filtered.json"

    contests = extract_contests(path, debug=debug)
    print(f"[cat] discovered {len(contests)} contests at {path}")
    out_raw.write_text(json.dumps(contests, indent=2, ensure_ascii=False))
    print(f"[out] wrote {out_raw}")

    # Pull metadata for each contest
    enriched = []
    for i, c in enumerate(contests, start=1):
        url = c["qoj_url"]
        print(f"[{i:>3}/{len(contests)}] {c['name'][:80]}  →  {url}")
        html = fetch(url)
        meta = parse_contest_page(html) if html else {"likes": None, "tutorial_lang": None, "problems": []}
        merged = dict(c, **meta)
        enriched.append(merged)
        time.sleep(0.4)

    with_tut = [c for c in enriched if c.get("tutorial_lang")]
    icpc_with_tut = [c for c in with_tut if looks_icpc(c["name"])]
    print()
    print(f"  total in category:      {len(enriched)}")
    print(f"  with tutorial:          {len(with_tut)}")
    print(f"  ICPC-style with tutorial: {len(icpc_with_tut)}")

    out_filtered.write_text(json.dumps(icpc_with_tut, indent=2, ensure_ascii=False))
    print(f"[out] wrote {out_filtered}")
    print()
    print("Once this file is in place, tell me and I'll merge it with the existing v2 set.")


if __name__ == "__main__":
    main()
