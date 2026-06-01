"""
tutorial_worker.py — generation subprocess driver.

Invoked by the Flask /generate routes as a detached subprocess. Walks one or
more problem ids, spawns `claude -p` to run the cp-tutorial-orchestrator
agent on each, and updates the DB so the frontend can poll status.

CLI:

    python3 tutorial_worker.py --problem-ids 215,304
    python3 tutorial_worker.py --contest-id 12
    python3 tutorial_worker.py --problem-ids 215 --no-claude   # dry run

Behaviour:
  1. For each problem, mark `problem_tutorials.status = 'generating'`.
  2. Spawn `claude -p "Use cp-tutorial-orchestrator on <URL>" --output-format stream-json`
     with cwd = PROJECT_ROOT (so .claude/agents/ is found).
  3. If a contest tutorial exists locally (tutorials/<contest-slug>/tutorial.zh-cn.pdf
     or tutorial.en.md), include the path in the orchestrator's instruction so the
     researcher uses it as primary source.
  4. On exit code 0 + artifacts present → register + render PDFs → status='done'.
  5. On any failure → status='failed' with the captured error in error_message.

Logs to stderr; the Flask spawn redirects to a per-job log file under
problem-repository/logs/tutorial-<job-id>.log so coach can debug.
"""
from __future__ import annotations

# XXX: NOT YET PORTED TO POSTGRES (2026-05-30)
# ------------------------------------------------------------------
# This worker still talks directly to a local SQLite file via the
# stdlib `sqlite3` module.  The web app no longer ships such a file —
# the only database is Supabase Postgres reached through `db.py`.
#
# When the AI tutorial generation flow is needed in production, port
# the `_conn()` and `T.DB_PATH` references below to use `db.connect()`
# from the project root.  Until then this worker won't run because its
# DB path (`problems.db`) doesn't exist anymore.
# ------------------------------------------------------------------
import argparse
import json
import os
import re
import shlex
import sqlite3  # legacy — see note above
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import tutorials as T
import editorial_cache as EC


BASE_DIR     = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
LOG_DIR      = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------

def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(T.DB_PATH, timeout=10.0, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode = WAL")
    return c


def mark_status(problem_id: int, status: str, *, error: str | None = None,
                slug: str | None = None) -> None:
    conn = _conn()
    if slug is None:
        existing = conn.execute(
            "SELECT slug FROM problem_tutorials WHERE problem_id = ?",
            (problem_id,)).fetchone()
        if existing:
            slug = existing["slug"]
        else:
            p = conn.execute(
                "SELECT id, name, url, platform, contest_year, problem_index "
                "FROM problems WHERE id = ?", (problem_id,)).fetchone()
            slug = T.slug_for_problem(p) if p else f"unknown-{problem_id}"
    conn.execute(
        """INSERT INTO problem_tutorials (problem_id, slug, status, error_message)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(problem_id) DO UPDATE SET
             status = excluded.status,
             error_message = excluded.error_message,
             slug = excluded.slug""",
        (problem_id, slug, status, error),
    )
    conn.close()


# ---------------------------------------------------------------------------
# Find problems for a contest
# ---------------------------------------------------------------------------

def problems_in_contest(contest_id: int) -> list[dict]:
    conn = _conn()
    rows = conn.execute(
        """SELECT p.id, p.name, p.url, p.platform, p.contest_year, p.problem_index, p.difficulty,
                  COALESCE(p.contest_name, c.name) AS contest_name,
                  c.id AS contest_id, c.tutorial_pdf, c.tutorial_translated
           FROM contest_problems cp
           JOIN problems p ON p.id = cp.problem_id
           JOIN contests  c ON c.id = cp.contest_id
           WHERE cp.contest_id = ?
           ORDER BY COALESCE(cp.order_idx, p.id), p.id""",
        (contest_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def enrich_problem_with_contest(problem: dict) -> dict:
    """If a problem's contest_name/tutorial_pdf are missing, look them up via
    contest_problems → contests. Returns a copy with extra keys filled.
    Idempotent (already-enriched dicts pass through unchanged)."""
    if problem.get("contest_name") and (problem.get("tutorial_pdf") is not None
                                         or "tutorial_pdf" in problem):
        return problem
    conn = _conn()
    try:
        row = conn.execute(
            """SELECT c.id AS contest_id, c.name AS contest_name, c.contest_year,
                      c.tutorial_pdf, c.tutorial_translated
               FROM contest_problems cp
               JOIN contests c ON c.id = cp.contest_id
               WHERE cp.problem_id = ?
               LIMIT 1""",
            (problem["id"],),
        ).fetchone()
        if row:
            out = dict(problem)
            out.setdefault("contest_name",        row["contest_name"])
            out.setdefault("contest_year",        row["contest_year"])
            out["contest_id"]         = row["contest_id"]
            out["tutorial_pdf"]       = row["tutorial_pdf"]
            out["tutorial_translated"]= row["tutorial_translated"]
            return out
    finally:
        conn.close()
    return problem


# ---------------------------------------------------------------------------
# Locate contest base tutorial
# ---------------------------------------------------------------------------

# Tutorial file ranking: prefer text formats over PDFs, English over Chinese.
# A higher rank value wins. Files are scored at lookup time.
_TUTORIAL_RANK = {
    "tutorial.en.md":     100,
    "tutorial.en.pdf":     90,
    "tutorial.zh-cn.md":   60,
    "tutorial.zh-cn.pdf":  50,
    "tutorial.zh-tw.pdf":  45,
    # any other tutorial.* file is a fallback at rank 10
}


def _score_tutorial_file(name: str) -> int:
    if name in _TUTORIAL_RANK:
        return _TUTORIAL_RANK[name]
    return 10 if name.startswith("tutorial.") else 0


def find_contest_base_tutorial(contest_name: str | None,
                               contest_year: int | None,
                               *,
                               direct_path: str | None = None,
                               translated_path: str | None = None) -> Path | None:
    """Find the best local editorial for a contest. Three-tier lookup:

    1. **Direct path** — if the contests row has `tutorial_pdf` or
       `tutorial_translated` populated, prefer those (translated > original).
    2. **Slug fuzzy match** — scan tutorials/ for any folder whose name
       overlaps the contest name and rank `tutorial.*` files in it.
    3. **None** — no editorial available.

    Files are ranked: English markdown > English PDF > Chinese markdown >
    Chinese PDF > anything else. Empty/translation-failed `.md` files are
    demoted so a real PDF beats them.

    For English markdown, the file is rejected if it's tiny or contains
    "translation failed" boilerplate (a common artifact of older translation
    runs). PDFs and Chinese files are always considered if present.
    """
    tut_root = PROJECT_ROOT / "tutorials"

    # Tier 1: trust the contests-row direct path if it points at a real file.
    for cand in (translated_path, direct_path):
        if cand:
            p = (PROJECT_ROOT / cand) if not cand.startswith("/") else Path(cand)
            if p.is_file():
                return p

    if not contest_name:
        return None
    if not tut_root.exists():
        return None

    norm = re.sub(r"[^a-z0-9]+", "-", contest_name.lower()).strip("-")
    candidates = {norm}
    if contest_year:
        candidates.add(f"{norm}-{contest_year}")
        candidates.add(f"the-{contest_year}-{norm}")
        # Common importer pattern: drop the leading "the-" if present
        if norm.startswith("the-"):
            candidates.add(norm[4:])
    candidates = sorted(candidates, key=len, reverse=True)

    best_score = 0
    best_path: Path | None = None
    for child in tut_root.iterdir():
        if not child.is_dir():
            continue
        if not any(g in child.name or child.name in g for g in candidates):
            continue
        for f in child.iterdir():
            if not f.is_file():
                continue
            score = _score_tutorial_file(f.name)
            if score == 0:
                continue
            # Validate text content for .md (don't blindly trust empty translations)
            if f.suffix == ".md":
                text = f.read_text(errors="ignore")
                if len(text) < 500 or "translation failed" in text.lower():
                    score = max(0, score - 70)        # demote bad translations
                    if score == 0:
                        continue
            if score > best_score:
                best_score = score
                best_path = f
    return best_path


# ---------------------------------------------------------------------------
# Run cp-tutorial-orchestrator via `claude -p`
# ---------------------------------------------------------------------------

def build_prompt(problem: dict, base_tutorial: Path | None,
                 explicit_slug: str | None = None,
                 seed_path: Path | None = None) -> str:
    """Build the instruction for `claude -p`. There are TWO modes:

    A. Editorial-grounded FAST path (when base_tutorial is non-null):
       - The orchestrator skips the independent solver entirely.
       - The researcher reads the local editorial PDF/MD, extracts the
         relevant problem's section, and uses it as the canonical solution.
       - Only ONE reviewer (coach-reviewer for pedagogy) — algorithm
         correctness is established by the editorial.
       - Expected runtime: ~10-15 min per problem.

    B. From-scratch SLOW path (when base_tutorial is null):
       - Full pipeline: researcher + solver in parallel, then 3 persona
         reviews. Expected runtime: ~30-45 min per problem.

    The slug is always passed explicitly so the worker's ingestion path
    matches the orchestrator's output path.
    """
    p = problem
    name = p.get("name", "")
    url  = p["url"]
    idx  = p.get("problem_index") or ""
    ctnm = p.get("contest_name") or ""
    yr   = p.get("contest_year") or ""

    parts = []

    if base_tutorial:
        rel = base_tutorial.relative_to(PROJECT_ROOT)
        # Fast path: editorial-grounded
        parts.append(
            f"Use the cp-tutorial-orchestrator subagent in **EDITORIAL-GROUNDED FAST mode** "
            f"to build a Socratic AI tutorial for this problem:"
        )
        parts.append(
            f"\n- URL: {url}"
            f"\n- Name: {name}"
            f"\n- Problem index/letter: {idx or '(unknown — derive from URL or editorial)'}"
            f"\n- Contest: {ctnm} {yr}"
        )
        if seed_path:
            seed_rel = seed_path.relative_to(PROJECT_ROOT)
            parts.append(
                f"\n\n**Per-problem editorial section pre-extracted at: `{seed_rel}`.** "
                f"This is the canonical authoritative source — already extracted from "
                f"the contest PDF and translated to English if needed. "
                f"Read this file FIRST and use it as your primary research material. "
                f"Original contest PDF: `{rel}`."
            )
        else:
            parts.append(
                f"\n\n**Local editorial is available at: `{rel}`.** "
                f"This is the canonical authoritative source. The per-problem cache "
                f"could not be pre-built — run `pdftotext -layout` on the PDF and find "
                f"THIS problem's section yourself."
            )
        parts.append(
            "\n\nFAST-PATH RULES (deviate from the full pipeline as follows):"
            "\n1. SKIP cp-problem-solver entirely — the editorial already has the canonical "
            "solution, independent solving wastes 5-10 min and adds no value."
            "\n2. Run cp-editorial-researcher to extract the per-problem editorial section "
            "(translate from Chinese with `pdftotext` + the WebFetch translate flow if needed). "
            "Save as `research.md`. The researcher MUST cite/quote the editorial directly — "
            "no first-principles reasoning."
            "\n3. Run cp-socratic-coach to draft the ladder, MCQs, snippets — grounded in the "
            "editorial's solution, not independently derived."
            "\n4. Run cp-coach-reviewer ONLY (skip cp-elite-reviewer + cp-weak-student-reviewer). "
            "Algorithm correctness is established by the editorial; only pedagogy needs review."
            "\n5. Run cp-final-editor as usual."
            "\n6. Run cp-version-publisher and cp-tutorial-humanizer as usual."
            "\n\nIf the editorial PDF can't be parsed, or the relevant problem's section isn't "
            "findable, FALL BACK to the full slow path (run cp-problem-solver + 3 reviewers). "
            "Note this fallback in the final tutorial's metadata."
        )
    else:
        # Slow path: from scratch
        parts.append(
            f"Use the cp-tutorial-orchestrator subagent in **FROM-SCRATCH mode** "
            f"to build a Socratic AI tutorial for this problem:"
        )
        parts.append(
            f"\n- URL: {url}"
            f"\n- Name: {name}"
            f"\n- Problem index/letter: {idx or '(unknown)'}"
            f"\n- Contest: {ctnm} {yr}"
        )
        parts.append(
            "\n\nNo local editorial available. Run the full pipeline: research (web search), "
            "independent-solve, draft, 3 persona reviews, final-edit, publish, humanize."
        )

    if explicit_slug:
        parts.append(
            f"\n\n**Output slug — CRITICAL.** Use EXACTLY this slug for the output folder: "
            f"`{explicit_slug}`. Save every artifact under "
            f"`socratic-tutorials/{explicit_slug}/`. Do not invent a different slug. "
            f"The web app reads from this exact path."
        )

    parts.append(
        "\n\nWhen done, report only the slug and a one-line summary. "
        "Do not paste tutorial content in your final response."
    )
    return "".join(parts)


def invoke_claude(prompt: str, log_path: Path,
                  use_claude: bool = True,
                  timeout_seconds: int = 60 * 60) -> tuple[bool, str]:
    """Spawn `claude -p ...` from PROJECT_ROOT so .claude/agents/ is found.

    The agent runs the orchestrator pipeline which uses Task/Write/Bash/Edit
    extensively. We pass --dangerously-skip-permissions explicitly so even
    nested sub-agent permission checks (which sometimes don't honour the
    parent's bypassPermissions) cannot pause the run waiting for a UI dialog
    that will never come.

    Output is streamed to `log_path` line-by-line, so `tail -f` shows real-
    time progress instead of staring at an empty file for 30 minutes.

    Returns (success, brief_summary).
    """
    if not use_claude:
        log_path.write_text(
            f"[{datetime.utcnow().isoformat()}] DRY RUN — would invoke:\n  {prompt}\n"
        )
        return False, "dry-run (--no-claude); no artifacts written"

    # Flags explained:
    #   -p / --print                       non-interactive mode
    #   --dangerously-skip-permissions     no permission prompts AT ALL — even
    #                                      nested agent calls go through. This
    #                                      is the right setting for unattended
    #                                      worker subprocesses; bypassPermissions
    #                                      alone has nested-agent edge cases.
    #   --output-format stream-json        one JSON event per line; we stream
    #                                      these to disk so logs are useful in
    #                                      real time, not just post-mortem.
    #   --verbose                          required when output is stream-json
    #   --add-dir                          ensure project + socratic-tutorials
    #                                      are explicitly writable.
    cmd = [
        "claude",
        "-p", prompt,
        "--dangerously-skip-permissions",
        "--output-format", "stream-json",
        "--verbose",
        "--add-dir", str(PROJECT_ROOT),
        "--add-dir", str(PROJECT_ROOT / "socratic-tutorials"),
    ]
    env = os.environ.copy()
    env.setdefault("HOME", os.path.expanduser("~"))

    # Per-line buffered streaming
    summary_lines: list[str] = []
    last_text = ""
    last_error = ""
    started = time.time()

    with log_path.open("w") as logf:
        logf.write(f"[{datetime.utcnow().isoformat()}] running:\n")
        logf.write(f"  {shlex.join(cmd[:5])} ...\n")           # truncate prompt for header readability
        logf.write(f"  cwd: {PROJECT_ROOT}\n")
        logf.write(f"  HOME={env.get('HOME')}  PATH={env.get('PATH','')[:60]}...\n")
        logf.write(f"  timeout: {timeout_seconds}s\n\n")
        logf.flush()

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(PROJECT_ROOT),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,                           # line-buffered
            )
        except FileNotFoundError:
            logf.write("[claude CLI not on PATH]\n")
            return False, "`claude` CLI not found on PATH"

        try:
            assert proc.stdout is not None
            for line in proc.stdout:
                logf.write(line)
                logf.flush()                          # so `tail -f` works
                # Try to extract structured info from stream-json events.
                stripped = line.strip()
                if stripped.startswith("{"):
                    try:
                        obj = json.loads(stripped)
                    except Exception:
                        obj = None
                    if obj is not None:
                        # Save the most recent assistant text and any error.
                        if obj.get("type") == "result":
                            r = obj.get("result")
                            if isinstance(r, str):
                                last_text = r[-500:]
                            if obj.get("is_error"):
                                last_error = (obj.get("error") or last_text or "is_error=true")[:300]
                        elif obj.get("type") == "assistant":
                            content = (obj.get("message") or {}).get("content") or []
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    last_text = (c.get("text") or "")[-500:]
                        elif obj.get("type") == "system" and obj.get("subtype") == "error":
                            last_error = (obj.get("message") or "")[:300]

                # Bail if we've blown the timeout
                if time.time() - started > timeout_seconds:
                    logf.write(f"\n[TIMEOUT after {timeout_seconds}s — killing claude]\n")
                    proc.kill()
                    proc.wait(timeout=10)
                    return False, f"claude CLI timed out after {timeout_seconds}s"
        finally:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()

    rc = proc.returncode
    summary = (f"ERROR: {last_error}" if last_error else last_text) or f"claude exited rc={rc}"
    summary = summary.replace("\n", " | ")[:500]
    return rc == 0, summary


def _summarise_stream_json(text: str) -> str:
    """Pull the final result message + any visible error from stream-json output."""
    last_text = ""
    last_error = ""
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        # The schema varies a bit by event type; surface what's most informative.
        if obj.get("type") == "result":
            r = obj.get("result")
            if isinstance(r, str) and r:
                last_text = r[-500:]
            err = obj.get("is_error") and obj.get("error")
            if err:
                last_error = str(err)[:300]
        elif obj.get("type") == "assistant":
            content = (obj.get("message") or {}).get("content") or []
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text":
                    last_text = (c.get("text") or "")[-500:]
        elif obj.get("type") == "system" and obj.get("subtype") == "error":
            last_error = obj.get("message") or last_error
    if last_error:
        return f"ERROR: {last_error}"
    return last_text


# ---------------------------------------------------------------------------
# After claude exits: ingest the artifacts
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Deterministic post-process — runs AFTER the agent's cp-tutorial-humanizer
# in case the agent skipped that step (e.g. credit exhaustion). Idempotent;
# just calls T.humanize_markdown on every .md the publisher emits.
# ---------------------------------------------------------------------------

def humanize_disk_files(slug: str) -> dict[str, int]:
    """Read each tutorial file, run humanize_markdown, write back if changed.
    Returns {filename: bytes_changed} for the worker log."""
    sd = T.slug_dir(slug)
    targets = ["tutorial.md", "tutorial.student.md", "tutorial.teacher.md"]
    report = {}
    for name in targets:
        f = sd / name
        if not f.exists():
            continue
        before = f.read_text()
        after = T.humanize_markdown(before)
        if after != before:
            f.write_text(after)
            report[name] = abs(len(after) - len(before))
        else:
            report[name] = 0
    return report


def ingest_artifacts(problem_id: int) -> tuple[bool, str]:
    """Read the slug folder produced by the orchestrator and update the DB.
    Returns (ok, message)."""
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM problems WHERE id = ?", (problem_id,)).fetchone()
        if not row:
            return False, f"problem {problem_id} vanished from DB"
        slug = T.slug_for_problem(row)
        sd = T.slug_dir(slug)
        if not (sd / "tutorial.student.md").exists() or not (sd / "metadata.json").exists():
            return False, f"orchestrator did not produce expected files at {sd}"
        # Deterministic version-publish (replaces cp-version-publisher agent).
        # Reads tutorial.md + metadata.json, writes student/teacher versions,
        # and adds versions/served_to to metadata.json.
        pub_report = T.publish_versions(slug)
        if not pub_report.get("ok"):
            return False, f"publish_versions failed: {pub_report.get('error')}"
        print(f"  publish_versions: student={pub_report.get('student_md_lines')}L "
              f"teacher={pub_report.get('teacher_md_lines')}L", flush=True)
        # Deterministic markup cleanup — fixes <details markdown="1">, code
        # fences, etc. Runs after publish so it covers all three .md files.
        humanize_report = humanize_disk_files(slug)
        if any(humanize_report.values()):
            print(f"  humanize: {humanize_report}", flush=True)
        T.upsert_tutorial_from_artifacts(conn, problem_id)
        # Render PDFs (best-effort; we don't fail the whole job if PDF fails)
        try:
            tut_row = T.get_tutorial_row(conn, problem_id)
            if tut_row:
                T.render_audience_pdf(tut_row, "student")
                T.render_audience_pdf(tut_row, "teacher")
        except Exception as e:
            return True, f"registered (PDF render failed: {e})"
        return True, f"registered slug={slug}, PDFs rendered"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Per-problem driver
# ---------------------------------------------------------------------------



def derive_problem_letter(problem: dict) -> str | None:
    """Best-effort: figure out which letter (A, B, C, ...) this problem is in
    its contest. Sources: problem_index field, URL pattern, name match."""
    idx = (problem.get("problem_index") or "").strip().upper()
    if idx and len(idx) <= 2 and idx[0].isalpha():
        return idx[0]
    # UCup URLs: contest/<cid>/problem/<pid> — the pid is numeric, not a letter,
    # but the problem ORDER in the contest gives us the letter. We get this
    # from the contest_problems.order_idx if available.
    return None


def derive_letter_from_order(conn, contest_id: int, problem_id: int) -> str | None:
    """Fallback: look up the problem's order_idx in this contest and convert
    to a letter. The DB stores 1-indexed values for some imports and 0-indexed
    for others — we normalise by subtracting the contest's min order_idx, so
    the FIRST problem in either scheme maps to A."""
    if not contest_id:
        return None
    row = conn.execute(
        """SELECT order_idx,
                  (SELECT MIN(order_idx) FROM contest_problems
                   WHERE contest_id = ? AND order_idx IS NOT NULL) AS base
           FROM contest_problems
           WHERE contest_id = ? AND problem_id = ?
           LIMIT 1""",
        (contest_id, contest_id, problem_id),
    ).fetchone()
    if row and row["order_idx"] is not None:
        idx = row["order_idx"] - (row["base"] or 0)
        if 0 <= idx < 26:
            return chr(ord("A") + idx)
    return None


def preextract_editorial(problem: dict, base_path: Path, slug_dir: Path) -> Path | None:
    """If the editorial cache has THIS problem's section, copy it into the
    slug folder as `research-seed.md` so the agent reads it directly. Returns
    the seed path if successful, None otherwise."""
    # Figure out which letter this problem is
    letter = derive_problem_letter(problem)
    if not letter and problem.get("contest_id"):
        conn = _conn()
        try:
            letter = derive_letter_from_order(conn, problem["contest_id"], problem["id"])
        finally:
            conn.close()
    if not letter:
        return None

    try:
        section_path = EC.get_problem_section(base_path, letter)
    except Exception as e:
        print(f"  editorial cache build failed: {e}", flush=True)
        return None
    if not section_path or not section_path.exists():
        print(f"  no editorial section for letter {letter} in cache", flush=True)
        return None

    # Copy into the slug folder so the agent reads it as research-seed.md
    seed = slug_dir / "research-seed.md"
    seed.write_text(
        f"# Editorial extract for Problem {letter} — {problem.get('name','')}\n\n"
        f"_Source: `{base_path.relative_to(PROJECT_ROOT)}`, problem letter `{letter}`, "
        f"language: {(EC._cache_dir(base_path.parent) / 'language.txt').read_text().strip()}._\n\n"
        f"---\n\n"
        + section_path.read_text()
    )
    return seed


def run_one(problem: dict, *, use_claude: bool = True) -> bool:
    pid = problem["id"]
    # Enrich with contest info (tutorial_pdf, contest_name) if not already there
    problem = enrich_problem_with_contest(problem)
    slug = T.slug_for_problem(problem)
    print(f"[{datetime.utcnow().isoformat()}] PROBLEM {pid} {problem.get('name')!r} (slug={slug}) starting", flush=True)
    mark_status(pid, "generating", slug=slug)
    base = find_contest_base_tutorial(
        problem.get("contest_name"),
        problem.get("contest_year"),
        direct_path     = problem.get("tutorial_pdf"),
        translated_path = problem.get("tutorial_translated"),
    )
    if base:
        print(f"  using contest base tutorial: {base.relative_to(PROJECT_ROOT)}", flush=True)
    # Make sure the output dir exists and is writable BEFORE the agent starts —
    # this avoids the orchestrator pausing waiting for "create directory" permission.
    out_dir = T.SOCRATIC_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    # Pre-extract THIS problem's section from the cached editorial. If the
    # editorial is non-English, the cache also has a translated version.
    seed_path = None
    if base:
        seed_path = preextract_editorial(problem, base, out_dir)
        if seed_path:
            print(f"  pre-extracted editorial section -> {seed_path.relative_to(PROJECT_ROOT)}", flush=True)
        else:
            print(f"  could not pre-extract — agent will run pdftotext itself", flush=True)
    prompt = build_prompt(problem, base, explicit_slug=slug, seed_path=seed_path)
    log_path = LOG_DIR / f"tutorial-{pid}-{int(time.time())}.log"
    ok, summary = invoke_claude(prompt, log_path, use_claude=use_claude)
    print(f"  claude: ok={ok}  summary={summary[:200]}", flush=True)
    if not ok:
        mark_status(pid, "failed", error=f"claude: {summary}  (log: {log_path.name})", slug=slug)
        return False
    ok2, msg2 = ingest_artifacts(pid)
    if not ok2:
        mark_status(pid, "failed", error=f"ingest: {msg2}  (log: {log_path.name})", slug=slug)
        return False
    print(f"  done. {msg2}", flush=True)
    return True


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Doctor — environment diagnostics
# ---------------------------------------------------------------------------

def doctor() -> int:
    """Verify the environment can actually generate tutorials. Returns 0 on
    success, non-zero if something is broken. Printed output is human-readable.
    """
    print("=== Tutorial generation doctor ===")
    print()

    ok = True
    def check(label, condition, hint=""):
        nonlocal ok
        mark = "[✓]" if condition else "[✗]"
        print(f"  {mark} {label}")
        if not condition and hint:
            print(f"      → {hint}")
        if not condition: ok = False

    # 1. claude CLI on PATH
    import shutil as _sh
    claude_path = _sh.which("claude")
    check(f"claude CLI on PATH ({claude_path or 'NOT FOUND'})", bool(claude_path),
          "Install Claude Code: https://docs.claude.com/claude-code")

    # 2. Project root + agents directory
    agents_dir = PROJECT_ROOT / ".claude" / "agents"
    check(f"agents dir exists ({agents_dir})", agents_dir.exists(),
          "The .claude/agents/ folder is missing — re-run the setup steps that wrote it")

    found = list(agents_dir.glob("cp-*.md")) if agents_dir.exists() else []
    check(f"sub-agent .md files found ({len(found)} files)", len(found) >= 8,
          "Expected 8 cp-*.md files in .claude/agents/")

    # 3. socratic-tutorials writable
    sd = PROJECT_ROOT / "socratic-tutorials"
    is_dir = sd.is_dir()
    is_link = sd.is_symlink()
    check(f"socratic-tutorials/ exists and is a real directory (not a symlink)",
          is_dir and not is_link,
          f"`mv socratic-tutorials .stash; mkdir socratic-tutorials; mv .stash/* socratic-tutorials/; rmdir .stash`"
          if is_link else "Create the directory: `mkdir socratic-tutorials`")

    if is_dir and not is_link:
        # Check for stray inner symlink
        stray = sd / "socratic-tutorials"
        check("no stray socratic-tutorials/socratic-tutorials symlink",
              not stray.exists() and not stray.is_symlink(),
              f"Run: `rm \"{stray}\"` to remove the stray symlink")
        # Try a real write
        try:
            t = sd / ".doctor-write-test"
            t.write_text("ok")
            t.unlink()
            check("write to socratic-tutorials/ succeeds", True)
        except Exception as e:
            check("write to socratic-tutorials/ succeeds", False, f"Permission denied: {e}")

    # 4. claude can authenticate
    if claude_path:
        print()
        print("  Testing `claude -p` authentication (10s timeout)...")
        try:
            res = subprocess.run(
                ["claude", "-p", "Reply with the word PONG and nothing else.",
                 "--dangerously-skip-permissions",
                 "--output-format", "json"],
                cwd=str(PROJECT_ROOT),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=30,
            )
            txt = res.stdout or ""
            authed = ("not logged in" not in txt.lower() and
                      "authentication" not in txt.lower() and
                      res.returncode == 0)
            check(f"claude -p reaches the API (rc={res.returncode})", authed,
                  "Run `claude /login` from your terminal once to authenticate, then retry")
            if not authed:
                print(f"      claude output: {txt[:300]}")
        except subprocess.TimeoutExpired:
            check("claude -p reaches the API in time", False,
                  "claude CLI is hanging — check network and try `claude /login` interactively")
        except Exception as e:
            check("claude -p reaches the API", False, str(e))

    # 5. DB tables present
    try:
        conn = _conn()
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%tutorial%'")]
        check(f"problem_tutorials + tutorial_unlocks tables present ({tables})",
              "problem_tutorials" in tables and "tutorial_unlocks" in tables,
              "Re-run the schema migration in app.py")
        conn.close()
    except Exception as e:
        check("DB reachable", False, str(e))

    print()
    print("All checks passed." if ok else "FAILURES above — fix the [✗] items, then retry the Generate button.")
    return 0 if ok else 1


def clean_failed() -> int:
    """Clear failed/queued tutorial rows so the buttons go back to Generate."""
    conn = _conn()
    n = conn.execute(
        "DELETE FROM problem_tutorials WHERE status IN ('failed','queued','generating')"
    ).rowcount
    conn.close()
    print(f"Removed {n} failed/queued/generating tutorial rows.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--problem-ids", help="Comma-separated problem ids")
    g.add_argument("--contest-id",  type=int, help="Process every problem in this contest")
    g.add_argument("--doctor", action="store_true",
                   help="Diagnose claude/DB/permissions; do not generate anything")
    g.add_argument("--clean-failed", action="store_true",
                   help="Clear failed/queued/generating rows from the DB")
    ap.add_argument("--no-claude", action="store_true",
                    help="Skip the actual claude invocation; mark failed with explanatory message. "
                         "Useful for testing the UI flow without spending API tokens.")
    args = ap.parse_args()
    if args.doctor:
        sys.exit(doctor())
    if args.clean_failed:
        sys.exit(clean_failed())

    if args.contest_id:
        problems = problems_in_contest(args.contest_id)
        if not problems:
            print(f"contest {args.contest_id} has no problems", file=sys.stderr)
            sys.exit(2)
        print(f"contest {args.contest_id}: processing {len(problems)} problem(s) sequentially")
    else:
        ids = [int(s) for s in args.problem_ids.split(",") if s.strip()]
        conn = _conn()
        problems = []
        for pid in ids:
            r = conn.execute(
                """SELECT p.id, p.name, p.url, p.platform,
                          COALESCE(p.contest_name, c.name) AS contest_name,
                          COALESCE(p.contest_year, c.contest_year) AS contest_year,
                          p.problem_index, p.difficulty,
                          c.id AS contest_id, c.tutorial_pdf, c.tutorial_translated
                   FROM problems p
                   LEFT JOIN contest_problems cp ON cp.problem_id = p.id
                   LEFT JOIN contests c          ON c.id          = cp.contest_id
                   WHERE p.id = ?
                   LIMIT 1""",
                (pid,)).fetchone()
            if r:
                problems.append(dict(r))
        conn.close()

    n_ok, n_fail = 0, 0
    for p in problems:
        # Skip if already done — useful for "Generate all missing" on contests
        conn = _conn()
        existing = conn.execute(
            "SELECT status FROM problem_tutorials WHERE problem_id = ?", (p["id"],)
        ).fetchone()
        conn.close()
        if existing and existing["status"] == "done":
            print(f"  problem {p['id']}: already done, skipping")
            continue
        ok = run_one(p, use_claude=not args.no_claude)
        if ok: n_ok += 1
        else:  n_fail += 1

    print(f"\nDone. ok={n_ok} failed={n_fail}")
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    main()
