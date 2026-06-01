"""
One-shot importer: load the v3 extracted YouKn0wWho dataset, optionally
enrich each Codeforces problem via the official CF API (running on this
machine, where the network reaches codeforces.com), then bulk-insert into
the Problem Bank with is_bank = 1.

Usage:
    cd /Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository
    .venv/bin/python3 import_youknowwho_bank.py

Idempotent: dedupe is by URL (which is UNIQUE in `problems`).  Re-running
will skip rows that already exist.
"""
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
DB_PATH     = REPO_DIR / "problems.db"
EXTRACT_PATH = PROJECT_DIR / "youknowwho_starred_extracted_v3.json"
CF_CACHE     = PROJECT_DIR / "cf_problemset.json"
CF_API_URL   = "https://codeforces.com/api/problemset.problems"


# --- Difficulty bucket from CF rating -------------------------------------
def diff_from_rating(r):
    if r is None:
        return None
    if r < 1600:  return "Easy"
    if r <= 1900: return "Normal"
    if r <= 2200: return "Normal-Hard"
    if r <= 2500: return "Hard"
    return "Challenge"


# --- Codeforces problem index --------------------------------------------
def parse_cf_url(url):
    if not url:
        return None
    m = re.search(r"/(?:problemset/problem|contest|gym)/(\d+)/(?:problem/)?([A-Za-z0-9]+)",
                  url, re.IGNORECASE)
    if not m:
        return None
    return (int(m.group(1)), m.group(2).upper())


def load_cf_index():
    """Return a dict {(contest_id, index): problem_dict}, fetching once and
    caching to disk so repeat runs are instant.  None on failure."""
    if CF_CACHE.exists():
        try:
            data = json.loads(CF_CACHE.read_text())
            problems = (data.get("result") or {}).get("problems") or data.get("problems") or []
            if problems:
                print(f"[cf] using cached {CF_CACHE.name} ({len(problems)} problems)")
                return {(p["contestId"], p["index"]): p for p in problems if "contestId" in p and "index" in p}
        except Exception as e:
            print(f"[cf] cached file unreadable ({e}), refetching")

    print(f"[cf] fetching {CF_API_URL} …")
    try:
        req = urllib.request.Request(
            CF_API_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(blob)
        if data.get("status") != "OK":
            print(f"[cf] API returned status={data.get('status')!r}; skipping enrichment")
            return None
        CF_CACHE.write_text(blob)
        problems = data["result"]["problems"]
        print(f"[cf] cached {len(problems)} problems → {CF_CACHE}")
        return {(p["contestId"], p["index"]): p for p in problems if "contestId" in p and "index" in p}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
        print(f"[cf] fetch failed: {e}; falling back to YK difficulty/tags only")
        return None


# --- Insert one row ------------------------------------------------------
INSERT_SQL = """
INSERT OR IGNORE INTO problems
  (name, url, platform, contest_type, rating, difficulty, topic, sub_topic,
   tags, importance, is_bank, status, created_by, notes)
VALUES (?,?,?,?,?,?,?,?,?,?, 1, 'Todo', NULL, NULL)
"""


def main():
    if not DB_PATH.exists():
        print(f"!! problems.db not found at {DB_PATH}")
        print("   Make sure the Flask server has run at least once to create it.")
        sys.exit(1)
    if not EXTRACT_PATH.exists():
        print(f"!! Extracted JSON not found at {EXTRACT_PATH}")
        sys.exit(1)

    payload = json.loads(EXTRACT_PATH.read_text())
    records = payload["records"]
    print(f"[in] {len(records)} records loaded from {EXTRACT_PATH.name}")

    cf_index = load_cf_index()
    cf_hits = cf_misses = 0

    rows = []
    for r in records:
        rating       = r.get("rating")
        difficulty   = r.get("difficulty")
        tags         = list(r.get("tags") or [])
        name         = r.get("name")

        if cf_index is not None:
            ids = parse_cf_url(r.get("url"))
            if ids and ids in cf_index:
                cf_hits += 1
                cf       = cf_index[ids]
                rating   = cf.get("rating") or rating
                cf_tags  = cf.get("tags") or []
                if cf_tags:
                    tags = cf_tags
                if cf.get("name"):
                    name = cf["name"]
            else:
                cf_misses += 1

        # Re-derive difficulty from CF rating if available, else keep YK fallback
        rating_diff = diff_from_rating(rating)
        if rating_diff:
            difficulty = rating_diff

        rows.append((
            name,
            r.get("url"),
            r.get("platform") or "Codeforces",
            r.get("contest_type") or "Codeforces Round",
            rating,
            difficulty,
            r.get("topic"),
            r.get("sub_topic"),
            json.dumps(tags),
            r.get("importance") or "Critical",
        ))

    if cf_index is not None:
        print(f"[cf] hits/misses: {cf_hits}/{cf_misses}")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    inserted = 0
    skipped = 0
    for row in rows:
        cur = conn.execute(INSERT_SQL, row)
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()

    total_bank = conn.execute("SELECT COUNT(*) FROM problems WHERE is_bank = 1").fetchone()[0]
    conn.close()

    print()
    print(f"[done] inserted {inserted}, skipped (already present) {skipped}")
    print(f"[bank] total problems with is_bank=1: {total_bank}")
    print()
    print("Open the app and click the **Problem Bank** tab to see them.")


if __name__ == "__main__":
    main()
