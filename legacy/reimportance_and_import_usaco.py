"""
Two-step maintenance script.

Step 1 — Re-importance the previously-imported YouKn0wWho problems based on
percentile of solve count *within each difficulty bucket*.

   <= 15%ile  → Normal
   16-30%ile  → Important
   31-55%ile  → Very Important
   56-70%ile  → Important
   71-85%ile  → Critical
   86-100%ile → Normal

Step 2 — Bulk-insert the USACO Guide starred problems we approved.  Codeforces
rows get rating + tags + difficulty refined by the official CF API (cached).

Idempotent.  Safe to re-run.

Usage:
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 reimportance_and_import_usaco.py
"""
# XXX: NOT YET PORTED TO POSTGRES (2026-05-30)
# ------------------------------------------------------------------
# This importer talks directly to a local SQLite file via the stdlib
# `sqlite3` module.  The web app no longer ships such a file — the only
# database is Supabase Postgres reached through `db.py`.  Port the
# `sqlite3.connect(DB_PATH)` calls to `db.connect()` before re-running.
# ------------------------------------------------------------------
import json
import os
import re
import sqlite3  # legacy — see note above
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
DB_PATH     = REPO_DIR / "problems.db"

YK_EXTRACT    = PROJECT_DIR / "youknowwho_starred_extracted_v3.json"
USACO_EXTRACT = PROJECT_DIR / "usaco_starred_extracted_v1.json"
CF_CACHE      = PROJECT_DIR / "cf_problemset.json"
CF_API_URL    = "https://codeforces.com/api/problemset.problems"


# --- Difficulty bucket from CF rating -------------------------------------
def diff_from_rating(r):
    if r is None: return None
    if r < 1600:  return "Easy"
    if r <= 1900: return "Normal"
    if r <= 2200: return "Normal-Hard"
    if r <= 2500: return "Hard"
    return "Challenge"


# --- Percentile importance (per-difficulty bucket) ------------------------
def importance_from_pct(p):
    if p <= 15:  return "Normal"
    if p <= 30:  return "Important"
    if p <= 55:  return "Very Important"
    if p <= 70:  return "Important"
    if p <= 85:  return "Critical"
    return "Normal"


# --- Codeforces problem index --------------------------------------------
def parse_cf_url(url):
    if not url: return None
    m = re.search(
        r"/(?:problemset/problem|contest|gym)/(\d+)/(?:problem/)?([A-Za-z0-9]+)",
        url, re.IGNORECASE,
    )
    if not m: return None
    return (int(m.group(1)), m.group(2).upper())


def load_cf_index():
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
        req = urllib.request.Request(CF_API_URL, headers={"User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            blob = resp.read().decode("utf-8", errors="ignore")
        data = json.loads(blob)
        if data.get("status") != "OK":
            print(f"[cf] API returned status={data.get('status')!r}")
            return None
        CF_CACHE.write_text(blob)
        problems = data["result"]["problems"]
        print(f"[cf] cached {len(problems)} problems → {CF_CACHE}")
        return {(p["contestId"], p["index"]): p for p in problems if "contestId" in p and "index" in p}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as e:
        print(f"[cf] fetch failed: {e}")
        return None


# ============================================================================
# Step 1 — Re-importance YouKn0wWho rows
# ============================================================================
def reimportance_yk():
    if not YK_EXTRACT.exists():
        print(f"!! YK extract not found at {YK_EXTRACT} — skipping step 1")
        return 0

    payload = json.loads(YK_EXTRACT.read_text())
    records = payload["records"]

    # Group by *current* difficulty (which now lives in the DB after CF
    # enrichment, but the extracted JSON also has it — they should agree).
    from collections import defaultdict
    groups = defaultdict(list)
    skipped = 0
    for r in records:
        d = r.get("difficulty")
        if not d:
            skipped += 1
            continue
        groups[d].append(r)

    # Compute new importance per problem
    new_imp = {}    # url -> importance
    for d, group in groups.items():
        group.sort(key=lambda r: (r.get("_meta", {}).get("yk_solve_count") or 0))
        n = len(group)
        for i, r in enumerate(group):
            pct = (i + 1) / n * 100
            new_imp[r["url"]] = importance_from_pct(pct)

    print(f"[yk] computed new importance for {len(new_imp)} problems "
          f"({skipped} skipped — no difficulty)")

    # UPDATE the problems table
    conn = sqlite3.connect(DB_PATH)
    updated = 0
    for url, imp in new_imp.items():
        cur = conn.execute(
            "UPDATE problems SET importance = ? WHERE url = ?",
            (imp, url),
        )
        updated += cur.rowcount
    conn.commit()

    # Show the resulting distribution
    cur = conn.execute("""
        SELECT importance, COUNT(*) FROM problems
         WHERE url IN ({})
      GROUP BY importance
      ORDER BY COUNT(*) DESC
    """.format(",".join("?" * len(new_imp))), list(new_imp.keys()))
    print("[yk] importance distribution after update:")
    for imp, n in cur.fetchall():
        print(f"      {imp or '(none)':<16s} {n}")

    conn.close()
    print(f"[yk] {updated} rows updated")
    return updated


# ============================================================================
# Step 2 — Insert USACO Guide starred problems
# ============================================================================
INSERT_SQL = """
INSERT OR IGNORE INTO problems
  (name, url, platform, contest_type, rating, difficulty, topic, sub_topic,
   tags, importance, is_bank, status, created_by, notes)
VALUES (?,?,?,?,?,?,?,?,?,?, 1, 'Todo', NULL, NULL)
"""


def import_usaco():
    if not USACO_EXTRACT.exists():
        print(f"!! USACO extract not found at {USACO_EXTRACT} — skipping step 2")
        return 0

    payload = json.loads(USACO_EXTRACT.read_text())
    records = payload["records"]
    print(f"[usaco] {len(records)} records to insert")

    cf_index = load_cf_index()
    cf_hits = cf_misses = 0

    rows = []
    for r in records:
        rating       = r.get("rating")
        difficulty   = r.get("difficulty")
        tags         = list(r.get("tags") or [])
        name         = r.get("name")

        if cf_index is not None and r.get("platform") == "Codeforces":
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

        # If we got a CF rating, refine the difficulty bucket
        if r.get("platform") == "Codeforces":
            rating_diff = diff_from_rating(rating)
            if rating_diff:
                difficulty = rating_diff

        rows.append((
            name,
            r.get("url"),
            r.get("platform") or "Other",
            r.get("contest_type") or "Practice",
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
    inserted = skipped = 0
    for row in rows:
        cur = conn.execute(INSERT_SQL, row)
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1
    conn.commit()
    total_bank = conn.execute("SELECT COUNT(*) FROM problems WHERE is_bank = 1").fetchone()[0]
    conn.close()

    print(f"[usaco] inserted {inserted}, skipped (already present) {skipped}")
    print(f"[bank] total problems with is_bank=1 now: {total_bank}")
    return inserted


# ============================================================================
def main():
    if not DB_PATH.exists():
        print(f"!! problems.db not found at {DB_PATH}")
        sys.exit(1)
    print("=== Step 1 — re-importance YouKn0wWho problems ===")
    reimportance_yk()
    print()
    print("=== Step 2 — import USACO Guide problems ===")
    import_usaco()
    print()
    print("Refresh the browser and visit Problem Bank to see the changes.")


if __name__ == "__main__":
    main()
