"""
Fetch per-contest metadata from contest.ucup.ac for the candidate list, so
the review sheet can show Likes, Tutorial availability, and problem counts.

Usage (on your local machine; sandbox can't reach contest.ucup.ac):
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 fetch_ucup_metadata.py

Inputs : ../ucup_contests_v1.json   (parsed candidate list)
Output : ../ucup_contests_v2.json   (same list, augmented with likes / tutorial / problems)

Then re-run the XLSX builder to refresh the review sheet — or I can do that for you.
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
IN_PATH     = PROJECT_DIR / "ucup_contests_v1.json"
OUT_PATH    = PROJECT_DIR / "ucup_contests_v2.json"


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


# --- Score (likes - dislikes) ---------------------------------------------
# The UOJ template emits an empty <div class="uoj-click-zan-block"> with
# data attributes; the score is JS-rendered from `data-cnt`. The raw count
# (signed int — negative means more dislikes than likes) is what we want.
SCORE_PATTERNS = [
    re.compile(r'class="uoj-click-zan-block"[^>]*\bdata-cnt="(-?\d+)"', re.IGNORECASE),
    re.compile(r'\bdata-cnt="(-?\d+)"[^>]*class="uoj-click-zan-block"', re.IGNORECASE),
    # Fallbacks just in case the template changes again
    re.compile(r'class="text-(?:success|danger|muted)"[^>]*>\s*\[?\s*([+-]?\d+)\s*\]?\s*<', re.IGNORECASE),
]

# --- Tutorial attachment ---------------------------------------------------
# href can be "&" or HTML-escaped "&amp;"; text is "Tutorials (lang)".
TUT_RE = re.compile(
    r'href="[^"]*download\.php\?[^"]*\bid=\d+[^"]*\br=1"[^>]*>\s*Tutorials\s*\(([a-zA-Z\-]+)\)',
    re.IGNORECASE,
)

# --- Problem list ----------------------------------------------------------
PROBLEM_RE = re.compile(
    r'href="(/contest/\d+/problem/(\d+))[^"]*">([^<]+)</a>',
    re.IGNORECASE,
)


def parse_contest_page(html: str) -> dict:
    """Return {likes, tutorial_lang, problems[]} parsed from a UCup contest dashboard."""
    out = {"likes": None, "tutorial_lang": None, "problems": []}

    # Score: search only the top of the page — the dashboard renders the
    # like / dislike block right under the contest title, before the nav list.
    head_chunk = html
    for marker in ('id="tab_dashboard"', 'class="nav nav-tabs', '<ul class="nav', 'Standings'):
        if marker in html:
            head_chunk = html.split(marker, 1)[0]
            break
    for pat in SCORE_PATTERNS:
        m = pat.search(head_chunk)
        if m:
            try:
                out["likes"] = int(m.group(1))
                break
            except ValueError:
                continue

    # Tutorial attachment
    m = TUT_RE.search(html)
    if m:
        out["tutorial_lang"] = m.group(1)

    # Problem list — kept de-duped in source order
    seen = set()
    for href, pid, name in PROBLEM_RE.findall(html):
        if pid in seen:
            continue
        seen.add(pid)
        out["problems"].append({
            "url":  "https://contest.ucup.ac" + href,
            "id":   int(pid),
            "name": name.strip(),
        })
    return out


def main():
    if not IN_PATH.exists():
        print(f"!! input not found: {IN_PATH}")
        sys.exit(1)
    contests = json.loads(IN_PATH.read_text())
    print(f"[in]  {len(contests)} contests from {IN_PATH.name}")

    debug = "--debug" in sys.argv
    augmented = []
    for i, c in enumerate(contests, start=1):
        url = c["ucup_url"]
        print(f"[{i:>3}/{len(contests)}] {c['primary'][:80]}  →  {url}")
        html = fetch(url)
        if debug and i == 1 and html:
            # Dump everything before the standings section to a file so we can
            # see what the score / tutorial markup actually looks like.
            dbg = PROJECT_DIR / "ucup_first_contest_debug.html"
            head = html
            for marker in ('id="tab_dashboard"', 'class="nav nav-tabs', '<ul class="nav', 'Standings'):
                if marker in html:
                    head = html.split(marker, 1)[0]
                    break
            dbg.write_text(head)
            print(f"  [debug] wrote first-contest HTML head (~{len(head)} bytes) → {dbg}")
        meta = parse_contest_page(html) if html else {"likes": None, "tutorial_lang": None, "problems": []}
        merged = dict(c)
        merged.update(meta)
        augmented.append(merged)
        # Be polite — small delay between requests
        time.sleep(0.4)

    OUT_PATH.write_text(json.dumps(augmented, indent=2, ensure_ascii=False))
    print(f"[out] wrote {OUT_PATH}")
    likes_known = sum(1 for c in augmented if c.get("likes") is not None)
    tutorial_yes = sum(1 for c in augmented if c.get("tutorial_lang"))
    avg_problems = sum(len(c.get("problems") or []) for c in augmented) / max(1, len(augmented))
    print(f"      likes captured:    {likes_known}/{len(augmented)}")
    print(f"      tutorials present: {tutorial_yes}/{len(augmented)}")
    print(f"      avg problems/contest: {avg_problems:.1f}")
    print()
    print("Tell me to rebuild the v2 review sheet now.")


if __name__ == "__main__":
    main()
