"""
URL → problem metadata pipeline.  Ported from legacy/app.py:524-820.

Public entry:  `lookup(url)`  → dict matching the LookupOut schema.

Strategy (line-for-line port):
  1. Detect platform + contest_type from URL host/path (cheap, always tried).
  2. If Codeforces URL, hit the CF problemset API for name + rating + tags +
     derived difficulty + topic + sub-topic.
  3. Otherwise fall back to scraping the page <title> / class hooks.

Uses httpx.AsyncClient (FastAPI's transitive dep) so we don't block the event
loop on outbound HTTP — meaningful when uvicorn is serving other requests at
the same time.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from html import unescape
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# CF rating → our difficulty bucket
# ---------------------------------------------------------------------------

def difficulty_from_cf_rating(rating: int | None) -> str | None:
    if rating is None:
        return None
    try:
        r = int(rating)
    except (TypeError, ValueError):
        return None
    if r < 1600:
        return "Easy"
    if r <= 1900:
        return "Normal"
    if r <= 2200:
        return "Normal-Hard"
    if r <= 2500:
        return "Hard"
    return "Challenge"


# ---------------------------------------------------------------------------
# CF tag → topic + sub-topic mapping
# ---------------------------------------------------------------------------

CF_TAG_TO_TOPIC: dict[str, str] = {
    "dp": "DP",
    "graphs": "Graph",
    "shortest paths": "Graph",
    "dfs and similar": "Graph",
    "graph matchings": "Flows / Matching",
    "trees": "Tree",
    "data structures": "Data Structures",
    "dsu": "DSU",
    "trie": "Trie",
    "binary search": "Binary Search",
    "ternary search": "Binary Search",
    "two pointers": "Two Pointers",
    "sortings": "Sorting",
    "bitmasks": "Bitmask",
    "flows": "Flows / Matching",
    "matchings": "Flows / Matching",
    "fft": "FFT / NTT",
    "ntt": "FFT / NTT",
    "math": "Math",
    "matrices": "Math",
    "number theory": "Number Theory",
    "combinatorics": "Combinatorics",
    "probabilities": "Probability",
    "games": "Game Theory",
    "geometry": "Geometry",
    "strings": "Strings",
    "string suffix structures": "Strings",
    "hashing": "Strings",
    "expression parsing": "Strings",
    "greedy": "Greedy",
    "constructive algorithms": "Constructive",
    "implementation": "Implementation",
    "brute force": "Implementation",
    "divide and conquer": "Misc",
    "2-sat": "Graph",
    "interactive": "Misc",
    "schedules": "Misc",
}

SPECIFIC_TOPICS: set[str] = {
    "Segment Tree", "DSU", "Trie", "Binary Search", "Two Pointers",
    "Bitmask", "Flows / Matching", "FFT / NTT",
}


def topic_from_cf_tags(tags: list[str]) -> tuple[str | None, str | None]:
    """Return (primary_topic, sub_topic) given a list of Codeforces tags."""
    if not tags:
        return (None, None)
    mapped = [(t, CF_TAG_TO_TOPIC.get(t.lower())) for t in tags]
    primary: str | None = None
    primary_idx: int | None = None
    for i, (_, m) in enumerate(mapped):
        if m and m in SPECIFIC_TOPICS:
            primary, primary_idx = m, i
            break
    if primary is None:
        for i, (_, m) in enumerate(mapped):
            if m:
                primary, primary_idx = m, i
                break
    remaining = [t for i, (t, _) in enumerate(mapped) if i != primary_idx]
    sub = ", ".join(s.title() for s in remaining) if remaining else None
    return (primary, sub)


# ---------------------------------------------------------------------------
# URL → platform + contest_type defaults
# ---------------------------------------------------------------------------

def detect_platform_and_contest(url: str) -> tuple[str | None, str | None]:
    try:
        parts = urllib.parse.urlparse(url)
    except Exception:
        return (None, None)
    host = (parts.hostname or "").lower()
    path = parts.path or ""

    if "codeforces.com" in host:
        if "/gym/" in path:
            return ("Codeforces", "Gym")
        return ("Codeforces", "Codeforces Round")
    if "atcoder.jp" in host:
        m = re.search(r"/contests/([a-z]+)", path, re.IGNORECASE)
        if m:
            kind = m.group(1).lower()
            if kind.startswith("abc"):
                return ("AtCoder", "AtCoder ABC")
            if kind.startswith("arc"):
                return ("AtCoder", "AtCoder ARC")
            if kind.startswith("agc"):
                return ("AtCoder", "AtCoder AGC")
        return ("AtCoder", "Practice")
    if "codechef.com" in host:
        return ("CodeChef", "Practice")
    if (
        "kattis.com" in host
        or "icpcarchive.ecs.baylor.edu" in host
        or "icpc.global" in host
    ):
        return ("Kattis", "ICPC Regional")
    if "uva.onlinejudge.org" in host or "onlinejudge.org" in host:
        return ("UVa", "Practice")
    if "spoj.com" in host:
        return ("SPOJ", "Practice")
    if "codingcompetitions.withgoogle.com" in host or "codejam.withgoogle.com" in host:
        return ("Google Code Jam", "Google Code Jam")
    if "facebook.com" in host and "codingcompetitions" in path:
        return ("Meta Hacker Cup", "Meta Hacker Cup")
    if "usaco.org" in host:
        return ("USACO", "Practice")
    return (None, None)


# ---------------------------------------------------------------------------
# Codeforces API — cached problem index
# ---------------------------------------------------------------------------

_CF_API_URL = "https://codeforces.com/api/problemset.problems"
_CF_TTL_SECONDS = 24 * 60 * 60
_cf_cache: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _cf_url_to_ids(url: str) -> tuple[int, str] | None:
    """Extract (contest_id, problem_index) from a Codeforces URL."""
    m = re.search(
        r"/(?:problemset/problem|contest|gym)/(\d+)/(?:problem/)?([A-Za-z0-9]+)",
        url,
    )
    if not m:
        return None
    return int(m.group(1)), m.group(2).upper()


async def _cf_fetch_index(client: httpx.AsyncClient) -> dict[str, Any] | None:
    """Return cached CF problemset index, refreshing if stale."""
    now = time.time()
    if _cf_cache["data"] and now - _cf_cache["fetched_at"] < _CF_TTL_SECONDS:
        return _cf_cache["data"]
    try:
        resp = await client.get(_CF_API_URL, timeout=15)
        data = resp.json()
        if data.get("status") == "OK":
            _cf_cache["data"] = data["result"]
            _cf_cache["fetched_at"] = now
            return _cf_cache["data"]
    except (httpx.HTTPError, ValueError):
        return None
    return None


async def _fetch_codeforces_details(
    client: httpx.AsyncClient, url: str
) -> dict[str, Any] | None:
    parsed = _cf_url_to_ids(url)
    if not parsed:
        return None
    contest_id, index = parsed
    idx = await _cf_fetch_index(client)
    if not idx:
        return None
    for p in idx.get("problems", []):
        if p.get("contestId") == contest_id and p.get("index") == index:
            rating = p.get("rating")
            return {
                "name": p.get("name"),
                "rating": rating,
                "tags": p.get("tags") or [],
                "difficulty": difficulty_from_cf_rating(rating),
            }
    return None


# ---------------------------------------------------------------------------
# Generic title scraper (fallback when CF API doesn't apply)
# ---------------------------------------------------------------------------

def _clean_title(s: str) -> str:
    return unescape(re.sub(r"\s+", " ", s)).strip()


async def _fetch_problem_name(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=8,
            follow_redirects=True,
        )
        html = resp.text[:2_000_000]
    except httpx.HTTPError:
        return None

    host = (urllib.parse.urlparse(url).hostname or "").lower()

    if "codeforces.com" in host:
        m = re.search(r'<div\s+class="title"[^>]*>\s*([^<]+?)\s*</div>', html)
        if m:
            return _clean_title(m.group(1))

    if "atcoder.jp" in host:
        m = re.search(r'<span\s+class="h2"[^>]*>\s*([^<]+?)\s*</span>', html)
        if m:
            return _clean_title(m.group(1))

    if "codechef.com" in host:
        m = re.search(
            r'<h3[^>]*class="[^"]*problem-statement[^"]*"[^>]*>([^<]+)</h3>',
            html,
        )
        if m:
            return _clean_title(m.group(1))

    # Generic <title> fallback
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = _clean_title(m.group(1))
        for sfx in (
            r"\s*[-|]\s*Codeforces.*$",
            r"\s*[-|]\s*AtCoder.*$",
            r"\s*[-|]\s*CodeChef.*$",
            r"\s*[-|]\s*Kattis.*$",
            r"\s*[-|]\s*UVa Online Judge.*$",
        ):
            title = re.sub(sfx, "", title, flags=re.IGNORECASE)
        return title.strip() or None
    return None


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

async def lookup(url: str) -> dict[str, Any]:
    """Compose all three steps. Returns the LookupOut shape (without
    validation — the router wraps it in the Pydantic model)."""

    platform, contest_type = detect_platform_and_contest(url)
    out: dict[str, Any] = {
        "url": url,
        "name": None,
        "rating": None,
        "tags": [],
        "difficulty": None,
        "topic": None,
        "sub_topic": None,
        "platform": platform,
        "contest_type": contest_type,
    }

    async with httpx.AsyncClient() as client:
        if "codeforces.com" in url:
            cf = await _fetch_codeforces_details(client, url)
            if cf and cf.get("name"):
                out.update(cf)
                topic, sub = topic_from_cf_tags(out.get("tags") or [])
                out["topic"] = topic
                out["sub_topic"] = sub
                return out

        out["name"] = await _fetch_problem_name(client, url)

    return out


async def fetch_name_only(url: str) -> str | None:
    """Used by POST /api/problems when the caller didn't supply a name."""
    async with httpx.AsyncClient() as client:
        # Try the CF API first (returns the canonical title without scraping).
        if "codeforces.com" in url:
            cf = await _fetch_codeforces_details(client, url)
            if cf and cf.get("name"):
                return cf["name"]
        return await _fetch_problem_name(client, url)
