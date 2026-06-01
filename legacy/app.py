"""
ICPC Training - Problem Repository
Flask backend: SQLite + REST CRUD + Excel export + auth (Admin/Coach/Contestant)
+ team management.

Run:
    .venv/bin/python3 -m pip install -r requirements.txt

    # First time only - create the bootstrap admin:
    .venv/bin/python3 app.py create-admin admin@example.com "Admin Name"

    # Then run the server:
    .venv/bin/python3 app.py

Open http://127.0.0.1:5000/
"""

import io
import json
import os
import re
import secrets
import sys

# Project-local DB adapter for Supabase Postgres.  Re-exports IntegrityError
# (psycopg's) for `except dbmod.IntegrityError` clauses below.
import db as dbmod
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from functools import wraps
from getpass import getpass
from html import unescape
from pathlib import Path

from flask import (
    Flask, g, jsonify, request, send_file, send_from_directory, abort, session
)
from flask_cors import CORS
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from werkzeug.security import generate_password_hash as _werkzeug_hash, check_password_hash

# CommandLineTools Python on macOS ships hashlib without scrypt, which breaks
# Werkzeug's default. Pin to PBKDF2-SHA256 — works on every Python build.
def generate_password_hash(password: str) -> str:
    return _werkzeug_hash(password, method="pbkdf2:sha256", salt_length=16)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR     = Path(__file__).resolve().parent
STATIC_DIR   = BASE_DIR / "static"
SECRET_FILE  = BASE_DIR / ".flask_secret"

USER_ROLES = ["Admin", "Coach", "Contestant"]
TEAM_ROLES = ["Member", "Reserve"]
MAX_MEMBERS_PER_TEAM   = 3
MAX_RESERVES_PER_TEAM  = 1

# --- Problem enum values ---
PLATFORMS = [
    "Codeforces", "AtCoder", "CodeChef", "ICPC Archive", "Kattis", "UVa",
    "SPOJ", "CSES", "Google Code Jam", "Meta Hacker Cup", "USACO",
    "HackerEarth", "Other",
]
CONTEST_TYPES = [
    "ICPC World Finals", "Asia West Finals", "ICPC Regional",
    "Codeforces Round", "AtCoder ABC", "AtCoder ARC", "AtCoder AGC",
    "CodeChef Long", "CodeChef Cook-Off", "Google Code Jam",
    "Meta Hacker Cup", "Practice", "Gym", "Other",
]
DIFFICULTIES = [
    "Easy", "Normal", "Normal-Hard", "Hard", "Very Hard", "Challenge",
]
TOPICS = [
    "Ad-hoc", "Implementation", "Greedy", "Constructive",
    "Math", "Number Theory", "Combinatorics", "Probability", "Game Theory",
    "Graph", "Tree", "DP", "Strings", "Geometry",
    "Data Structures", "Segment Tree", "DSU", "Trie",
    "Binary Search", "Two Pointers", "Sorting",
    "Bitmask", "Flows / Matching", "FFT / NTT", "Misc",
]
IMPORTANCE_LEVELS = ["Critical", "Very Important", "Important", "Normal"]
ROLES_SUGGESTED   = ["Algo", "DS", "Math", "Geometry", "Implementation", "Any"]
STATUSES          = ["Todo", "In Progress", "Done", "Upsolve", "Skipped"]

# Per-user attempt enums (problem_attempts table)
ATTEMPT_STATUSES = ["TODO", "Accepted", "Wrong Answer", "TLE", "RE"]
# Two phases for any solved problem: solved during the simulated contest
# window, or upsolved later.  Self-reported by the contestant.
ATTEMPT_PHASES = ["During Contest", "Upsolve"]
PROBLEM_FACED = [
    "Stuck in Implementation",
    "Stuck in Logic",
    "Stuck in Both",
    "Didn't know the necessary topic",
    "Couldn't understand problem",
    "Didn't Attempt",
    "No Problem Faced",
]

# Migration maps for legacy enum values -> new ones (apply via a one-shot
# UPDATE statement if you ever import old data; no longer auto-run at boot).
DIFFICULTY_REMAP = {
    "Easy-Medium": "Normal",
    "Medium":      "Normal",
    "Medium-Hard": "Normal-Hard",
}
IMPORTANCE_REMAP = {
    "High":   "Very Important",
    "Medium": "Important",
    "Low":    "Normal",
}

EDITABLE_FIELDS = [
    "name", "url", "platform", "contest_name", "contest_type", "contest_year",
    "problem_index", "rating", "difficulty", "topic", "sub_topic", "tags",
    "importance", "suggested_role", "prerequisites", "key_idea",
    "editorial_url", "time_limit_ms", "memory_limit_mb",
    "status", "assigned_to", "notes",
]
# Legacy single-FK columns `assigned_user_id` / `assigned_team_id` are
# kept on the table for backward-compat but no longer written. Multi-user
# lives in `problem_users`; multi-team in `problem_teams`.

# ---------------------------------------------------------------------------
# Secret key (persisted across restarts so sessions survive)
# ---------------------------------------------------------------------------

def _load_secret() -> str:
    env = os.environ.get("FLASK_SECRET_KEY")
    if env:
        return env
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    s = secrets.token_hex(32)
    # On serverless platforms (Vercel, Lambda) the filesystem is read-only or
    # ephemeral, so writing the secret would either fail or be lost on the next
    # cold start (rotating sessions on every deploy). In that case we just
    # return an in-memory key and rely on FLASK_SECRET_KEY being configured.
    try:
        SECRET_FILE.write_text(s)
        try:
            os.chmod(SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        # Read-only FS — caller should set FLASK_SECRET_KEY in env.
        pass
    return s


# ---------------------------------------------------------------------------
# App + DB
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.config.update(
    SECRET_KEY                 = _load_secret(),
    SESSION_COOKIE_HTTPONLY    = True,
    SESSION_COOKIE_SAMESITE    = "Lax",
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14,   # 14 days
)
CORS(app, supports_credentials=True)


def get_db():
    """Per-request Postgres connection.  The schema is managed externally by
    `scripts/seed_postgres.py`; this function never runs DDL."""
    if "db" not in g:
        g.db = dbmod.connect()
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def current_user():
    """Return the dict of the logged-in user, or None."""
    uid = session.get("user_id")
    if not uid:
        return None
    if "user" in g and g.user and g.user["id"] == uid:
        return g.user
    row = get_db().execute(
        "SELECT id, email, name, role, handle, institution, year_of_study, "
        "is_active, date_joined, last_login FROM users WHERE id = ?",
        (uid,),
    ).fetchone()
    g.user = dict(row) if row else None
    if g.user and not g.user["is_active"]:
        g.user = None
        session.clear()
    return g.user


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        if not current_user():
            abort(401, description="Authentication required")
        return fn(*a, **kw)
    return wrapper


def role_required(*roles):
    """Allow only users whose global role is in `roles`."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                abort(401, description="Authentication required")
            if u["role"] not in roles:
                abort(403, description=f"Requires role: {', '.join(roles)}")
            return fn(*a, **kw)
        return wrapper
    return decorator


def is_admin(u=None) -> bool:
    u = u or current_user()
    return bool(u and u["role"] == "Admin")


def is_coach_of(team_id: int, user_id: int) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM team_coaches WHERE team_id = ? AND user_id = ?",
        (team_id, user_id),
    ).fetchone()
    return row is not None


def is_member_of(team_id: int, user_id: int) -> bool:
    row = get_db().execute(
        "SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?",
        (team_id, user_id),
    ).fetchone()
    return row is not None


def can_manage_team(team_id: int) -> bool:
    u = current_user()
    if not u:
        return False
    if u["role"] == "Admin":
        return True
    return is_coach_of(team_id, u["id"])


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _attempt_dict(row) -> dict:
    """Shape a problem_attempts row for API output."""
    if row is None:
        return None
    # `attempt_phase` is read defensively because old DB rows pre-date the
    # column.  Treat absence as None so callers always get a stable shape.
    try:
        phase = row["attempt_phase"]
    except (IndexError, KeyError):
        phase = None
    return {
        "attempt_status": row["attempt_status"],
        "attempt_phase":  phase,
        "problem_faced":  row["problem_faced"],
        "time_spent_min": row["time_spent_min"],
        "notes":          row["notes"],
        "updated_at":     row["updated_at"],
    }


def row_to_dict(row, db=None, viewer=None) -> dict:
    d = dict(row)
    if "tags" in d:
        if d.get("tags"):
            try:
                d["tags"] = json.loads(d["tags"])
            except json.JSONDecodeError:
                d["tags"] = [t.strip() for t in str(d["tags"]).split(",") if t.strip()]
        else:
            d["tags"] = []
    # Hydrate assignment with name for UI rendering
    d["assigned_users"] = []
    d["assigned_teams"] = []
    d["my_attempt"]     = None
    d["team_summary"]   = []   # populated only for Admin/Coach
    if db is None:
        try:
            db = get_db()
        except RuntimeError:
            db = None
    if viewer is None:
        try:
            viewer = current_user()
        except Exception:
            viewer = None

    if db is not None:
        ur = db.execute(
            "SELECT u.id, u.name, u.role FROM problem_users pu "
            "JOIN users u ON pu.user_id = u.id "
            "WHERE pu.problem_id = ? ORDER BY u.name",
            (d["id"],),
        ).fetchall()
        d["assigned_users"] = [{"id": r["id"], "name": r["name"], "role": r["role"]} for r in ur]
        tr = db.execute(
            "SELECT t.id, t.name FROM problem_teams pt "
            "JOIN teams t ON pt.team_id = t.id "
            "WHERE pt.problem_id = ? ORDER BY t.name",
            (d["id"],),
        ).fetchall()
        d["assigned_teams"] = [{"id": r["id"], "name": r["name"]} for r in tr]

        # current viewer's own attempt record (always useful)
        if viewer is not None:
            arow = db.execute(
                "SELECT attempt_status, attempt_phase, problem_faced, "
                "       time_spent_min, notes, updated_at "
                "FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
                (d["id"], viewer["id"]),
            ).fetchone()
            d["my_attempt"] = _attempt_dict(arow)

        # team-level summary for Coach / Admin lists & detail
        if viewer is not None and viewer["role"] in ("Admin", "Coach"):
            d["team_summary"] = _build_team_summary(db, d["id"], d["assigned_teams"], d["assigned_users"])
    return d


def _build_team_summary(db, problem_id, teams, direct_users):
    """For each team the problem is assigned to, return solved/total counts +
    per-member attempt rows.  Also include direct (non-team) user assignments."""
    out = []
    for t in teams:
        members = db.execute(
            "SELECT u.id, u.name, tm.role_in_team, "
            "       pa.attempt_status, pa.problem_faced, pa.time_spent_min, pa.notes, pa.updated_at "
            "FROM team_members tm "
            "JOIN users u ON u.id = tm.user_id "
            "LEFT JOIN problem_attempts pa "
            "       ON pa.user_id = u.id AND pa.problem_id = ? "
            "WHERE tm.team_id = ? "
            "ORDER BY tm.role_in_team, u.name",
            (problem_id, t["id"]),
        ).fetchall()
        members_list = []
        primary_solved = 0
        primary_total  = 0
        reserve_solved = 0
        reserve_total  = 0
        for m in members:
            entry = {
                "id":             m["id"],
                "name":           m["name"],
                "role_in_team":   m["role_in_team"],
                "attempt_status": m["attempt_status"],
                "problem_faced":  m["problem_faced"],
                "time_spent_min": m["time_spent_min"],
                "notes":          m["notes"],
                "updated_at":     m["updated_at"],
            }
            members_list.append(entry)
            if m["role_in_team"] == "Member":
                primary_total += 1
                if m["attempt_status"] == "Accepted":
                    primary_solved += 1
            else:
                reserve_total += 1
                if m["attempt_status"] == "Accepted":
                    reserve_solved += 1
        out.append({
            "team_id":         t["id"],
            "team_name":       t["name"],
            "solved":          primary_solved,
            "total":           primary_total,
            "reserve_solved":  reserve_solved,
            "reserve_total":   reserve_total,
            "members":         members_list,
        })

    # Direct user assignments not already covered by teams above
    member_ids_in_teams = {m["id"] for grp in out for m in grp["members"]}
    direct = []
    for u in direct_users:
        if u["id"] in member_ids_in_teams:
            continue
        a = db.execute(
            "SELECT attempt_status, attempt_phase, problem_faced, "
            "       time_spent_min, notes, updated_at "
            "FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
            (problem_id, u["id"]),
        ).fetchone()
        direct.append({
            "id":             u["id"],
            "name":           u["name"],
            "role":           u.get("role"),
            "attempt_status": a["attempt_status"]      if a else None,
            "problem_faced":  a["problem_faced"]       if a else None,
            "time_spent_min": a["time_spent_min"]      if a else None,
            "notes":          a["notes"]               if a else None,
            "updated_at":     a["updated_at"]          if a else None,
        })
    if direct:
        out.append({
            "team_id":   None,
            "team_name": "Direct user assignments",
            "solved":    sum(1 for u in direct if u["attempt_status"] == "Accepted"),
            "total":     len(direct),
            "reserve_solved": 0,
            "reserve_total":  0,
            "members":   direct,
        })
    return out


def normalize_problem_payload(payload: dict) -> dict:
    clean = {k: payload.get(k) for k in EDITABLE_FIELDS if k in payload}
    if "tags" in clean:
        v = clean["tags"]
        if isinstance(v, list):
            clean["tags"] = json.dumps([str(x).strip() for x in v if str(x).strip()])
        elif isinstance(v, str):
            parts = [p.strip() for p in v.split(",") if p.strip()]
            clean["tags"] = json.dumps(parts)
        elif v is None:
            clean["tags"] = json.dumps([])
    for k in ("rating", "contest_year", "time_limit_ms", "memory_limit_mb"):
        if k in clean:
            if clean[k] in (None, ""):
                clean[k] = None
            else:
                try:
                    clean[k] = int(clean[k])
                except (ValueError, TypeError):
                    clean[k] = None
    return clean


def validate_required(payload: dict, fields):
    missing = [k for k in fields if not payload.get(k)]
    if missing:
        abort(400, description=f"Missing required fields: {', '.join(missing)}")


def public_user(row) -> dict:
    """Strip password_hash and shape user row for API response."""
    if not row:
        return None
    d = dict(row)
    d.pop("password_hash", None)
    d["is_active"] = bool(d.get("is_active", 1))
    return d


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# Serve project-relative resources (tutorial PDFs, English-translated MDs)
# referenced by contests.tutorial_pdf / contests.tutorial_translated.  These
# paths are stored relative to the project root (one level above this file).
# A plain `file:///Users/...` link is blocked by every modern browser when the
# page itself loads over http://, so we expose them through the same origin.
PROJECT_ROOT = BASE_DIR.parent

@app.route("/files/<path:relpath>")
def serve_project_file(relpath):
    # Resolve and confine to PROJECT_ROOT — block .. traversal.
    target = (PROJECT_ROOT / relpath).resolve()
    try:
        target.relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        abort(404)
    if not target.is_file():
        abort(404)
    # send_from_directory wants (directory, filename); split is fine because
    # we've already validated containment.
    return send_from_directory(target.parent, target.name, conditional=True)


@app.route("/api/meta")
def meta():
    return jsonify({
        "platforms":         PLATFORMS,
        "contest_types":     CONTEST_TYPES,
        "difficulties":      DIFFICULTIES,
        "topics":            TOPICS,
        "importance":        IMPORTANCE_LEVELS,
        "roles":             ROLES_SUGGESTED,
        "statuses":          STATUSES,
        "user_roles":        USER_ROLES,
        "team_roles":        TEAM_ROLES,
        "team_caps":         {"member": MAX_MEMBERS_PER_TEAM, "reserve": MAX_RESERVES_PER_TEAM},
        "attempt_statuses":  ATTEMPT_STATUSES,
        "attempt_phases":    ATTEMPT_PHASES,
        "problem_faced":     PROBLEM_FACED,
    })


# ---------------------------------------------------------------------------
# URL -> problem name lookup
# ---------------------------------------------------------------------------

def fetch_problem_name(url: str):
    """Best-effort: GET the URL and pull a sensible problem name from the page.
    Returns the name string or None.  No external libraries.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            html = resp.read(2_000_000).decode(charset, errors="ignore")
    except (urllib.error.URLError, ValueError, TimeoutError, OSError):
        return None

    host = urllib.parse.urlparse(url).hostname or ""

    # --- Codeforces ---  problem statement page has <div class="title">A. Name</div>
    if "codeforces.com" in host:
        m = re.search(r'<div\s+class="title"[^>]*>\s*([^<]+?)\s*</div>', html)
        if m:
            return _clean_title(m.group(1))

    # --- AtCoder --- task pages have <span class="h2">A - Name</span>
    if "atcoder.jp" in host:
        m = re.search(r'<span\s+class="h2"[^>]*>\s*([^<]+?)\s*</span>', html)
        if m:
            t = _clean_title(m.group(1))
            # AtCoder often prefixes with "A - Title"; keep whole thing, useful as-is
            return t

    # --- CodeChef --- problem pages have <h1 ... > Title </h1>  inside problem-statement
    if "codechef.com" in host:
        m = re.search(r'<h3[^>]*class="[^"]*problem-statement[^"]*"[^>]*>([^<]+)</h3>', html)
        if m:
            return _clean_title(m.group(1))

    # --- Generic fallback: <title>...</title>
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if m:
        title = _clean_title(m.group(1))
        # Strip common site suffixes
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


def _clean_title(s: str) -> str:
    return unescape(re.sub(r"\s+", " ", s)).strip()


# ---------------------------------------------------------------------------
# Codeforces API lookup
# ---------------------------------------------------------------------------

CF_API_URL = "https://codeforces.com/api/problemset.problems"
_CF_CACHE = {"data": None, "fetched_at": 0.0}
_CF_TTL_SECONDS = 24 * 60 * 60   # refresh once a day


def difficulty_from_cf_rating(rating):
    """Map a Codeforces problem rating to our difficulty bucket.
    <1600 Easy / 1600-1900 Normal / 2000-2200 Normal-Hard /
    2300-2500 Hard / >2500 Challenge."""
    if rating is None:
        return None
    try:
        r = int(rating)
    except (TypeError, ValueError):
        return None
    if r < 1600:  return "Easy"
    if r <= 1900: return "Normal"
    if r <= 2200: return "Normal-Hard"
    if r <= 2500: return "Hard"
    return "Challenge"


def _cf_url_to_ids(url: str):
    """Extract (contest_id, index) from a Codeforces problem URL.
    Supports /problemset/problem/<id>/<idx>, /contest/<id>/problem/<idx>, /gym/<id>/problem/<idx>."""
    m = re.search(r"/(?:problemset/problem|contest|gym)/(\d+)/(?:problem/)?([A-Za-z0-9]+)", url)
    if not m:
        return None
    return int(m.group(1)), m.group(2).upper()


def _cf_fetch_index():
    """Return the cached CF problemset index, refreshing if stale."""
    import time
    if _CF_CACHE["data"] and time.time() - _CF_CACHE["fetched_at"] < _CF_TTL_SECONDS:
        return _CF_CACHE["data"]
    try:
        req = urllib.request.Request(
            CF_API_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ICPC-Training/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        if data.get("status") == "OK":
            _CF_CACHE["data"] = data["result"]
            _CF_CACHE["fetched_at"] = time.time()
            return _CF_CACHE["data"]
    except (urllib.error.URLError, ValueError, TimeoutError, OSError, json.JSONDecodeError):
        return None
    return None


# --- URL → platform / contest_type defaults ----------------------------------

def detect_platform_and_contest(url: str):
    """Best-guess (platform, contest_type) from a URL. Either may be None."""
    try:
        parts = urllib.parse.urlparse(url)
    except Exception:
        return (None, None)
    host = (parts.hostname or "").lower()
    path = parts.path or ""

    if "codeforces.com" in host:
        if "/gym/" in path:
            return ("Codeforces", "Gym")
        if "/problemset" in path or "/contest/" in path:
            return ("Codeforces", "Codeforces Round")
        return ("Codeforces", "Codeforces Round")
    if "atcoder.jp" in host:
        m = re.search(r"/contests/([a-z]+)", path, re.IGNORECASE)
        if m:
            kind = m.group(1).lower()
            if kind.startswith("abc"): return ("AtCoder", "AtCoder ABC")
            if kind.startswith("arc"): return ("AtCoder", "AtCoder ARC")
            if kind.startswith("agc"): return ("AtCoder", "AtCoder AGC")
        return ("AtCoder", "Practice")
    if "codechef.com" in host:
        return ("CodeChef", "Practice")
    if "kattis.com" in host or "icpcarchive.ecs.baylor.edu" in host or "icpc.global" in host:
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


# --- CF tag → topic / sub_topic mapping --------------------------------------

CF_TAG_TO_TOPIC = {
    "dp":                       "DP",
    "graphs":                   "Graph",
    "shortest paths":           "Graph",
    "dfs and similar":          "Graph",
    "graph matchings":          "Flows / Matching",
    "trees":                    "Tree",
    "data structures":          "Data Structures",
    "dsu":                      "DSU",
    "trie":                     "Trie",
    "binary search":            "Binary Search",
    "ternary search":           "Binary Search",
    "two pointers":             "Two Pointers",
    "sortings":                 "Sorting",
    "bitmasks":                 "Bitmask",
    "flows":                    "Flows / Matching",
    "matchings":                "Flows / Matching",
    "fft":                      "FFT / NTT",
    "ntt":                      "FFT / NTT",
    "math":                     "Math",
    "matrices":                 "Math",
    "number theory":            "Number Theory",
    "combinatorics":            "Combinatorics",
    "probabilities":            "Probability",
    "games":                    "Game Theory",
    "geometry":                 "Geometry",
    "strings":                  "Strings",
    "string suffix structures": "Strings",
    "hashing":                  "Strings",
    "expression parsing":       "Strings",
    "greedy":                   "Greedy",
    "constructive algorithms":  "Constructive",
    "implementation":           "Implementation",
    "brute force":              "Implementation",
    "divide and conquer":       "Misc",
    "2-sat":                    "Graph",
    "interactive":              "Misc",
    "schedules":                "Misc",
}

# Specific topics worth surfacing as the *primary* topic over a generic one.
SPECIFIC_TOPICS = {
    "Segment Tree", "DSU", "Trie", "Binary Search", "Two Pointers",
    "Bitmask", "Flows / Matching", "FFT / NTT",
}


def topic_from_cf_tags(tags):
    """Pick a primary topic + a comma-separated sub-topic from CF tags.
    Returns (topic, sub_topic) where either may be None.
    Strategy: prefer a specific topic match; otherwise the first general match.
    Sub-topic = the remaining CF tags joined as Title Case."""
    if not tags:
        return (None, None)
    mapped = []   # parallel list of (cf_tag, mapped_topic_or_None)
    for t in tags:
        mapped.append((t, CF_TAG_TO_TOPIC.get(t.lower())))
    # Prefer a specific topic if any CF tag maps to one
    primary = None
    primary_idx = None
    for i, (_, m) in enumerate(mapped):
        if m and m in SPECIFIC_TOPICS:
            primary, primary_idx = m, i
            break
    # Fall back to first general match
    if primary is None:
        for i, (_, m) in enumerate(mapped):
            if m:
                primary, primary_idx = m, i
                break
    # Build sub-topic from the remaining CF tags
    remaining = [t for i, (t, _) in enumerate(mapped) if i != primary_idx]
    sub = ", ".join(s.title() for s in remaining) if remaining else None
    return (primary, sub)


def fetch_codeforces_details(url: str):
    """Return {name, rating, tags, difficulty} for a CF URL, or None."""
    parsed = _cf_url_to_ids(url)
    if not parsed:
        return None
    contest_id, index = parsed
    idx = _cf_fetch_index()
    if not idx:
        return None
    for p in idx.get("problems", []):
        if p.get("contestId") == contest_id and p.get("index") == index:
            rating = p.get("rating")
            return {
                "name":       p.get("name"),
                "rating":     rating,
                "tags":       p.get("tags") or [],
                "difficulty": difficulty_from_cf_rating(rating),
            }
    return None


@app.route("/api/lookup", methods=["GET"])
@login_required
def lookup_problem():
    """Resolve a problem URL to as much metadata as we can get.
    For Codeforces URLs, hits the Codeforces API for name + rating + tags +
    derived difficulty + topic + sub-topic.  Detects platform + contest_type
    from URL for every supported host.  Falls back to title-tag scraping
    for the name on unsupported hosts."""
    url = (request.args.get("url") or "").strip()
    if not url:
        abort(400, description="`url` query param required")
    if not (url.startswith("http://") or url.startswith("https://")):
        abort(400, description="URL must start with http:// or https://")

    platform, contest_type = detect_platform_and_contest(url)
    out = {
        "url":          url,
        "name":         None,
        "rating":       None,
        "tags":         [],
        "difficulty":   None,
        "topic":        None,
        "sub_topic":    None,
        "platform":     platform,
        "contest_type": contest_type,
    }

    if "codeforces.com" in url:
        cf = fetch_codeforces_details(url)
        if cf and cf.get("name"):
            out.update(cf)
            t, s = topic_from_cf_tags(out.get("tags") or [])
            out["topic"]     = t
            out["sub_topic"] = s
            return jsonify(out)

    out["name"] = fetch_problem_name(url)
    return jsonify(out)


# ---------------------------------------------------------------------------
# Assignment options (for the "Assign to" dropdown in problem form)
# ---------------------------------------------------------------------------

@app.route("/api/assignment-options", methods=["GET"])
@role_required("Admin", "Coach")
def assignment_options():
    """Return all users + teams visible to the caller."""
    db = get_db()
    u = current_user()

    users = db.execute(
        "SELECT id, name, email, role FROM users WHERE is_active = 1 ORDER BY name"
    ).fetchall()
    teams = db.execute(
        "SELECT id, name, institution FROM teams WHERE is_active = 1 ORDER BY name"
    ).fetchall()

    if u["role"] == "Coach":
        # Coach sees everyone for assignment purposes (so they can hand off
        # problems across the program); restrict only if you want stricter scoping.
        pass

    return jsonify({
        "users": [dict(r) for r in users],
        "teams": [dict(r) for r in teams],
    })


# ---------------------------------------------------------------------------
# Per-user attempt (problem_attempts)
# ---------------------------------------------------------------------------

def _user_can_see_problem(user_id: int, problem_id: int) -> bool:
    """Visibility rule used for attempt updates: contestants must be assigned
    directly or via a team they belong to."""
    db = get_db()
    direct = db.execute(
        "SELECT 1 FROM problem_users WHERE problem_id = ? AND user_id = ?",
        (problem_id, user_id),
    ).fetchone()
    if direct:
        return True
    via_team = db.execute(
        "SELECT 1 FROM problem_teams pt "
        "JOIN team_members tm ON tm.team_id = pt.team_id "
        "WHERE pt.problem_id = ? AND tm.user_id = ?",
        (problem_id, user_id),
    ).fetchone()
    return via_team is not None


@app.route("/api/problems/<int:problem_id>/attempt", methods=["PUT"])
@login_required
def upsert_attempt(problem_id):
    """Upsert the current user's attempt record for a problem.
    Body: {attempt_status?, problem_faced?, time_spent_min?, notes?}"""
    me = current_user()
    db = get_db()
    if not db.execute("SELECT 1 FROM problems WHERE id = ?", (problem_id,)).fetchone():
        abort(404)

    # Contestants are limited to problems assigned to them (or their teams).
    # Coaches/Admins can record attempts for themselves regardless.
    if me["role"] == "Contestant" and not _user_can_see_problem(me["id"], problem_id):
        abort(404)

    payload = request.get_json(force=True, silent=True) or {}
    fields = {}
    if "attempt_status" in payload:
        v = payload["attempt_status"]
        if v not in ATTEMPT_STATUSES and v not in (None, ""):
            abort(400, description=f"attempt_status must be one of {ATTEMPT_STATUSES}")
        fields["attempt_status"] = v or None
    if "problem_faced" in payload:
        v = payload["problem_faced"]
        if v not in PROBLEM_FACED and v not in (None, ""):
            abort(400, description=f"problem_faced must be one of {PROBLEM_FACED}")
        fields["problem_faced"] = v or None
    if "time_spent_min" in payload:
        v = payload["time_spent_min"]
        if v in (None, ""):
            fields["time_spent_min"] = None
        else:
            try:
                fields["time_spent_min"] = max(0, int(v))
            except (TypeError, ValueError):
                abort(400, description="time_spent_min must be an integer (minutes)")
    if "notes" in payload:
        fields["notes"] = (payload["notes"] or "").strip() or None
    if "attempt_phase" in payload:
        v = payload["attempt_phase"]
        if v not in ATTEMPT_PHASES and v not in (None, ""):
            abort(400, description=f"attempt_phase must be one of {ATTEMPT_PHASES}")
        fields["attempt_phase"] = v or None

    # Server-side rule: marking Accepted requires time + notes + phase.
    # Phase is mandatory because the Assigned-Contest progress view depends on
    # it — an Accepted attempt without a phase can't be classified into the
    # during/upsolved buckets and would silently leak into a "—" pile.
    if fields.get("attempt_status") == "Accepted":
        existing = db.execute(
            "SELECT time_spent_min, notes, attempt_phase "
            "FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
            (problem_id, me["id"]),
        ).fetchone()
        # New value if provided in this call, else fall back to whatever's on
        # the existing row.  Defensive read for `attempt_phase` since legacy
        # rows pre-date the column.
        ts = fields["time_spent_min"] if "time_spent_min" in fields else (existing["time_spent_min"] if existing else None)
        nt = fields["notes"]          if "notes"          in fields else (existing["notes"]          if existing else None)
        if "attempt_phase" in fields:
            ph = fields["attempt_phase"]
        else:
            try:    ph = existing["attempt_phase"] if existing else None
            except (IndexError, KeyError): ph = None
        if ts in (None, "") or not (nt or "").strip():
            abort(400, description="Marking a problem Accepted requires both Time Spent and Notes.")
        if ph not in ATTEMPT_PHASES:
            abort(400, description="Marking a problem Accepted requires picking when you solved it (During Contest / Upsolve).")

    if not fields:
        abort(400, description="No fields to update")

    existing = db.execute(
        "SELECT id FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
        (problem_id, me["id"]),
    ).fetchone()
    if existing:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        db.execute(
            f"UPDATE problem_attempts SET {set_clause}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE problem_id = ? AND user_id = ?",
            [*fields.values(), problem_id, me["id"]],
        )
    else:
        cols = ["problem_id", "user_id", *fields.keys()]
        ph   = ", ".join(["?"] * len(cols))
        db.execute(
            f"INSERT INTO problem_attempts ({', '.join(cols)}) VALUES ({ph})",
            [problem_id, me["id"], *fields.values()],
        )
    db.commit()

    row = db.execute(
        "SELECT attempt_status, attempt_phase, problem_faced, "
        "       time_spent_min, notes, updated_at "
        "FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
        (problem_id, me["id"]),
    ).fetchone()
    return jsonify(dict(row))


# ===========================================================================
# AUTH endpoints
# ===========================================================================

@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    """Public signup. Always creates a Contestant. Admins/Coaches must be promoted by an admin."""
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["email", "password", "name"])

    email    = data["email"].strip().lower()
    password = data["password"]
    name     = data["name"].strip()

    if len(password) < 8:
        abort(400, description="Password must be at least 8 characters")

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        abort(409, description="An account with that email already exists")

    cur = db.execute(
        "INSERT INTO users (email, password_hash, name, role, handle, institution, year_of_study) "
        "VALUES (?, ?, ?, 'Contestant', ?, ?, ?)",
        (
            email,
            generate_password_hash(password),
            name,
            (data.get("handle") or "").strip() or None,
            (data.get("institution") or "").strip() or None,
            data.get("year_of_study") or None,
        ),
    )
    db.commit()
    session.clear()
    session.permanent = True
    session["user_id"] = cur.lastrowid

    db.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (cur.lastrowid,))
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(public_user(row)), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["email", "password"])
    email    = data["email"].strip().lower()
    password = data["password"]

    row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        abort(401, description="Invalid email or password")
    if not row["is_active"]:
        abort(403, description="Account is deactivated")

    session.clear()
    session.permanent = True
    session["user_id"] = row["id"]

    get_db().execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    get_db().commit()
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
    return jsonify(public_user(row))


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def auth_me():
    u = current_user()
    if not u:
        return jsonify({"authenticated": False}), 200
    return jsonify({"authenticated": True, "user": u})


@app.route("/api/auth/password", methods=["POST"])
@login_required
def auth_change_password():
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["current_password", "new_password"])
    if len(data["new_password"]) < 8:
        abort(400, description="New password must be at least 8 characters")
    u = current_user()
    row = get_db().execute("SELECT password_hash FROM users WHERE id = ?", (u["id"],)).fetchone()
    if not check_password_hash(row["password_hash"], data["current_password"]):
        abort(401, description="Current password is incorrect")
    get_db().execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (generate_password_hash(data["new_password"]), u["id"]),
    )
    get_db().commit()
    return jsonify({"ok": True})


# ===========================================================================
# USERS endpoints
# ===========================================================================

@app.route("/api/users", methods=["GET"])
@login_required
def list_users():
    """Admins see all. Coaches see contestants on teams they coach + other coaches/admins."""
    u = current_user()
    db = get_db()
    role_f = request.args.get("role")
    q      = request.args.get("q")

    where, params = [], []
    if role_f:
        where.append("role = ?"); params.append(role_f)
    if q:
        like = f"%{q}%"
        where.append("(name LIKE ? OR email LIKE ? OR handle LIKE ? OR institution LIKE ?)")
        params.extend([like, like, like, like])

    sql = "SELECT id, email, name, role, handle, institution, year_of_study, is_active, date_joined, last_login FROM users"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY name"
    rows = db.execute(sql, params).fetchall()

    # Coach: see admins/coaches + contestants on their teams
    if u["role"] == "Coach":
        coach_team_ids = {r["team_id"] for r in db.execute(
            "SELECT team_id FROM team_coaches WHERE user_id = ?", (u["id"],)
        )}
        visible_contestants = set()
        if coach_team_ids:
            placeholders = ",".join("?" * len(coach_team_ids))
            for r in db.execute(
                f"SELECT user_id FROM team_members WHERE team_id IN ({placeholders})",
                tuple(coach_team_ids),
            ):
                visible_contestants.add(r["user_id"])
        rows = [r for r in rows if r["role"] in ("Admin", "Coach") or r["id"] in visible_contestants]

    # Contestant: see only themselves
    elif u["role"] == "Contestant":
        rows = [r for r in rows if r["id"] == u["id"]]

    return jsonify([public_user(r) for r in rows])


@app.route("/api/users/<int:uid>", methods=["GET"])
@login_required
def get_user(uid):
    u = current_user()
    if u["role"] != "Admin" and u["id"] != uid and u["role"] != "Coach":
        abort(403)
    row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        abort(404)
    return jsonify(public_user(row))


@app.route("/api/users/<int:uid>", methods=["PATCH"])
@login_required
def update_user(uid):
    u = current_user()
    data = request.get_json(force=True, silent=True) or {}

    self_only = {"name", "handle", "institution", "year_of_study"}
    admin_only = {"role", "is_active", "email"}

    if u["id"] != uid and u["role"] != "Admin":
        abort(403)

    fields = {}
    for k, v in data.items():
        if k in self_only:
            fields[k] = v
        elif k in admin_only and u["role"] == "Admin":
            if k == "role" and v not in USER_ROLES:
                abort(400, description=f"role must be one of {USER_ROLES}")
            if k == "is_active":
                v = 1 if v else 0
            if k == "email":
                v = v.strip().lower()
            fields[k] = v
        # silently drop unknown fields

    if not fields:
        abort(400, description="No editable fields supplied")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    try:
        get_db().execute(
            f"UPDATE users SET {set_clause} WHERE id = ?",
            [*fields.values(), uid],
        )
        get_db().commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))

    row = get_db().execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()
    if not row:
        abort(404)
    return jsonify(public_user(row))


@app.route("/api/users", methods=["POST"])
@role_required("Admin")
def admin_create_user():
    """Admin creates an account directly (any role)."""
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["email", "password", "name", "role"])
    if data["role"] not in USER_ROLES:
        abort(400, description=f"role must be one of {USER_ROLES}")
    if len(data["password"]) < 8:
        abort(400, description="Password must be at least 8 characters")
    email = data["email"].strip().lower()
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        abort(409, description="An account with that email already exists")
    cur = db.execute(
        "INSERT INTO users (email, password_hash, name, role, handle, institution, year_of_study) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            email,
            generate_password_hash(data["password"]),
            data["name"].strip(),
            data["role"],
            (data.get("handle") or "").strip() or None,
            (data.get("institution") or "").strip() or None,
            data.get("year_of_study") or None,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(public_user(row)), 201


# ===========================================================================
# TEAMS endpoints
# ===========================================================================

def serialize_team(team_row, db) -> dict:
    t = dict(team_row)
    t["is_active"] = bool(t.get("is_active", 1))

    members = db.execute(
        "SELECT u.id, u.name, u.email, u.handle, u.institution, tm.role_in_team, tm.joined_at "
        "FROM team_members tm JOIN users u ON tm.user_id = u.id "
        "WHERE tm.team_id = ? ORDER BY tm.role_in_team, u.name",
        (t["id"],),
    ).fetchall()
    coaches = db.execute(
        "SELECT u.id, u.name, u.email, u.role, tc.assigned_at "
        "FROM team_coaches tc JOIN users u ON tc.user_id = u.id "
        "WHERE tc.team_id = ? ORDER BY u.name",
        (t["id"],),
    ).fetchall()
    t["members"] = [dict(r) for r in members]
    t["coaches"] = [dict(r) for r in coaches]
    t["member_count"]  = sum(1 for r in members if r["role_in_team"] == "Member")
    t["reserve_count"] = sum(1 for r in members if r["role_in_team"] == "Reserve")
    return t


@app.route("/api/teams", methods=["GET"])
@login_required
def list_teams():
    u = current_user()
    db = get_db()

    only_mine = request.args.get("mine") == "1"
    rows = db.execute("SELECT * FROM teams ORDER BY name").fetchall()

    visible = []
    for t in rows:
        if u["role"] == "Admin" and not only_mine:
            visible.append(t); continue
        if is_coach_of(t["id"], u["id"]) or is_member_of(t["id"], u["id"]):
            visible.append(t)

    return jsonify([serialize_team(t, db) for t in visible])


@app.route("/api/teams/<int:tid>", methods=["GET"])
@login_required
def get_team(tid):
    u = current_user()
    db = get_db()
    row = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    if not row:
        abort(404)
    if u["role"] != "Admin" and not is_coach_of(tid, u["id"]) and not is_member_of(tid, u["id"]):
        abort(403)
    return jsonify(serialize_team(row, db))


@app.route("/api/teams", methods=["POST"])
@role_required("Admin", "Coach")
def create_team():
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["name"])
    u = current_user()
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO teams (name, institution, description, created_by) VALUES (?, ?, ?, ?)",
            (data["name"].strip(), (data.get("institution") or "").strip() or None,
             (data.get("description") or "").strip() or None, u["id"]),
        )
        # If creator is a coach, auto-assign them as a coach of this team
        if u["role"] == "Coach":
            db.execute(
                "INSERT INTO team_coaches (team_id, user_id) VALUES (?, ?)",
                (cur.lastrowid, u["id"]),
            )
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))
    row = db.execute("SELECT * FROM teams WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(serialize_team(row, db)), 201


@app.route("/api/teams/<int:tid>", methods=["PATCH"])
@login_required
def update_team(tid):
    if not can_manage_team(tid):
        abort(403)
    data = request.get_json(force=True, silent=True) or {}
    fields = {k: v for k, v in data.items() if k in ("name", "institution", "description", "is_active")}
    if "is_active" in fields:
        fields["is_active"] = 1 if fields["is_active"] else 0
    if not fields:
        abort(400, description="No editable fields supplied")
    db = get_db()
    if not db.execute("SELECT 1 FROM teams WHERE id = ?", (tid,)).fetchone():
        abort(404)
    try:
        db.execute(
            f"UPDATE teams SET {', '.join(f'{k} = ?' for k in fields)} WHERE id = ?",
            [*fields.values(), tid],
        )
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))
    row = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    return jsonify(serialize_team(row, db))


@app.route("/api/teams/<int:tid>", methods=["DELETE"])
@role_required("Admin")
def delete_team(tid):
    db = get_db()
    cur = db.execute("DELETE FROM teams WHERE id = ?", (tid,))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"deleted": tid})


# --- Members --------------------------------------------------------------

@app.route("/api/teams/<int:tid>/members", methods=["POST"])
@login_required
def add_team_member(tid):
    if not can_manage_team(tid):
        abort(403)
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["user_id"])
    role_in_team = (data.get("role_in_team") or "Member").strip()
    if role_in_team not in TEAM_ROLES:
        abort(400, description=f"role_in_team must be one of {TEAM_ROLES}")

    db = get_db()
    if not db.execute("SELECT 1 FROM teams WHERE id = ?", (tid,)).fetchone():
        abort(404, description="Team not found")
    user = db.execute("SELECT id, role FROM users WHERE id = ?", (data["user_id"],)).fetchone()
    if not user:
        abort(404, description="User not found")
    if user["role"] != "Contestant":
        abort(400, description="Only Contestants can be added as Member or Reserve. Use /coaches to assign coaches.")

    counts = db.execute(
        "SELECT role_in_team, COUNT(*) AS n FROM team_members WHERE team_id = ? GROUP BY role_in_team",
        (tid,),
    ).fetchall()
    counts = {r["role_in_team"]: r["n"] for r in counts}
    if role_in_team == "Member" and counts.get("Member", 0) >= MAX_MEMBERS_PER_TEAM:
        abort(409, description=f"Team already has {MAX_MEMBERS_PER_TEAM} members")
    if role_in_team == "Reserve" and counts.get("Reserve", 0) >= MAX_RESERVES_PER_TEAM:
        abort(409, description=f"Team already has {MAX_RESERVES_PER_TEAM} reserve")

    try:
        db.execute(
            "INSERT INTO team_members (team_id, user_id, role_in_team) VALUES (?, ?, ?)",
            (tid, data["user_id"], role_in_team),
        )
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))

    row = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    return jsonify(serialize_team(row, db)), 201


@app.route("/api/teams/<int:tid>/members/<int:uid>", methods=["PATCH"])
@login_required
def update_team_member(tid, uid):
    """Promote Reserve -> Member or demote Member -> Reserve."""
    if not can_manage_team(tid):
        abort(403)
    data = request.get_json(force=True, silent=True) or {}
    new_role = (data.get("role_in_team") or "").strip()
    if new_role not in TEAM_ROLES:
        abort(400, description=f"role_in_team must be one of {TEAM_ROLES}")
    db = get_db()
    if not db.execute(
        "SELECT 1 FROM team_members WHERE team_id = ? AND user_id = ?", (tid, uid)
    ).fetchone():
        abort(404)
    counts = db.execute(
        "SELECT role_in_team, COUNT(*) AS n FROM team_members WHERE team_id = ? AND user_id != ? GROUP BY role_in_team",
        (tid, uid),
    ).fetchall()
    counts = {r["role_in_team"]: r["n"] for r in counts}
    if new_role == "Member" and counts.get("Member", 0) >= MAX_MEMBERS_PER_TEAM:
        abort(409, description=f"Team already has {MAX_MEMBERS_PER_TEAM} members")
    if new_role == "Reserve" and counts.get("Reserve", 0) >= MAX_RESERVES_PER_TEAM:
        abort(409, description=f"Team already has {MAX_RESERVES_PER_TEAM} reserve")
    db.execute(
        "UPDATE team_members SET role_in_team = ? WHERE team_id = ? AND user_id = ?",
        (new_role, tid, uid),
    )
    db.commit()
    row = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    return jsonify(serialize_team(row, db))


@app.route("/api/teams/<int:tid>/members/<int:uid>", methods=["DELETE"])
@login_required
def remove_team_member(tid, uid):
    if not can_manage_team(tid):
        abort(403)
    db = get_db()
    cur = db.execute(
        "DELETE FROM team_members WHERE team_id = ? AND user_id = ?", (tid, uid)
    )
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"team_id": tid, "removed_user_id": uid})


# --- Coaches --------------------------------------------------------------

@app.route("/api/teams/<int:tid>/coaches", methods=["POST"])
@role_required("Admin")
def add_team_coach(tid):
    """Admin assigns a coach (or another admin) to a team."""
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["user_id"])
    db = get_db()
    if not db.execute("SELECT 1 FROM teams WHERE id = ?", (tid,)).fetchone():
        abort(404, description="Team not found")
    user = db.execute("SELECT id, role FROM users WHERE id = ?", (data["user_id"],)).fetchone()
    if not user:
        abort(404, description="User not found")
    if user["role"] not in ("Coach", "Admin"):
        abort(400, description="Only Coach or Admin users can be assigned as a coach")
    try:
        db.execute(
            "INSERT INTO team_coaches (team_id, user_id) VALUES (?, ?)",
            (tid, data["user_id"]),
        )
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))
    row = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    return jsonify(serialize_team(row, db)), 201


@app.route("/api/teams/<int:tid>/coaches/<int:uid>", methods=["DELETE"])
@role_required("Admin")
def remove_team_coach(tid, uid):
    db = get_db()
    cur = db.execute(
        "DELETE FROM team_coaches WHERE team_id = ? AND user_id = ?", (tid, uid)
    )
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"team_id": tid, "removed_user_id": uid})


@app.route("/api/teams/<int:tid>/problems", methods=["GET"])
@login_required
def list_team_problems(tid):
    """Problems assigned to a team, with the per-team-member status breakdown
    embedded (same shape that the Assigned tab uses for its row expand)."""
    db = get_db()
    me = current_user()
    team = db.execute("SELECT * FROM teams WHERE id = ?", (tid,)).fetchone()
    if not team:
        abort(404)
    # Coach must coach this team (or be Admin); contestants must be on it.
    if me["role"] == "Coach" and not is_coach_of(tid, me["id"]):
        abort(403)
    if me["role"] == "Contestant" and not is_member_of(tid, me["id"]):
        abort(403)

    # Mirror the Assigned-Problems tab: exclude rows that came in through an
    # Assign-contest action (those live in the team's Assigned Contests view).
    rows = db.execute(
        "SELECT p.* FROM problem_teams pt "
        "JOIN problems p ON p.id = pt.problem_id "
        "WHERE pt.team_id = ? AND pt.via_contest = 0 "
        "ORDER BY p.date_added DESC",
        (tid,),
    ).fetchall()
    return jsonify({
        "team":     {"id": team["id"], "name": team["name"], "institution": team["institution"]},
        "count":    len(rows),
        "results":  [row_to_dict(r, db, viewer=me) for r in rows],
    })


@app.route("/api/users/<int:uid>/problems", methods=["GET"])
@login_required
def list_user_problems(uid):
    """Problems assigned to a user (directly or via any team they belong to),
    with each row carrying that user's own attempt status."""
    db = get_db()
    me = current_user()
    target = db.execute(
        "SELECT id, name, email, role FROM users WHERE id = ?", (uid,)
    ).fetchone()
    if not target:
        abort(404)
    # Permission: self, Admin, or Coach of any team this user belongs to.
    if me["id"] != uid and me["role"] != "Admin":
        if me["role"] == "Coach":
            n = db.execute(
                "SELECT 1 FROM team_members tm "
                "JOIN team_coaches tc ON tc.team_id = tm.team_id "
                "WHERE tm.user_id = ? AND tc.user_id = ? LIMIT 1",
                (uid, me["id"]),
            ).fetchone()
            if not n:
                abort(403)
        else:
            abort(403)

    # Mirror the Assigned-Problems tab — only direct (via_contest = 0) rows.
    # Contest-derived assignments are reachable via the user's Assigned
    # Contests view, not their per-problem list.
    rows = db.execute(
        "SELECT DISTINCT p.* FROM problems p "
        "WHERE p.id IN (SELECT problem_id FROM problem_users "
        "                WHERE user_id = ? AND via_contest = 0) "
        "   OR p.id IN ("
        "        SELECT pt.problem_id FROM problem_teams pt "
        "        JOIN team_members tm ON tm.team_id = pt.team_id "
        "        WHERE tm.user_id = ? AND pt.via_contest = 0"
        "      ) "
        "ORDER BY p.date_added DESC",
        (uid, uid),
    ).fetchall()

    # Re-shape attempt rows so the "user's own" status is what the UI needs.
    out = []
    for r in rows:
        d = row_to_dict(r, db, viewer=me)
        ar = db.execute(
            "SELECT attempt_status, attempt_phase, problem_faced, "
            "       time_spent_min, notes, updated_at "
            "FROM problem_attempts WHERE problem_id = ? AND user_id = ?",
            (r["id"], uid),
        ).fetchone()
        d["user_attempt"] = _attempt_dict(ar)
        out.append(d)
    return jsonify({
        "user":    dict(target),
        "count":   len(out),
        "results": out,
    })


# ===========================================================================
# BANK endpoints  (Admin / Coach catalog of unassigned problems + contests)
# ===========================================================================

@app.route("/api/bank/problems", methods=["GET"])
@role_required("Admin", "Coach")
def list_bank_problems():
    """The Problem Bank shows standalone problems only.  Problems that belong
    to a contest are reachable through the Contest Bank and are excluded here."""
    args = request.args
    where, params = ["from_contest = 0"], []

    def eq(col, key=None):
        v = args.get(key or col)
        if v:
            where.append(f"{col} = ?")
            params.append(v)

    eq("platform")
    eq("topic")
    eq("difficulty")
    eq("importance")
    eq("contest_type")
    eq("contest_year")

    if args.get("rating_min"):
        where.append("rating >= ?"); params.append(int(args["rating_min"]))
    if args.get("rating_max"):
        where.append("rating <= ?"); params.append(int(args["rating_max"]))

    q = args.get("q")
    if q:
        like = f"%{q}%"
        where.append(
            "(name LIKE ? OR notes LIKE ? OR key_idea LIKE ? OR sub_topic LIKE ? OR tags LIKE ?)"
        )
        params.extend([like, like, like, like, like])

    order_by = resolve_problem_sort(args.get("sort", "date_added"), args.get("order"))

    db = get_db()
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = db.execute(
        f"SELECT * FROM problems{where_clause} ORDER BY {order_by}",
        params,
    ).fetchall()
    total = db.execute(f"SELECT COUNT(*) FROM problems{where_clause}", params).fetchone()[0]

    return jsonify({
        "total":   total,
        "count":   len(rows),
        "results": [row_to_dict(r, db, viewer=current_user()) for r in rows],
    })


@app.route("/api/bank/problems/<int:problem_id>/assign", methods=["POST"])
@role_required("Admin", "Coach")
def assign_from_bank(problem_id):
    """Assign a catalog problem to user(s)/team(s).  The problem stays in the
    bank — Bank is a permanent catalog."""
    db = get_db()
    row = db.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if not row:
        abort(404)

    payload = request.get_json(force=True, silent=True) or {}
    user_ids = _normalize_id_list(payload, "assigned_user_ids", "user")
    team_ids = _normalize_id_list(payload, "assigned_team_ids", "team")
    if not user_ids and not team_ids:
        abort(400, description="Provide at least one assigned_user_ids or assigned_team_ids")
    _validate_assignment(user_ids, team_ids)

    # Direct per-problem assignment ALWAYS gets via_contest = 0; if the row
    # already exists via a prior Assign-contest action we downgrade it (because
    # this explicit assignment is now also a real per-problem assignment).
    if user_ids:
        for uid in user_ids:
            db.execute(
                "INSERT INTO problem_users (problem_id, user_id, via_contest) "
                "VALUES (?, ?, 0) "
                "ON CONFLICT(problem_id, user_id) DO UPDATE SET via_contest = 0",
                (problem_id, uid),
            )
    if team_ids:
        for tid in team_ids:
            db.execute(
                "INSERT INTO problem_teams (problem_id, team_id, via_contest) "
                "VALUES (?, ?, 0) "
                "ON CONFLICT(problem_id, team_id) DO UPDATE SET via_contest = 0",
                (problem_id, tid),
            )
    db.commit()

    row = db.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    return jsonify(row_to_dict(row, db, viewer=current_user()))


# ---------- Contests --------------------------------------------------------

def _contest_summary(db, c) -> dict:
    """Shape a contest row + counts: total problems, and how many of those
    are 'unassigned' (not yet handed out to any user or team).  Also surfaces
    tutorial paths and the assignee lists when present."""
    d = dict(c)
    counts = db.execute(
        "SELECT "
        "  COUNT(*) AS total, "
        "  SUM(CASE WHEN "
        "       (p.id NOT IN (SELECT problem_id FROM problem_users)) "
        "    AND (p.id NOT IN (SELECT problem_id FROM problem_teams)) "
        "  THEN 1 ELSE 0 END) AS unassigned "
        "FROM contest_problems cp "
        "JOIN problems p ON p.id = cp.problem_id "
        "WHERE cp.contest_id = ?",
        (c["id"],),
    ).fetchone()
    d["problem_count"]      = counts["total"]      or 0
    d["bank_problem_count"] = counts["unassigned"] or 0   # field name kept for FE compat

    # Contest-level assignees (independent of per-problem assignments).
    d["assigned_users"] = [
        dict(r) for r in db.execute(
            "SELECT u.id, u.name, u.role FROM contest_users cu "
            "JOIN users u ON u.id = cu.user_id "
            "WHERE cu.contest_id = ? ORDER BY u.name",
            (c["id"],),
        ).fetchall()
    ]
    d["assigned_teams"] = [
        dict(r) for r in db.execute(
            "SELECT t.id, t.name, t.institution FROM contest_teams ct "
            "JOIN teams t ON t.id = ct.team_id "
            "WHERE ct.contest_id = ? ORDER BY t.name",
            (c["id"],),
        ).fetchall()
    ]

    # Tutorial paths — these come straight from the contests row (set by importer).
    # Keep both pdf and translated copy when present so the UI can link both.
    return d


def _contest_with_problems(db, c, viewer) -> dict:
    d = _contest_summary(db, c)
    rows = db.execute(
        "SELECT p.*, cp.order_idx FROM contest_problems cp "
        "JOIN problems p ON p.id = cp.problem_id "
        "WHERE cp.contest_id = ? "
        "ORDER BY COALESCE(cp.order_idx, p.id), p.id",
        (c["id"],),
    ).fetchall()
    d["problems"] = [row_to_dict(r, db, viewer=viewer) for r in rows]
    return d


# ---------- Assigned contests --------------------------------------------

@app.route("/api/contests/assigned", methods=["GET"])
@login_required
def list_assigned_contests():
    """Contests that have been handed out to the current viewer (or, for
    Admin/Coach, to teams in scope).  Each row also carries a solved-progress
    summary computed from the underlying problem_attempts."""
    me = current_user()
    db = get_db()

    if me["role"] == "Admin":
        rows = db.execute(
            "SELECT DISTINCT c.* FROM contests c "
            "WHERE c.id IN (SELECT contest_id FROM contest_users) "
            "   OR c.id IN (SELECT contest_id FROM contest_teams) "
            "ORDER BY c.date_added DESC"
        ).fetchall()
    elif me["role"] == "Coach":
        # A coach sees a contest if any of the following holds:
        #   1. It's assigned to a team they coach.
        #   2. It's assigned to a user who's on a team they coach (covers
        #      the case where a coach hands a contest to an individual
        #      contestant rather than the whole team).
        #   3. It's assigned to the coach directly (as a user).
        # Without (2)+(3) a coach who assigned the contest to one trainee
        # ends up with an empty Assigned Contests tab — confusing.
        rows = db.execute(
            "SELECT DISTINCT c.* FROM contests c "
            "WHERE c.id IN ( "
            "    SELECT ct.contest_id FROM contest_teams ct "
            "    JOIN team_coaches tc ON tc.team_id = ct.team_id "
            "    WHERE tc.user_id = ? "
            ") "
            "OR c.id IN ( "
            "    SELECT cu.contest_id FROM contest_users cu "
            "    JOIN team_members tm ON tm.user_id = cu.user_id "
            "    JOIN team_coaches  tc ON tc.team_id = tm.team_id "
            "    WHERE tc.user_id = ? "
            ") "
            "OR c.id IN ( "
            "    SELECT contest_id FROM contest_users WHERE user_id = ? "
            ") "
            "ORDER BY c.date_added DESC",
            (me["id"], me["id"], me["id"]),
        ).fetchall()
    else:  # Contestant
        rows = db.execute(
            "SELECT DISTINCT c.* FROM contests c "
            "WHERE c.id IN (SELECT contest_id FROM contest_users WHERE user_id = ?) "
            "   OR c.id IN ( "
            "       SELECT ct.contest_id FROM contest_teams ct "
            "       JOIN team_members tm ON tm.team_id = ct.team_id "
            "       WHERE tm.user_id = ? "
            "   ) "
            "ORDER BY c.date_added DESC",
            (me["id"], me["id"]),
        ).fetchall()

    # ----- Phase rollup ------------------------------------------------------
    # For each contest+viewer, count how many problems were solved during the
    # contest vs upsolved later.  The verdict is derived per-problem:
    #   • 'During Contest' if any teammate (or the viewer themself) marked
    #     attempt_phase = 'During Contest' AND attempt_status = 'Accepted';
    #   • else 'Upsolve' if any solved with phase = 'Upsolve';
    #   • else 'Accepted (phase unspecified)' if any plain Accepted with no
    #     phase set (legacy rows from before the field existed);
    #   • else 'Unsolved'.
    #
    # The set of "members" used for the rollup depends on the viewer:
    #   - Contestant: own team(s) on this contest, plus self if individually
    #     assigned.
    #   - Coach: all teams they coach that are assigned the contest.
    #   - Admin: all teams + individuals assigned the contest.
    out = []
    for c in rows:
        d = _contest_summary(db, c)

        # Resolve the user-id set whose attempts count toward this rollup.
        member_ids = set()
        if me["role"] == "Contestant":
            # Teams the viewer is on AND that are assigned this contest.
            for r in db.execute(
                "SELECT tm.user_id FROM contest_teams ct "
                "  JOIN team_members tm ON tm.team_id = ct.team_id "
                "  WHERE ct.contest_id = ? AND tm.team_id IN ("
                "    SELECT team_id FROM team_members WHERE user_id = ?"
                "  )",
                (c["id"], me["id"]),
            ).fetchall():
                member_ids.add(r["user_id"])
            # Also include self if individually assigned.
            if db.execute(
                "SELECT 1 FROM contest_users WHERE contest_id = ? AND user_id = ?",
                (c["id"], me["id"]),
            ).fetchone():
                member_ids.add(me["id"])
            # If somehow the viewer wasn't found in either, fall back to self.
            if not member_ids:
                member_ids.add(me["id"])
        else:
            # Coach/Admin: anyone the contest is assigned to.
            for r in db.execute(
                "SELECT user_id FROM contest_users WHERE contest_id = ?",
                (c["id"],),
            ).fetchall():
                member_ids.add(r["user_id"])
            for r in db.execute(
                "SELECT tm.user_id FROM contest_teams ct "
                "  JOIN team_members tm ON tm.team_id = ct.team_id "
                "  WHERE ct.contest_id = ?",
                (c["id"],),
            ).fetchall():
                member_ids.add(r["user_id"])

        if member_ids:
            placeholders = ",".join(["?"] * len(member_ids))
            phase_rows = db.execute(
                f"SELECT cp.problem_id, "
                f"  MAX(CASE WHEN pa.attempt_status='Accepted' AND pa.attempt_phase='During Contest' THEN 1 ELSE 0 END) AS any_during, "
                f"  MAX(CASE WHEN pa.attempt_status='Accepted' AND pa.attempt_phase='Upsolve'        THEN 1 ELSE 0 END) AS any_upsolve, "
                f"  MAX(CASE WHEN pa.attempt_status='Accepted' THEN 1 ELSE 0 END) AS any_accepted "
                f"FROM contest_problems cp "
                f"LEFT JOIN problem_attempts pa "
                f"  ON pa.problem_id = cp.problem_id AND pa.user_id IN ({placeholders}) "
                f"WHERE cp.contest_id = ? "
                f"GROUP BY cp.problem_id",
                [*member_ids, c["id"]],
            ).fetchall()
            during  = sum(1 for r in phase_rows if r["any_during"])
            upsolve = sum(1 for r in phase_rows if not r["any_during"] and r["any_upsolve"])
            accepted_unphased = sum(
                1 for r in phase_rows
                if r["any_accepted"] and not r["any_during"] and not r["any_upsolve"]
            )
            total_solved = during + upsolve + accepted_unphased
        else:
            during = upsolve = accepted_unphased = total_solved = 0

        d["my_solved"]      = total_solved              # kept for backwards-compat with existing UI
        d["during_count"]   = during
        d["upsolve_count"]  = upsolve
        d["unphased_solved"] = accepted_unphased        # legacy Accepted attempts pre-phase-field
        out.append(d)
    return jsonify(out)


@app.route("/api/bank/contests", methods=["GET"])
@role_required("Admin", "Coach")
def list_contests():
    db = get_db()
    q = request.args.get("q")
    where, params = [], []
    if q:
        like = f"%{q}%"
        where.append("(name LIKE ? OR platform LIKE ? OR notes LIKE ?)")
        params.extend([like, like, like])
    sql = "SELECT * FROM contests"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY date_added DESC"
    rows = db.execute(sql, params).fetchall()
    return jsonify([_contest_summary(db, r) for r in rows])


@app.route("/api/bank/contests/<int:cid>", methods=["GET"])
@login_required
def get_contest(cid):
    """Contest detail (with problems).  Admins/Coaches can view any contest;
    contestants only contests assigned to them or to a team they belong to —
    that's how they drill into the problems for their Assigned Contests."""
    db = get_db()
    row = db.execute("SELECT * FROM contests WHERE id = ?", (cid,)).fetchone()
    if not row:
        abort(404)
    me = current_user()
    if me["role"] == "Contestant":
        ok = db.execute(
            "SELECT 1 FROM contest_users WHERE contest_id = ? AND user_id = ? "
            "UNION ALL "
            "SELECT 1 FROM contest_teams ct "
            "  JOIN team_members tm ON tm.team_id = ct.team_id "
            "  WHERE ct.contest_id = ? AND tm.user_id = ? "
            "LIMIT 1",
            (cid, me["id"], cid, me["id"]),
        ).fetchone()
        if not ok:
            abort(404)
    return jsonify(_contest_with_problems(db, row, current_user()))


@app.route("/api/bank/contests", methods=["POST"])
@role_required("Admin", "Coach")
def create_contest():
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["name"])
    db = get_db()
    cur = db.execute(
        "INSERT INTO contests (name, platform, contest_type, contest_year, url, notes, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            data["name"].strip(),
            (data.get("platform") or "").strip() or None,
            (data.get("contest_type") or "").strip() or None,
            data.get("contest_year") or None,
            (data.get("url") or "").strip() or None,
            (data.get("notes") or "").strip() or None,
            current_user()["id"],
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM contests WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(_contest_summary(db, row)), 201


@app.route("/api/bank/contests/<int:cid>", methods=["PATCH"])
@role_required("Admin", "Coach")
def update_contest(cid):
    data = request.get_json(force=True, silent=True) or {}
    fields = {k: v for k, v in data.items() if k in (
        "name", "platform", "contest_type", "contest_year", "url", "notes")}
    if not fields:
        abort(400, description="No editable fields supplied")
    db = get_db()
    if not db.execute("SELECT 1 FROM contests WHERE id = ?", (cid,)).fetchone():
        abort(404)
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    db.execute(f"UPDATE contests SET {set_clause} WHERE id = ?", [*fields.values(), cid])
    db.commit()
    row = db.execute("SELECT * FROM contests WHERE id = ?", (cid,)).fetchone()
    return jsonify(_contest_summary(db, row))


@app.route("/api/bank/contests/<int:cid>", methods=["DELETE"])
@role_required("Admin")
def delete_contest(cid):
    db = get_db()
    cur = db.execute("DELETE FROM contests WHERE id = ?", (cid,))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"deleted": cid})


@app.route("/api/bank/contests/<int:cid>/problems", methods=["POST"])
@role_required("Admin", "Coach")
def add_problem_to_contest(cid):
    data = request.get_json(force=True, silent=True) or {}
    validate_required(data, ["problem_id"])
    db = get_db()
    if not db.execute("SELECT 1 FROM contests WHERE id = ?", (cid,)).fetchone():
        abort(404, description="Contest not found")
    if not db.execute("SELECT 1 FROM problems WHERE id = ?", (data["problem_id"],)).fetchone():
        abort(404, description="Problem not found")
    try:
        db.execute(
            "INSERT INTO contest_problems (contest_id, problem_id, order_idx) VALUES (?, ?, ?)",
            (cid, data["problem_id"], data.get("order_idx")),
        )
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=str(e))
    row = db.execute("SELECT * FROM contests WHERE id = ?", (cid,)).fetchone()
    return jsonify(_contest_with_problems(db, row, current_user())), 201


@app.route("/api/bank/contests/<int:cid>/problems/<int:pid>", methods=["DELETE"])
@role_required("Admin", "Coach")
def remove_problem_from_contest(cid, pid):
    db = get_db()
    cur = db.execute(
        "DELETE FROM contest_problems WHERE contest_id = ? AND problem_id = ?",
        (cid, pid),
    )
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"contest_id": cid, "removed_problem_id": pid})


@app.route("/api/bank/contests/<int:cid>/assign", methods=["POST"])
@role_required("Admin", "Coach")
def assign_contest(cid):
    """Assign every problem in a contest to the given user(s)/team(s).
    Each affected problem is pulled out of the bank."""
    db = get_db()
    if not db.execute("SELECT 1 FROM contests WHERE id = ?", (cid,)).fetchone():
        abort(404)
    payload = request.get_json(force=True, silent=True) or {}
    user_ids = _normalize_id_list(payload, "assigned_user_ids", "user")
    team_ids = _normalize_id_list(payload, "assigned_team_ids", "team")
    if not user_ids and not team_ids:
        abort(400, description="Provide at least one assigned_user_ids or assigned_team_ids")
    _validate_assignment(user_ids, team_ids)

    pids = [r["problem_id"] for r in db.execute(
        "SELECT problem_id FROM contest_problems WHERE contest_id = ?", (cid,)
    ).fetchall()]
    if not pids:
        abort(409, description="Contest has no problems")

    # Contest-driven rows get via_contest = 1 so the Assigned-Problems list
    # filters them out — they're reachable only through the Assigned-Contests
    # tab.  INSERT OR IGNORE means existing direct (via_contest = 0) rows are
    # preserved unchanged: a manual assignment is "stronger" than a contest one.
    affected = 0
    for pid in pids:
        if user_ids:
            for uid in user_ids:
                db.execute(
                    "INSERT OR IGNORE INTO problem_users "
                    "  (problem_id, user_id, via_contest) VALUES (?, ?, 1)",
                    (pid, uid),
                )
        if team_ids:
            for tid in team_ids:
                db.execute(
                    "INSERT OR IGNORE INTO problem_teams "
                    "  (problem_id, team_id, via_contest) VALUES (?, ?, 1)",
                    (pid, tid),
                )
        affected += 1

    # Record the contest-level assignment so the Assigned Contests tab can
    # surface it without having to re-derive from problem-level junctions.
    if user_ids:
        for uid in user_ids:
            db.execute(
                "INSERT OR IGNORE INTO contest_users (contest_id, user_id) VALUES (?, ?)",
                (cid, uid),
            )
    if team_ids:
        for tid in team_ids:
            db.execute(
                "INSERT OR IGNORE INTO contest_teams (contest_id, team_id) VALUES (?, ?)",
                (cid, tid),
            )
    db.commit()

    row = db.execute("SELECT * FROM contests WHERE id = ?", (cid,)).fetchone()
    return jsonify({
        "contest":            _contest_summary(db, row),
        "problems_assigned":  affected,
    })


# ===========================================================================
# PROBLEMS endpoints (now login-protected; create/edit/delete = Admin/Coach)
# ===========================================================================

# Difficulty has a non-natural ordering — surface it as an explicit rank.
DIFFICULTY_ORDER_SQL = (
    "CASE difficulty "
    "WHEN 'Easy' THEN 1 "
    "WHEN 'Normal' THEN 2 "
    "WHEN 'Normal-Hard' THEN 3 "
    "WHEN 'Hard' THEN 4 "
    "WHEN 'Very Hard' THEN 5 "
    "WHEN 'Challenge' THEN 6 "
    "ELSE 99 END"
)


def resolve_problem_sort(sort: str, order: str):
    """Return a SQL ORDER BY fragment safe to interpolate, given user input."""
    order = (order or "desc").lower()
    if order not in {"asc", "desc"}:
        order = "desc"
    if sort == "difficulty":
        # Empty / unrecognized values sink to the bottom regardless of direction.
        return f"{DIFFICULTY_ORDER_SQL} {order.upper()}, name ASC"
    if sort not in {"name", "rating", "date_added", "importance", "id"}:
        sort = "date_added"
    return f"{sort} {order.upper()}"


CONTESTANT_VISIBILITY_SQL = (
    "(id IN (SELECT problem_id FROM problem_users WHERE user_id = ? AND via_contest = 0)"
    " OR id IN ("
    "    SELECT pt.problem_id FROM problem_teams pt"
    "    JOIN team_members tm ON tm.team_id = pt.team_id"
    "    WHERE tm.user_id = ? AND pt.via_contest = 0"
    "))"
)

COACH_VISIBILITY_SQL = (
    "(id IN ("
    "    SELECT pt.problem_id FROM problem_teams pt "
    "    JOIN team_coaches tc ON tc.team_id = pt.team_id "
    "    WHERE tc.user_id = ? AND pt.via_contest = 0"
    ") OR created_by = ?)"
)


@app.route("/api/problems", methods=["GET"])
@login_required
def list_problems():
    args = request.args
    where, params = [], []

    def eq(col, key=None):
        v = args.get(key or col)
        if v:
            where.append(f"{col} = ?")
            params.append(v)

    eq("platform")
    eq("topic")
    eq("difficulty")
    eq("importance")
    eq("status")
    eq("suggested_role")
    eq("contest_type")
    eq("contest_year")

    if args.get("rating_min"):
        where.append("rating >= ?"); params.append(int(args["rating_min"]))
    if args.get("rating_max"):
        where.append("rating <= ?"); params.append(int(args["rating_max"]))

    q = args.get("q")
    if q:
        like = f"%{q}%"
        where.append(
            "(name LIKE ? OR notes LIKE ? OR key_idea LIKE ? OR sub_topic LIKE ? OR tags LIKE ?)"
        )
        params.extend([like, like, like, like, like])

    # The Assigned Problems tab only ever shows problems that someone is
    # actually working on (vs. the Bank, which holds the catalog).  We
    # explicitly require `via_contest = 0` so problems that came in through an
    # "Assign contest" action don't pollute this list — those live in the
    # Assigned Contests tab and are reachable by clicking into the contest.
    HAS_ANY_ASSIGNMENT_SQL = (
        "(id IN (SELECT problem_id FROM problem_users WHERE via_contest = 0)"
        " OR id IN (SELECT problem_id FROM problem_teams WHERE via_contest = 0))"
    )
    where.append(HAS_ANY_ASSIGNMENT_SQL)

    # Role-scoped visibility
    me = current_user()
    if me["role"] == "Contestant":
        where.append(CONTESTANT_VISIBILITY_SQL)
        params.extend([me["id"], me["id"]])
    elif me["role"] == "Coach":
        # Coach: any problem assigned (directly — not via contest) to a team
        # they coach.  Contest-assigned problems are reachable through the
        # Assigned Contests tab.
        where.append(
            "id IN ("
            "  SELECT pt.problem_id FROM problem_teams pt "
            "  JOIN team_coaches tc ON tc.team_id = pt.team_id "
            "  WHERE tc.user_id = ? AND pt.via_contest = 0"
            ")"
        )
        params.append(me["id"])

    order_by = resolve_problem_sort(args.get("sort", "date_added"), args.get("order"))

    base   = " FROM problems"
    where_clause = (" WHERE " + " AND ".join(where)) if where else ""
    db = get_db()
    rows = db.execute(
        f"SELECT *{base}{where_clause} ORDER BY {order_by}"
        + (" LIMIT ? OFFSET ?" if args.get("limit") else ""),
        (params + [args.get("limit", type=int), args.get("offset", type=int, default=0)])
        if args.get("limit") else params,
    ).fetchall()
    total = db.execute(f"SELECT COUNT(*){base}{where_clause}", params).fetchone()[0]

    return jsonify({
        "total":   total,
        "count":   len(rows),
        "results": [row_to_dict(r, db, viewer=me) for r in rows],
    })


@app.route("/api/problems/<int:problem_id>", methods=["GET"])
@login_required
def get_problem(problem_id):
    db = get_db()
    row = db.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if not row:
        abort(404)
    me = current_user()
    # Coaches and Admins can access any problem (for browsing/editing in the
    # Bank). Contestants are still scoped to what's been assigned to them.
    if me["role"] == "Contestant" and not _user_can_see_problem(me["id"], problem_id):
        abort(404)
    return jsonify(row_to_dict(row, db, viewer=me))


@app.route("/api/problems", methods=["POST"])
@role_required("Admin", "Coach")
def create_problem():
    payload = request.get_json(force=True, silent=True) or {}
    # url + platform are always required; name auto-fetched from URL if missing
    validate_required(payload, ["url", "platform"])
    if not (payload.get("name") or "").strip():
        fetched = fetch_problem_name(payload["url"])
        if not fetched:
            abort(400, description="Could not fetch a name from that URL — please provide one.")
        payload["name"] = fetched

    user_ids = _normalize_id_list(payload, "assigned_user_ids", "user")
    team_ids = _normalize_id_list(payload, "assigned_team_ids", "team")
    _validate_assignment(user_ids, team_ids)
    data = normalize_problem_payload(payload)
    # Stamp the author server-side (cannot be spoofed via payload).
    data["created_by"] = current_user()["id"]
    # Every newly created problem lives in the catalog (Problem Bank).
    data["is_bank"] = 1

    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    db = get_db()
    try:
        cur = db.execute(
            f"INSERT INTO problems ({', '.join(cols)}) VALUES ({placeholders})",
            [data[c] for c in cols],
        )
        if user_ids is not None:
            _replace_problem_users(cur.lastrowid, user_ids)
        if team_ids is not None:
            _replace_problem_teams(cur.lastrowid, team_ids)
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=f"Integrity error: {e}")
    row = db.execute("SELECT * FROM problems WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row, db, viewer=current_user())), 201


def _normalize_id_list(payload: dict, key: str, label: str):
    """Pop `key` from payload, return a clean int list (or None if absent)."""
    if key not in payload:
        return None
    raw = payload.pop(key)
    if raw is None:
        return []
    if not isinstance(raw, list):
        abort(400, description=f"{key} must be a list of {label} ids")
    out = []
    for v in raw:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            abort(400, description=f"Invalid {label} id in {key}: {v!r}")
    seen, deduped = set(), []
    for v in out:
        if v not in seen:
            seen.add(v); deduped.append(v)
    return deduped


def _validate_assignment(user_ids, team_ids):
    """Verify referenced ids exist in their respective tables."""
    db = get_db()
    if user_ids:
        for uid in user_ids:
            if not db.execute("SELECT 1 FROM users WHERE id = ?", (uid,)).fetchone():
                abort(400, description=f"assigned_user_ids contains invalid user id {uid}")
    if team_ids:
        for tid in team_ids:
            if not db.execute("SELECT 1 FROM teams WHERE id = ?", (tid,)).fetchone():
                abort(400, description=f"assigned_team_ids contains invalid team id {tid}")


def _replace_problem_teams(problem_id: int, team_ids):
    """Replace the team-assignment set for a problem (overwrites prior assignments)."""
    db = get_db()
    db.execute("DELETE FROM problem_teams WHERE problem_id = ?", (problem_id,))
    for tid in team_ids:
        db.execute(
            "INSERT OR IGNORE INTO problem_teams (problem_id, team_id) VALUES (?, ?)",
            (problem_id, tid),
        )


def _replace_problem_users(problem_id: int, user_ids):
    """Replace the user-assignment set for a problem (overwrites prior assignments)."""
    db = get_db()
    db.execute("DELETE FROM problem_users WHERE problem_id = ?", (problem_id,))
    for uid in user_ids:
        db.execute(
            "INSERT OR IGNORE INTO problem_users (problem_id, user_id) VALUES (?, ?)",
            (problem_id, uid),
        )


@app.route("/api/problems/<int:problem_id>", methods=["PUT", "PATCH"])
@role_required("Admin", "Coach")
def update_problem(problem_id):
    payload = request.get_json(force=True, silent=True) or {}
    user_ids = _normalize_id_list(payload, "assigned_user_ids", "user")
    team_ids = _normalize_id_list(payload, "assigned_team_ids", "team")
    _validate_assignment(user_ids, team_ids)
    data = normalize_problem_payload(payload)
    if not data and user_ids is None and team_ids is None:
        abort(400, description="No editable fields supplied")
    db = get_db()
    if not db.execute("SELECT id FROM problems WHERE id = ?", (problem_id,)).fetchone():
        abort(404)
    try:
        if data:
            set_clause = ", ".join(f"{k} = ?" for k in data.keys())
            db.execute(
                f"UPDATE problems SET {set_clause} WHERE id = ?",
                [*data.values(), problem_id],
            )
        if user_ids is not None:
            _replace_problem_users(problem_id, user_ids)
        if team_ids is not None:
            _replace_problem_teams(problem_id, team_ids)
        db.commit()
    except dbmod.IntegrityError as e:
        abort(409, description=f"Integrity error: {e}")
    row = db.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
    return jsonify(row_to_dict(row, db, viewer=current_user()))


@app.route("/api/problems/<int:problem_id>", methods=["DELETE"])
@role_required("Admin", "Coach")
def delete_problem(problem_id):
    db = get_db()
    cur = db.execute("DELETE FROM problems WHERE id = ?", (problem_id,))
    db.commit()
    if cur.rowcount == 0:
        abort(404)
    return jsonify({"deleted": problem_id})


@app.route("/api/problems/bulk", methods=["POST"])
@role_required("Admin", "Coach")
def bulk_create():
    payload = request.get_json(force=True, silent=True) or {}
    items = payload.get("items") or []
    if not isinstance(items, list):
        abort(400, description="`items` must be an array")
    db = get_db()
    inserted, skipped = 0, 0
    errors = []
    for idx, item in enumerate(items):
        if not all(item.get(k) for k in ("name", "url", "platform")):
            errors.append({"index": idx, "error": "missing required fields"})
            skipped += 1; continue
        data = normalize_problem_payload(item)
        cols = list(data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        try:
            db.execute(
                f"INSERT INTO problems ({', '.join(cols)}) VALUES ({placeholders})",
                [data[c] for c in cols],
            )
            inserted += 1
        except dbmod.IntegrityError as e:
            errors.append({"index": idx, "error": str(e)})
            skipped += 1
    db.commit()
    return jsonify({"inserted": inserted, "skipped": skipped, "errors": errors})


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------

EXPORT_COLUMNS = [
    ("id",            "ID",             8),
    ("name",          "Name",           38),
    ("url",           "URL",            50),
    ("platform",      "Platform",       14),
    ("contest_type",  "Contest Type",   18),
    ("rating",        "Rating",         8),
    ("difficulty",    "Difficulty",     14),
    ("topic",         "Topic",          18),
    ("sub_topic",     "Sub-topic",      28),
    ("tags",          "Tags",           28),
    ("importance",    "Importance",     12),
    ("assigned_users","Assigned Users", 28),
    ("assigned_teams","Assigned Teams", 28),
    ("notes",         "Notes",          38),
    ("date_added",    "Added",          18),
]


@app.route("/api/export/xlsx", methods=["GET"])
@login_required
def export_xlsx():
    """Export the same problems the caller would see on Assigned Problems,
    respecting current filters / search / sort.  Stays inside the live
    request context so session + auth are preserved."""
    # `list_problems` is just another view function — call it with the
    # *current* request context (which already has the session) instead of
    # spinning up a new one (which breaks @login_required).
    resp  = list_problems()
    rows  = resp.get_json()["results"]

    wb = Workbook()
    ws = wb.active
    ws.title = "Assigned Problems"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F4F6F")

    for c, (_, label, _w) in enumerate(EXPORT_COLUMNS, start=1):
        cell = ws.cell(row=1, column=c, value=label)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r, item in enumerate(rows, start=2):
        for c, (key, _, _w) in enumerate(EXPORT_COLUMNS, start=1):
            if key == "assigned_users":
                v = ", ".join(u["name"] for u in (item.get("assigned_users") or []))
            elif key == "assigned_teams":
                summaries = item.get("team_summary") or []
                if summaries:
                    v = ", ".join(
                        f"{t['team_name']} ({t['solved']}/{t['total']})"
                        for t in summaries if t.get("team_id") is not None
                    )
                else:
                    v = ", ".join(t["name"] for t in (item.get("assigned_teams") or []))
            else:
                v = item.get(key)
                if isinstance(v, list):
                    v = ", ".join(v)
            ws.cell(row=r, column=c, value=v)

    for c, (_, _label, w) in enumerate(EXPORT_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(c)].width = w

    ws.freeze_panes    = "A2"
    ws.auto_filter.ref = ws.dimensions

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"icpc_assigned_problems_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        buf, as_attachment=True, download_name=fname,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@app.route("/api/stats")
@login_required
def stats():
    db = get_db()
    def group(col):
        return [
            dict(r) for r in db.execute(
                f"SELECT {col} AS key, COUNT(*) AS n FROM problems "
                f"WHERE {col} IS NOT NULL AND {col} != '' "
                f"GROUP BY {col} ORDER BY n DESC"
            ).fetchall()
        ]
    total = db.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    return jsonify({
        "total":         total,
        "by_platform":   group("platform"),
        "by_topic":      group("topic"),
        "by_difficulty": group("difficulty"),
        "by_importance": group("importance"),
        "by_status":     group("status"),
    })




# ---------------------------------------------------------------------------
# AI Tutorial routes
# ---------------------------------------------------------------------------
# Backed by tutorials.py. Coaches/admins always get unrestricted access to
# both audiences. Contestants must clear a difficulty-based time-spent gate
# (recorded in tutorial_unlocks) before they can read the student version.

import tutorials as _tut


def _tutorial_role_audience(user, requested):
    """Map (user role, ?audience= override) -> the file we serve.

    Coaches/admins may pass ?audience=student to preview what the team sees.
    Contestants are always served the student version regardless of override
    (defense in depth — the gate is enforced separately).
    """
    role = user["role"]
    if role in ("Admin", "Coach"):
        if requested in ("student", "teacher"):
            return requested
        return "teacher"            # default for staff
    return "student"                # contestants


@app.route("/api/problems/<int:problem_id>/tutorial/status", methods=["GET"])
@login_required
def tutorial_status(problem_id):
    """Return whether a tutorial exists for this problem and what the user is
    allowed to do with it. Frontend uses this to render the right button."""
    user = current_user()
    db = get_db()
    p = db.execute("SELECT id, name, difficulty FROM problems WHERE id = ?",
                   (problem_id,)).fetchone()
    if not p:
        abort(404, description="Problem not found")
    row = db.execute(
        "SELECT status, slug, key_insight, rung_count, mcq_count, snippet_count, "
        "       generated_at, editorial_found "
        "FROM problem_tutorials WHERE problem_id = ?",
        (problem_id,),
    ).fetchone()
    threshold = _tut.time_threshold_minutes(p["difficulty"])

    # Per-contestant unlock state
    is_contestant = user["role"] == "Contestant"
    unlocked = False
    if is_contestant:
        unlocked = bool(db.execute(
            "SELECT 1 FROM tutorial_unlocks WHERE user_id = ? AND problem_id = ?",
            (user["id"], problem_id),
        ).fetchone())

    payload = {
        "problem_id": problem_id,
        "tutorial_exists": bool(row and row["status"] == "done"),
        "tutorial_status": row["status"] if row else "missing",
        "user_role": user["role"],
        "is_contestant": is_contestant,
        "unlocked": unlocked or not is_contestant,    # staff always "unlocked"
        "needs_time_gate": is_contestant and not unlocked,
        "time_threshold_minutes": threshold,
        "difficulty": p["difficulty"],
    }
    if row and row["status"] == "done":
        payload.update({
            "slug": row["slug"],
            "key_insight": row["key_insight"],
            "rung_count": row["rung_count"],
            "mcq_count": row["mcq_count"],
            "snippet_count": row["snippet_count"],
            "generated_at": row["generated_at"],
            "editorial_found": bool(row["editorial_found"]),
            # role -> audience map for the frontend
            "audiences_available": (
                ["student", "teacher"] if user["role"] in ("Admin", "Coach")
                else ["student"]
            ),
        })
    return jsonify(payload)


@app.route("/api/problems/<int:problem_id>/tutorial/unlock", methods=["POST"])
@login_required
def tutorial_unlock(problem_id):
    """Contestant claims they have spent at least the threshold minutes on the
    problem. Records the unlock so future fetches don't prompt again.

    Body: { "claimed_minutes": <int>, "confirm": true }

    Coaches/admins do not need to call this and a 400 is returned if they do.
    """
    user = current_user()
    if user["role"] != "Contestant":
        return jsonify({"error": "Only contestants need to unlock the tutorial."}), 400
    db = get_db()
    p = db.execute("SELECT id, difficulty FROM problems WHERE id = ?",
                   (problem_id,)).fetchone()
    if not p:
        abort(404, description="Problem not found")
    body = request.get_json(silent=True) or {}
    if not body.get("confirm"):
        return jsonify({"error": "Missing confirm=true in request body."}), 400
    threshold = _tut.time_threshold_minutes(p["difficulty"])
    claimed = body.get("claimed_minutes")
    try:
        claimed_int = int(claimed) if claimed is not None else threshold
    except (TypeError, ValueError):
        claimed_int = threshold
    db.execute(
        "INSERT OR IGNORE INTO tutorial_unlocks "
        "(user_id, problem_id, claimed_minutes, threshold_minutes) "
        "VALUES (?, ?, ?, ?)",
        (user["id"], problem_id, claimed_int, threshold),
    )
    db.commit()
    return jsonify({
        "ok": True,
        "problem_id": problem_id,
        "unlocked": True,
        "threshold_minutes": threshold,
        "claimed_minutes": claimed_int,
    })


def _check_audience_authorised(user, problem_id, audience):
    """Return None if allowed; abort otherwise."""
    if user["role"] in ("Admin", "Coach"):
        return None
    if audience == "teacher":
        abort(403, description="Teacher version is for coaches and admins only.")
    # contestant + student requires unlock
    db = get_db()
    if not db.execute(
        "SELECT 1 FROM tutorial_unlocks WHERE user_id = ? AND problem_id = ?",
        (user["id"], problem_id),
    ).fetchone():
        abort(403, description="Tutorial locked. Confirm time spent first.")


@app.route("/api/problems/<int:problem_id>/tutorial", methods=["GET"])
@login_required
def tutorial_html(problem_id):
    """Return the rendered HTML tutorial.
    Query params:
      audience=student|teacher    (coaches/admins only; contestants always get student)
    """
    user = current_user()
    requested = (request.args.get("audience") or "").strip().lower() or None
    audience = _tutorial_role_audience(user, requested)
    _check_audience_authorised(user, problem_id, audience)
    db = get_db()
    row = db.execute(
        "SELECT * FROM problem_tutorials WHERE problem_id = ? AND status = 'done'",
        (problem_id,),
    ).fetchone()
    if not row:
        abort(404, description="Tutorial not yet generated for this problem.")
    html = _tut.render_audience_html(dict(row), audience)
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/api/problems/<int:problem_id>/tutorial.pdf", methods=["GET"])
@login_required
def tutorial_pdf(problem_id):
    """Return the rendered PDF (cached on disk)."""
    user = current_user()
    requested = (request.args.get("audience") or "").strip().lower() or None
    audience = _tutorial_role_audience(user, requested)
    _check_audience_authorised(user, problem_id, audience)
    db = get_db()
    row = db.execute(
        "SELECT * FROM problem_tutorials WHERE problem_id = ? AND status = 'done'",
        (problem_id,),
    ).fetchone()
    if not row:
        abort(404, description="Tutorial not yet generated for this problem.")
    pdf_path = _tut.render_audience_pdf(dict(row), audience)
    return send_file(
        str(pdf_path),
        mimetype="application/pdf",
        as_attachment=False,
        download_name=f"{row['slug']}-{audience}.pdf",
    )




# ---------------------------------------------------------------------------
# AI Tutorial GENERATION routes
# ---------------------------------------------------------------------------
# Spawns tutorial_worker.py as a detached subprocess, which in turn spawns
# `claude -p "Use cp-tutorial-orchestrator on <URL>"` and ingests the
# artifacts. The Flask response is 202 Accepted with the new status — the
# frontend polls /tutorial/status while it runs.

import shlex as _shlex
import subprocess as _subprocess


def _generation_allowed(user) -> bool:
    """Who may trigger AI tutorial generation. By default every logged-in
    user (including Contestants) may trigger it — the user-facing flow is
    designed for self-service. Set TUTORIAL_GENERATION_STAFF_ONLY=1 in the
    server environment to lock generation to Coach/Admin (e.g. to control
    API spend per-team)."""
    if os.environ.get("TUTORIAL_GENERATION_STAFF_ONLY") == "1":
        return user["role"] in ("Admin", "Coach")
    return user["role"] in ("Admin", "Coach", "Contestant")


def _spawn_worker(args_list, log_label) -> int:
    """Spawn tutorial_worker.py detached. Returns the pid we started.

    The worker still talks to SQLite directly (it hasn't been ported to
    Postgres yet) — short-circuit here so a click on "Generate" doesn't
    create an empty problems.db file in the project root and silently
    crash the subprocess.  Remove this guard once tutorial_worker.py uses
    `db.connect()` like the rest of the web app."""
    abort(
        503,
        description=(
            "AI tutorial generation is temporarily disabled — the worker "
            "needs to be ported to Postgres before it can run against "
            "Supabase. See the XXX note at the top of tutorial_worker.py."
        ),
    )
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    log_path = log_dir / f"worker-{log_label}-{int(__import__('time').time())}.log"
    cmd = [sys.executable, str(BASE_DIR / "tutorial_worker.py"), *args_list]
    if os.environ.get("TUTORIAL_WORKER_DRY_RUN") == "1":
        cmd.append("--no-claude")
    # Detach: stdout/stderr to file; new session so Flask shutdown doesn't kill it.
    p = _subprocess.Popen(
        cmd,
        cwd=str(BASE_DIR),
        stdout=open(log_path, "w"),
        stderr=_subprocess.STDOUT,
        stdin=_subprocess.DEVNULL,
        start_new_session=True,
    )
    return p.pid


@app.route("/api/problems/<int:problem_id>/tutorial/generate", methods=["POST"])
@login_required
def tutorial_generate(problem_id):
    """Kick off generation for ONE problem. Coaches/Admins only."""
    user = current_user()
    if not _generation_allowed(user):
        abort(403, description="Only coaches and admins can trigger AI tutorial generation.")
    db = get_db()
    p = db.execute("SELECT id, name, url FROM problems WHERE id = ?", (problem_id,)).fetchone()
    if not p:
        abort(404, description="Problem not found")
    # Refuse if already done unless ?force=1 is passed
    existing = db.execute(
        "SELECT status FROM problem_tutorials WHERE problem_id = ?", (problem_id,)
    ).fetchone()
    if existing and existing["status"] == "generating":
        return jsonify({
            "ok": True, "problem_id": problem_id,
            "status": "generating",
            "message": "Generation already in progress."
        }), 202
    if existing and existing["status"] == "done" and request.args.get("force") != "1":
        return jsonify({
            "ok": False,
            "error": "Tutorial already generated. Pass ?force=1 to regenerate.",
            "status": "done"
        }), 409
    # Mark as queued in DB so the frontend immediately sees the state change
    slug = _tut.slug_for_problem(p)
    db.execute(
        """INSERT INTO problem_tutorials (problem_id, slug, status, error_message)
           VALUES (?, ?, 'queued', NULL)
           ON CONFLICT(problem_id) DO UPDATE SET
             status = 'queued', error_message = NULL, slug = excluded.slug""",
        (problem_id, slug),
    )
    db.commit()
    pid = _spawn_worker(["--problem-ids", str(problem_id)], f"problem-{problem_id}")
    return jsonify({
        "ok": True, "problem_id": problem_id,
        "status": "queued",
        "worker_pid": pid,
        "message": "Generation started. Poll /tutorial/status to track progress."
    }), 202


@app.route("/api/contests/<int:contest_id>/tutorial/generate", methods=["POST"])
@login_required
def tutorial_generate_contest(contest_id):
    """Kick off generation for every problem in a contest that doesn't yet
    have a 'done' tutorial. The worker walks them sequentially."""
    user = current_user()
    if not _generation_allowed(user):
        abort(403, description="Only coaches and admins can trigger AI tutorial generation.")
    db = get_db()
    c = db.execute("SELECT id, name FROM contests WHERE id = ?", (contest_id,)).fetchone()
    if not c:
        abort(404, description="Contest not found")
    rows = db.execute(
        """SELECT p.id, p.url, p.name,
                  COALESCE(t.status, 'missing') AS tut_status
           FROM contest_problems cp
           JOIN problems p ON p.id = cp.problem_id
           LEFT JOIN problem_tutorials t ON t.problem_id = p.id
           WHERE cp.contest_id = ?
           ORDER BY COALESCE(cp.order_idx, p.id), p.id""",
        (contest_id,),
    ).fetchall()
    if not rows:
        return jsonify({"ok": False, "error": "Contest has no problems."}), 400

    todo = [r for r in rows if r["tut_status"] != "done"]
    if not todo:
        return jsonify({
            "ok": True, "contest_id": contest_id,
            "message": "All problems in this contest already have generated tutorials.",
            "queued_count": 0
        }), 200

    # Mark each as queued and spawn ONE worker that walks them all
    for r in todo:
        slug = _tut.slug_for_problem(r)
        db.execute(
            """INSERT INTO problem_tutorials (problem_id, slug, status, error_message)
               VALUES (?, ?, 'queued', NULL)
               ON CONFLICT(problem_id) DO UPDATE SET
                 status = 'queued', error_message = NULL, slug = excluded.slug""",
            (r["id"], slug),
        )
    db.commit()
    pid = _spawn_worker(["--contest-id", str(contest_id)], f"contest-{contest_id}")
    return jsonify({
        "ok": True, "contest_id": contest_id,
        "queued_count": len(todo),
        "worker_pid": pid,
        "message": f"Queued {len(todo)} problem(s). Worker is processing sequentially."
    }), 202


@app.route("/api/contests/<int:contest_id>/tutorial/status", methods=["GET"])
@login_required
def tutorial_status_contest(contest_id):
    """Aggregate generation status across every problem in the contest."""
    db = get_db()
    c = db.execute("SELECT id, name FROM contests WHERE id = ?", (contest_id,)).fetchone()
    if not c:
        abort(404, description="Contest not found")
    rows = db.execute(
        """SELECT p.id, p.name, p.problem_index, p.url,
                  COALESCE(t.status, 'missing') AS status,
                  t.error_message, t.generated_at
           FROM contest_problems cp
           JOIN problems p ON p.id = cp.problem_id
           LEFT JOIN problem_tutorials t ON t.problem_id = p.id
           WHERE cp.contest_id = ?
           ORDER BY COALESCE(cp.order_idx, p.id), p.id""",
        (contest_id,),
    ).fetchall()
    by_status = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return jsonify({
        "contest_id": contest_id,
        "contest_name": c["name"],
        "total":       len(rows),
        "counts":      by_status,
        "any_running": (by_status.get("queued", 0) + by_status.get("generating", 0)) > 0,
        "all_done":    by_status.get("done", 0) == len(rows) and rows,
        "problems": [
            {
                "id":            r["id"],
                "name":          r["name"],
                "problem_index": r["problem_index"],
                "status":        r["status"],
                "error":         r["error_message"],
                "generated_at":  r["generated_at"],
            } for r in rows
        ]
    })


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(409)
def http_error(err):
    desc = err.description if hasattr(err, "description") else str(err)
    return jsonify({"error": desc}), err.code


# ---------------------------------------------------------------------------
# CLI: create-admin
# ---------------------------------------------------------------------------

def cli_create_admin(args):
    """python app.py create-admin EMAIL [NAME]

    Prerequisite: the schema must be applied first via
    `python scripts/seed_postgres.py`.
    """
    if not args:
        print("Usage: python app.py create-admin EMAIL [NAME]")
        sys.exit(1)
    email = args[0].strip().lower()
    name  = args[1] if len(args) > 1 else email.split("@")[0]
    pwd   = os.environ.get("ADMIN_PASSWORD")
    if not pwd:
        pwd = getpass(f"Password for {email} (min 8 chars): ")
        confirm = getpass("Confirm password: ")
        if pwd != confirm:
            print("Passwords do not match"); sys.exit(2)
    if len(pwd) < 8:
        print("Password must be at least 8 characters"); sys.exit(2)

    conn = dbmod.connect()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE users SET password_hash = ?, role = 'Admin', is_active = 1 WHERE id = ?",
            (generate_password_hash(pwd), existing["id"]),
        )
        print(f"Existing user {email!r} promoted to Admin and password reset.")
    else:
        conn.execute(
            "INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, 'Admin')",
            (email, generate_password_hash(pwd), name),
        )
        print(f"Admin {email!r} created.")
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "create-admin":
        cli_create_admin(sys.argv[2:])
        sys.exit(0)

    print(f"[boot] {dbmod.db_label()}")
    print("Open http://127.0.0.1:5000/  (or whatever PORT you set)")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=True)
