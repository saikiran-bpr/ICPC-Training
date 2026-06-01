"""
Bulk-insert the approved v6 contest set into the Contest Bank.

  1. Each row goes into `contests` (name, platform, contest_type, year, url,
     notes).  Notes embed: difficulty, likes, UCup ★ score, tutorial language,
     local PDF / English-markdown paths, problem count.
  2. Each problem of each contest goes into `problems` (with is_bank=1, deduped
     by URL — overlap with rows already in the bank is silently skipped).
  3. The (contest_id, problem_id, order_idx) link is inserted into
     `contest_problems`.

Idempotent — safe to re-run.  Existing contests are matched on (name, year);
existing problems on URL.

Usage:
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 import_contests_bank.py
"""
from __future__ import annotations
import hashlib
import json
import os
import random
import re
import sqlite3
import string
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
DB_PATH     = REPO_DIR / "problems.db"
INPUT_JSON  = PROJECT_DIR / "contests_v6.json"
CF_CACHE    = PROJECT_DIR / "cf_problemset.json"
CF_KEYFILE  = REPO_DIR / ".cf_api_key"  # key=...\nsecret=... (chmod 600)


def _load_cf_creds():
    """Read CF apiKey/apiSecret from the local keyfile.  Returns None if the
    file is missing or malformed.  CF gym contests need authenticated calls;
    main contests work without."""
    if not CF_KEYFILE.exists():
        return None
    creds = {}
    for line in CF_KEYFILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" not in line: continue
        k, v = line.split("=", 1)
        creds[k.strip().lower()] = v.strip()
    if "key" in creds and "secret" in creds and creds["key"] and creds["secret"]:
        return creds
    return None


def _cf_sign(method: str, params: dict, key: str, secret: str) -> dict:
    """Implement CF API signing: apiSig = rand + sha512(rand + '/' + method
    + '?' + sorted_query + '#' + secret).  Returns the augmented params
    (apiKey, time, apiSig added)."""
    params = dict(params)
    params["apiKey"] = key
    params["time"]   = str(int(time.time()))
    rand = "".join(random.choices(string.digits + string.ascii_lowercase, k=6))
    # CF wants params sorted by (key, value) before hashing.
    sorted_items = sorted(params.items())
    qs = "&".join(f"{k}={v}" for k, v in sorted_items)
    raw = f"{rand}/{method}?{qs}#{secret}"
    sig = hashlib.sha512(raw.encode("utf-8")).hexdigest()
    params["apiSig"] = rand + sig
    return params


def load_cf_index():
    """Build {contestId: [problems]} from the cached cf_problemset.json so we
    can backfill the per-problem list for CF main-contest rows that came in
    from the ICPC archive without a problems[] array."""
    if not CF_CACHE.exists():
        return {}
    try:
        data = json.loads(CF_CACHE.read_text())
    except Exception:
        return {}
    out = {}
    for p in (data.get("result") or {}).get("problems", []):
        cid = p.get("contestId")
        if cid is None: continue
        out.setdefault(cid, []).append(p)
    # CF API returns problems unordered for some contests; sort by index.
    for cid in out:
        out[cid].sort(key=lambda x: (x.get("index") or ""))
    return out


def cf_difficulty_signal(url: str, cf_index: dict):
    """Compute a robust difficulty signal for a CF main contest.

    We use the **median** problem rating, not the mean — ICPC-style sets
    deliberately include 2-3 easy problems (warm-ups) plus 2-3 trial-by-fire
    hard problems.  The mean is dragged down by the warm-ups; the median
    represents the rating of the *typical* problem on the set, which is what
    actually determines whether a team will solve any meaningful fraction.

    Returns None for gym URLs (gyms aren't in cf_problemset.json) or contests
    without any rated problems."""
    if not url or "/contest/" not in url:
        return None
    m = re.search(r"contest/(\d+)", url)
    if not m: return None
    cid = int(m.group(1))
    probs = cf_index.get(cid) or []
    rated = sorted(p["rating"] for p in probs if p.get("rating"))
    # Need a meaningful sample.  ICPC sets are 11–14 problems; if only 1–4 are
    # rated, the median is dominated by whichever subset CF happened to tag and
    # the result is misleading.  At ≥5 rated, the median tracks reality
    # closely enough — verified against AMPPZ 2022 / CCPC Guilin 2023.
    if len(rated) < 5:
        return None
    n = len(rated)
    if n % 2:
        return float(rated[n // 2])
    return (rated[n // 2 - 1] + rated[n // 2]) / 2.0


def rating_to_stars(rating: float):
    """Map a CF *median* problem rating onto 0–5 stars (0.5-step), tuned for
    ICPC-style sets:

      median < 1500 → 1★    (training territory; a regional B-team can solve most)
      1500–1799     → 2★    (mid regional; A-team solves comfortably)
      1800–2099     → 3★    (strong regional; A-team has to push)
      2100–2399     → 4★    (continent final / hard regional)
      2400+         → 5★    (world finals territory)

    We never return 0.0 stars for a contest that *had* rated problems — the
    minimum is 0.5★ so the badge always renders something meaningful when CF
    has data.  None remains None (signals no badge)."""
    if rating is None: return None
    if   rating < 1300: stars = 0.5
    elif rating < 1500: stars = 1.0
    elif rating < 1700: stars = 1.5
    elif rating < 1900: stars = 2.0
    elif rating < 2050: stars = 2.5
    elif rating < 2200: stars = 3.0
    elif rating < 2350: stars = 3.5
    elif rating < 2500: stars = 4.0
    elif rating < 2700: stars = 4.5
    else:               stars = 5.0
    return stars


# Backwards-compat alias: an earlier version of this module exposed
# cf_avg_rating(...) — keep the old name working but route it to the median.
cf_avg_rating = cf_difficulty_signal


def ucup_to_stars(score):
    """UCup score is already on a 0–5-ish scale (community votes); just clamp
    and snap to halves so the renderer is happy."""
    if score is None: return None
    try:
        v = float(score)
    except (TypeError, ValueError):
        return None
    v = max(0.0, min(5.0, v))
    return round(v * 2) / 2.0


def cf_main_contest_id(url: str):
    """Return the contestId iff the URL is a Codeforces main-contest URL
    (NOT a gym).  Gym contests aren't in cf_problemset.json."""
    if not url: return None
    m = re.search(r"codeforces\.com/contest/(\d+)", url)
    return int(m.group(1)) if m else None


def cf_gym_id(url: str):
    """Return the gym contestId iff the URL is a CF gym URL."""
    if not url: return None
    m = re.search(r"codeforces\.com/gym/(\d+)", url)
    return int(m.group(1)) if m else None


def fetch_cf_gym_problems(gym_id: int, creds: dict = None):
    """Fetch a gym contest's problem list via Codeforces contest.standings API.
    Gyms require authentication, so we sign the request with the locally-saved
    apiKey + apiSecret when available.  Returns a list of {index, name} dicts;
    empty list on any failure (with a printed reason)."""
    base_params = {"contestId": str(gym_id), "from": "1", "count": "1"}
    if creds:
        signed = _cf_sign("contest.standings", base_params, creds["key"], creds["secret"])
        qs = "&".join(f"{k}={v}" for k, v in sorted(signed.items()))
    else:
        qs = "&".join(f"{k}={v}" for k, v in base_params.items())
    url = f"https://codeforces.com/api/contest.standings?{qs}"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except urllib.error.HTTPError as e:
        # CF returns 400 with a JSON body explaining why; surface that.
        try:
            body = e.read().decode("utf-8", errors="ignore")
            data = json.loads(body)
            print(f"    [cf-api {gym_id}] HTTP {e.code}: {data.get('comment','')[:120]}")
        except Exception:
            print(f"    [cf-api {gym_id}] HTTP {e.code}")
        return []
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
        print(f"    [cf-api {gym_id}] {type(e).__name__}: {e}")
        return []
    if data.get("status") != "OK":
        print(f"    [cf-api {gym_id}] FAILED: {data.get('comment','')[:120]}")
        return []
    return data.get("result", {}).get("problems") or []


def yr_of(s: str):
    m = re.search(r"\b(20\d{2})\b", s or "")
    return int(m.group(1)) if m else None


def derive_platform(url: str, ucup_url: str = None):
    """Pick the platform label for a contest.  UCup wins over the practice
    mirror because that's the canonical host the contest lives on (the
    practice URL is just a redeployable replay)."""
    if ucup_url and ("ucup.ac" in (ucup_url or "").lower() or "qoj.ac" in (ucup_url or "").lower()):
        return "Universal Cup"
    if not url: return "Other"
    u = url.lower()
    if "ucup.ac" in u or "qoj.ac" in u: return "Universal Cup"
    if "codeforces.com" in u:    return "Codeforces"
    if "atcoder.jp" in u:        return "AtCoder"
    if "codechef.com" in u:      return "CodeChef"
    if "kattis.com" in u:        return "Kattis"
    if "spoj.com" in u:          return "SPOJ"
    if "cses.fi" in u:           return "CSES"
    return "Other"


def derive_contest_type(r: dict):
    name = (r.get("primary") or "").lower()
    url  = (r.get("practice_url") or r.get("ucup_url") or "").lower()
    if "world finals" in name:                 return "ICPC World Finals"
    if "/gym/" in url:                         return "Gym"
    if "championship" in name and "north america" in name: return "ICPC Regional"
    if "championship" in name and "europe"        in name: return "ICPC Regional"
    if "championship" in name and "latin america" in name: return "ICPC Regional"
    if "championship" in name and "asia pacific"  in name: return "ICPC Regional"
    if "ec-final" in name or "east continent final" in name: return "Asia West Finals"
    if "regional contest" in name or "regional programming" in name: return "ICPC Regional"
    if "ccpc" in name or "中国大学生程序设计竞赛" in name: return "ICPC Regional"
    if "amppz" in name or "polish collegiate" in name: return "ICPC Regional"
    if "cerc" in name: return "ICPC Regional"
    if "seerc" in name or "southeastern europe" in name: return "ICPC Regional"
    if "/contest/" in url: return "Codeforces Round"
    return "Practice"


def build_notes(r: dict):
    """Compose the notes column.  Includes everything that's interesting but
    that doesn't have a dedicated column on the contests table."""
    bits = []
    if r.get("difficulty"):       bits.append(f"Difficulty: {r['difficulty']}")
    if r.get("ucup_score") is not None:
        bits.append(f"UCup ★: {r['ucup_score']}")
    if r.get("likes") is not None: bits.append(f"Likes: {r['likes']:+}")
    if r.get("tutorial_lang"):     bits.append(f"Tutorial lang: {r['tutorial_lang']}")
    if r.get("tutorial_pdf_local"):
        bits.append(f"Tutorial PDF: {r['tutorial_pdf_local']}")
    if r.get("tutorial_translated_md"):
        bits.append(f"Tutorial (English): {r['tutorial_translated_md']}")
    if r.get("solution_pdf"):      bits.append(f"Solution PDF (archive): {r['solution_pdf']}")
    src = r.get("source")
    if src:                        bits.append(f"Source: {src}")
    n_probs = len(r.get("problems") or [])
    if n_probs:                    bits.append(f"{n_probs} problems")
    return " · ".join(bits)


def main():
    if not DB_PATH.exists():
        print(f"!! problems.db not found at {DB_PATH}")
        sys.exit(1)
    if not INPUT_JSON.exists():
        print(f"!! input not found: {INPUT_JSON}")
        sys.exit(1)

    rows = json.loads(INPUT_JSON.read_text())
    print(f"[in] {len(rows)} contests to import")

    cf_index = load_cf_index()
    if cf_index:
        print(f"[cf] cf_problemset.json: {sum(len(v) for v in cf_index.values())} problems "
              f"across {len(cf_index)} contests (used to backfill empty problems lists)")

    cf_creds = _load_cf_creds()
    if cf_creds:
        print(f"[cf] API credentials loaded from .cf_api_key (key {cf_creds['key'][:6]}…) — "
              f"gym backfill will use signed requests")
    else:
        print(f"[cf] no .cf_api_key found — gym backfill will be skipped (CF requires auth for gyms)")

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    contests_inserted = contests_skipped = 0
    problems_inserted = problems_skipped = 0
    cp_inserted       = cp_skipped       = 0

    for r in rows:
        name      = r.get("primary") or ""
        year      = r.get("year") or yr_of(name)
        url       = r.get("practice_url") or r.get("ucup_url")
        ucup_url  = r.get("ucup_url")
        platf     = derive_platform(url, ucup_url=ucup_url)
        ctype     = derive_contest_type(r)
        notes     = build_notes(r)

        # ---- Difficulty stars (independent: a contest can have both, one, or neither) ----
        # CF stars come from the CF problemset.json index — only main contests, not gyms.
        cf_avg     = cf_avg_rating(url, cf_index)
        cf_stars   = rating_to_stars(cf_avg)
        # UCup stars come straight from the community score scraped for this row.
        ucup_stars = ucup_to_stars(r.get("ucup_score"))

        # Backfill problems for CF rows whose v6 JSON has [] — this happens for
        # ICPC-archive-only entries where we know the practice URL but never
        # scraped per-problem links.  Two cases:
        #   • main contest  → use the cached cf_problemset.json (instant, free)
        #   • gym contest   → hit contest.standings API live (gyms aren't in
        #                     the public problemset feed)
        problems_in_row = list(r.get("problems") or [])
        if not problems_in_row:
            cid_in_url = cf_main_contest_id(url)
            if cid_in_url and cid_in_url in cf_index:
                for p in cf_index[cid_in_url]:
                    idx_letter = p.get("index") or ""
                    pname      = p.get("name") or f"Problem {idx_letter}"
                    purl       = f"https://codeforces.com/contest/{cid_in_url}/problem/{idx_letter}"
                    problems_in_row.append({"name": pname, "url": purl})
                if problems_in_row:
                    print(f"  [cf-backfill] {name[:55]} → {len(problems_in_row)} problems from cf_problemset.json")
            else:
                gym_id = cf_gym_id(url)
                if gym_id and cf_creds:
                    api_problems = fetch_cf_gym_problems(gym_id, cf_creds)
                    for p in api_problems:
                        idx_letter = p.get("index") or ""
                        pname      = p.get("name") or f"Problem {idx_letter}"
                        purl       = f"https://codeforces.com/gym/{gym_id}/problem/{idx_letter}"
                        problems_in_row.append({"name": pname, "url": purl})
                    if problems_in_row:
                        print(f"  [gym-backfill] {name[:55]} → {len(problems_in_row)} problems from contest.standings API")
                    else:
                        print(f"  [gym-backfill] {name[:55]} → API returned no problems (private/registration-only?)")
                    # be polite to the CF API
                    time.sleep(0.5)

        tutorial_pdf  = r.get("tutorial_pdf_local")
        tutorial_md   = r.get("tutorial_translated_md")
        tutorial_lang = r.get("tutorial_lang")

        # --- Contest dedupe (name + year) ---
        existing = conn.execute(
            "SELECT id FROM contests WHERE name = ? AND IFNULL(contest_year, -1) = IFNULL(?, -1)",
            (name, year),
        ).fetchone()
        if existing:
            contest_id = existing[0]
            contests_skipped += 1
            # Re-write everything that might have improved on a re-run, INCLUDING
            # platform / contest_type — those derive from updated logic and we
            # want re-runs to refresh them, not stick with whatever was there
            # the first time.
            conn.execute(
                "UPDATE contests SET notes = ?, url = COALESCE(?, url), "
                "  platform = ?, contest_type = ?, "
                "  tutorial_pdf = ?, tutorial_translated = ?, tutorial_lang = ?, "
                "  cf_stars = ?, ucup_stars = ? "
                "WHERE id = ?",
                (notes, url, platf, ctype, tutorial_pdf, tutorial_md, tutorial_lang,
                 cf_stars, ucup_stars, contest_id),
            )
        else:
            cur = conn.execute(
                "INSERT INTO contests (name, platform, contest_type, contest_year, url, notes, "
                "                       tutorial_pdf, tutorial_translated, tutorial_lang, "
                "                       cf_stars, ucup_stars) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (name, platf, ctype, year, url, notes,
                 tutorial_pdf, tutorial_md, tutorial_lang,
                 cf_stars, ucup_stars),
            )
            contest_id = cur.lastrowid
            contests_inserted += 1

        # --- Problems ---
        for idx, p in enumerate(problems_in_row):
            p_url  = p.get("url")
            p_name = p.get("name") or "(unnamed)"
            if not p_url:
                continue

            ex = conn.execute("SELECT id FROM problems WHERE url = ?", (p_url,)).fetchone()
            if ex:
                problem_id = ex[0]
                problems_skipped += 1
                # Make sure the row is flagged contest-scoped even if it
                # already existed (e.g. previously imported from another path).
                conn.execute("UPDATE problems SET from_contest = 1 WHERE id = ?",
                             (problem_id,))
            else:
                cur = conn.execute(
                    "INSERT INTO problems (name, url, platform, contest_type, importance, "
                    "                       is_bank, from_contest, status) "
                    "VALUES (?, ?, ?, ?, 'Normal', 1, 1, 'Todo')",
                    (p_name, p_url, platf, ctype),
                )
                problem_id = cur.lastrowid
                problems_inserted += 1

            # --- contest_problems link ---
            try:
                conn.execute(
                    "INSERT INTO contest_problems (contest_id, problem_id, order_idx) "
                    "VALUES (?, ?, ?)",
                    (contest_id, problem_id, idx + 1),
                )
                cp_inserted += 1
            except sqlite3.IntegrityError:
                cp_skipped += 1

    conn.commit()

    total_contests = conn.execute("SELECT COUNT(*) FROM contests").fetchone()[0]
    total_bank     = conn.execute("SELECT COUNT(*) FROM problems WHERE is_bank = 1").fetchone()[0]
    total_links    = conn.execute("SELECT COUNT(*) FROM contest_problems").fetchone()[0]
    conn.close()

    print()
    print(f"[contests]")
    print(f"  inserted: {contests_inserted}")
    print(f"  updated (already existed): {contests_skipped}")
    print(f"[problems]")
    print(f"  inserted: {problems_inserted}")
    print(f"  skipped (already in bank): {problems_skipped}")
    print(f"[contest_problems links]")
    print(f"  added:   {cp_inserted}")
    print(f"  already: {cp_skipped}")
    print()
    print(f"Bank totals → {total_contests} contests · {total_bank} bank problems · {total_links} contest-problem links")
    print()
    print("Open the app, switch to the **Contest Bank** tab, and you'll see them.")


if __name__ == "__main__":
    main()
