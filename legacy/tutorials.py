"""
tutorials.py — Socratic-tutorial registry, renderer, and unlock helpers.

Lives next to app.py; imported by app.py to wire the routes.

Responsibilities
----------------
1. Map a problem's `difficulty` enum to the contestant's time-spent threshold
   (in minutes). The threshold gates the "AI Coach" reveal for contestants.
2. Read tutorial artifacts from `socratic-tutorials/<slug>/` (the markdown +
   metadata.json the agent pipeline writes) and convert to:
     - self-contained HTML (collapsible <details> reveals work natively)
     - flat PDF (reveals are rendered as styled callouts, since PDFs are static)
3. Talk to two DB tables: `problem_tutorials` and `tutorial_unlocks`.
4. Authorize fetches: coaches/admins always allowed; contestants need a
   `tutorial_unlocks` row before they may read the student version.
"""
from __future__ import annotations

import io
import json
import re
import sqlite3
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

import markdown as md_lib

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR             = Path(__file__).resolve().parent
PROJECT_ROOT         = BASE_DIR.parent                              # /World Finals Training/
SOCRATIC_DIR         = PROJECT_ROOT / "socratic-tutorials"
DB_PATH              = BASE_DIR / "problems.db"


# ---------------------------------------------------------------------------
# Difficulty -> time-spent gate (in minutes)
# ---------------------------------------------------------------------------
# DB enum has 6 buckets; the spec called for 5. We interpolate sensibly.
# Easy / Normal / Normal-Hard / Hard / Very Hard / Challenge

TIME_THRESHOLD_MIN = {
    "Easy":         15,
    "Normal":       25,
    "Normal-Hard":  45,
    "Hard":         60,
    "Very Hard":    75,                 # interpolation between Hard and Challenge
    "Challenge":    90,
}
DEFAULT_TIME_THRESHOLD_MIN = 30          # if difficulty is null/unknown


def time_threshold_minutes(difficulty: Optional[str]) -> int:
    if not difficulty:
        return DEFAULT_TIME_THRESHOLD_MIN
    return TIME_THRESHOLD_MIN.get(difficulty, DEFAULT_TIME_THRESHOLD_MIN)


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def slug_for_problem(problem_row) -> str:
    """Build the canonical socratic-tutorials slug for a problem row.

    Format: <platform>-<contest>-<index>-<kebab-name>
    Examples: cf-911d-inversion-counting, atc-abc300-d-three-divisors,
              cses-1085-array-division, ucup-1516-8234-submissions

    URL parsing is opportunistic per platform; if nothing matches we fall
    back to (contest_year, problem_index) from the DB row.
    """
    p = dict(problem_row)
    url = p.get("url") or ""

    # Platform shorthand. URL is authoritative — the DB platform column is
    # sometimes wrong (e.g. UCup imports landed with platform="Codeforces").
    if "cses.fi" in url:
        plat = "CSES"
    elif "ucup.ac" in url or "qoj.ac" in url:
        plat = "UCup"
    elif "atcoder.jp" in url:
        plat = "AtCoder"
    elif "codeforces.com" in url:
        plat = "Codeforces"
    else:
        plat = (p.get("platform") or "Other").strip() or "Other"

    platform_short = {
        "Codeforces": "cf",
        "AtCoder": "atc",
        "CodeChef": "cc",
        "ICPC Archive": "icpc",
        "Kattis": "kattis",
        "UVa": "uva",
        "SPOJ": "spoj",
        "CSES": "cses",
        "UCup": "ucup",
        "Google Code Jam": "gcj",
        "Meta Hacker Cup": "mhc",
        "USACO": "usaco",
        "HackerEarth": "he",
        "Other": "other",
    }.get(plat, "other")

    # Per-platform URL patterns -> contest tag
    contest = ""

    # Codeforces: contest/<id>/problem/<idx>  OR  problemset/problem/<id>/<idx>
    m = re.search(r"codeforces[^/]*/contest/(\d+)/problem/([A-Z0-9]+)", url, re.I)
    if not m:
        m = re.search(r"codeforces[^/]*/problemset/problem/(\d+)/([A-Z0-9]+)", url, re.I)
    if m:
        contest = m.group(1) + (m.group(2) or "").lower()

    # CSES: cses.fi/problemset/task/<id>
    if not contest:
        m = re.search(r"cses\.fi/problemset/task/(\d+)", url)
        if m:
            contest = m.group(1)

    # AtCoder: atcoder.jp/contests/<contest>/tasks/<contest>_<idx>
    if not contest:
        m = re.search(r"atcoder\.jp/contests/([a-z0-9_]+)/tasks/([a-z0-9_]+)", url, re.I)
        if m:
            contest = m.group(1) + "-" + m.group(2).split("_")[-1]

    # Universal Cup / QOJ: contest.ucup.ac/contest/<cid>/problem/<pid>
    if not contest:
        m = re.search(r"(?:ucup|qoj)\.ac/contest/(\d+)/problem/(\d+)", url)
        if m:
            contest = m.group(1) + "-" + m.group(2)

    # Fall-back: <year>-<index> from the DB row
    if not contest:
        contest = f"{p.get('contest_year') or ''}-{(p.get('problem_index') or '').lower()}"
        contest = contest.strip("-")

    name_kebab = re.sub(r"[^a-z0-9]+", "-", (p.get("name") or "").lower()).strip("-")
    pieces = [platform_short, contest, name_kebab]
    return "-".join(s for s in pieces if s)


def slug_dir(slug: str) -> Path:
    return SOCRATIC_DIR / slug


def normalize_problem_url(url: str) -> list[str]:
    """Return all equivalent forms of a problem URL we'd accept as a match.
    Codeforces has at least three URL forms for the same problem:
      https://codeforces.com/problemset/problem/911/D
      https://codeforces.com/contest/911/problem/D
      https://codeforces.com/contests/911/problem/D
    We return all forms so the registrar can match either way."""
    if not url:
        return []
    forms = {url.strip()}
    # CF: problemset/problem/<C>/<I>  <->  contest/<C>/problem/<I>
    import re as _re
    m = _re.match(r"(https?://[^/]*codeforces[^/]*)/problemset/problem/(\d+)/([A-Z0-9]+)", url)
    if m:
        forms.add(f"{m.group(1)}/contest/{m.group(2)}/problem/{m.group(3)}")
        forms.add(f"{m.group(1)}/contests/{m.group(2)}/problem/{m.group(3)}")
    m = _re.match(r"(https?://[^/]*codeforces[^/]*)/contests?/(\d+)/problem/([A-Z0-9]+)", url)
    if m:
        forms.add(f"{m.group(1)}/problemset/problem/{m.group(2)}/{m.group(3)}")
        # also the other contest/contests variant
        forms.add(f"{m.group(1)}/contest/{m.group(2)}/problem/{m.group(3)}")
        forms.add(f"{m.group(1)}/contests/{m.group(2)}/problem/{m.group(3)}")
    return sorted(forms)


def find_problem_by_url(conn: sqlite3.Connection, url: str):
    """Try every equivalent URL form to find the problem row."""
    for form in normalize_problem_url(url):
        row = conn.execute("SELECT id, name FROM problems WHERE url = ?",
                           (form,)).fetchone()
        if row:
            return row
    return None


# ---------------------------------------------------------------------------
# Markdown -> HTML
# ---------------------------------------------------------------------------

_HTML_CSS = """
<style>
:root {
  --bg: #0e1116; --panel: #161b22; --panel-2: #1c232c; --border: #2a323d;
  --text: #e6edf3; --muted: #8b96a3; --accent: #5ea1ff; --green: #3fb950;
  --amber: #d29922; --red: #f85149;
  --hint-bg: rgba(210, 153, 34, 0.10); --hint-border: var(--amber);
  --answer-bg: rgba(63, 185, 80, 0.10); --answer-border: var(--green);
  --reveal-bg: rgba(94, 161, 255, 0.10); --reveal-border: var(--accent);
}
body {
  margin: 0; padding: 32px 36px; max-width: 920px; margin-inline: auto;
  background: var(--bg); color: var(--text);
  font: 15px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
}
h1 { font-size: 26px; margin: 0 0 14px; }
h2 { font-size: 19px; margin: 30px 0 10px; padding-bottom: 6px; border-bottom: 1px solid var(--border); }
h3 { font-size: 16px; margin: 22px 0 8px; color: var(--accent); }
h4 { font-size: 14px; margin: 18px 0 6px; color: var(--amber); }
p, li { color: var(--text); }
blockquote {
  margin: 14px 0; padding: 10px 14px; background: var(--panel-2);
  border-left: 3px solid var(--accent); color: var(--text); font-size: 14px;
}
code { background: var(--panel-2); padding: 2px 6px; border-radius: 4px; font-size: 13.5px; }
pre {
  background: var(--panel); border: 1px solid var(--border); border-radius: 6px;
  padding: 14px 16px; overflow-x: auto; font-size: 13px;
}
pre code { background: transparent; padding: 0; }
a { color: var(--accent); }
hr { border: none; border-top: 1px solid var(--border); margin: 22px 0; }

/* Collapsible reveal blocks (interactive) */
details {
  background: var(--reveal-bg); border: 1px solid var(--reveal-border);
  border-radius: 6px; padding: 8px 14px; margin: 10px 0;
}
details > summary {
  cursor: pointer; font-weight: 600; color: var(--accent);
  padding: 2px 0; user-select: none;
}
details[open] > summary { margin-bottom: 8px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
details > *:not(summary) { margin-top: 6px; }

/* Hint blocks (yellowish) and Answer blocks (greenish) */
details:has(> summary:contains("Hint")) { background: var(--hint-bg); border-color: var(--hint-border); }
details:has(> summary:contains("Hint")) > summary { color: var(--amber); }
details:has(> summary:contains("Answer")) { background: var(--answer-bg); border-color: var(--answer-border); }
details:has(> summary:contains("Answer")) > summary { color: var(--green); }

/* Tables */
table { border-collapse: collapse; margin: 12px 0; }
th, td { border: 1px solid var(--border); padding: 6px 10px; }
th { background: var(--panel-2); }

/* Banner / at-a-glance callouts */
blockquote strong { color: var(--accent); }

/* Audience banner (the first blockquote at the top) */
body > blockquote:first-of-type { border-left-color: var(--green); background: var(--panel-2); }

/* Print / PDF tweaks: flatten reveals so all content is visible */
@media print {
  body { background: white; color: #1a1a1a; }
  details { background: rgba(210, 153, 34, 0.08) !important; border-color: #d29922 !important; padding: 8px 14px; }
  details > summary { list-style: none; cursor: default; }
  details > summary::-webkit-details-marker { display: none; }
  details::before { display: none; }
  details > *:not(summary) { margin-top: 6px; }
  pre { white-space: pre-wrap; word-wrap: break-word; }
  a { color: #1a73e8; }
}
</style>
"""

_HTML_HEAD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{css}
</head>
<body>
{body}
<script>
// Open all <details> when printing (so PDF is complete) and restore after.
window.addEventListener('beforeprint', () => {{
  document.querySelectorAll('details').forEach(d => {{ d.dataset.wasOpen = d.open ? '1' : '0'; d.open = true; }});
}});
window.addEventListener('afterprint', () => {{
  document.querySelectorAll('details').forEach(d => {{ d.open = (d.dataset.wasOpen === '1'); }});
}});
</script>
</body></html>
"""




# ---------------------------------------------------------------------------
# Markdown preprocess — fix common authoring patterns that don't render cleanly
# ---------------------------------------------------------------------------
# Python-Markdown treats content inside HTML block elements (like <details>)
# as raw HTML by default, which means **bold** and ## heading inside a
# <details> render as literal asterisks/hashes. Adding markdown="1" lets
# the inner content be parsed. We also need blank lines around inline markdown
# for block-level constructs (lists, code fences) to work inside <details>.

_DETAILS_OPEN_RE  = re.compile(r"<details(?![^>]*\bmarkdown=)([^>]*)>", re.I)
_SUMMARY_OPEN_RE  = re.compile(r"<summary(?![^>]*\bmarkdown=)([^>]*)>", re.I)


_FENCE_RE = re.compile(r"^(```)(\w*)\s*$")


def _retag_opening_fences(text: str) -> str:
    """Add a language tag to OPENING code fences that don't have one. Walks
    line by line and tracks inside/outside state so closing fences stay bare."""
    out = []
    inside = False
    for line in text.split("\n"):
        m = _FENCE_RE.match(line)
        if m:
            if not inside:
                # opening fence
                if not m.group(2):
                    out.append("```text")
                else:
                    out.append(line)
                inside = True
            else:
                # closing fence — always emit bare
                out.append("```")
                inside = False
        else:
            out.append(line)
    return "\n".join(out)


def restore_broken_closing_fences(text: str) -> str:
    """One-shot fixer for files damaged by the previous broken regex. The
    bug rewrote every closing ``` to ```text. We can detect & undo this by
    walking with a state machine that knows the FIRST fence is the opener,
    so any ```text in a closing position becomes ```."""
    out = []
    inside = False
    for line in text.split("\n"):
        m = _FENCE_RE.match(line)
        if m:
            if not inside:
                # opening fence — keep whatever language is there
                out.append(line)
                inside = True
            else:
                # closing fence — always make bare regardless of what's there
                out.append("```")
                inside = False
        else:
            out.append(line)
    return "\n".join(out)


def humanize_markdown(md_text: str) -> str:
    """Mechanical preprocessing applied before EVERY render. Idempotent.

    What it fixes:
      1. Adds markdown="1" to <details> and <summary> so nested **bold**,
         `code`, ## heading, and lists actually parse.
      2. Adds a blank line right after every <details ...> opening tag
         and before every </details> so block-level markdown can recognise
         block boundaries inside the reveal.
      3. Tags bare code fences (```\n...```) with a sensible default language
         so codehilite has something to highlight.
      4. Normalises stray double-newlines that AI agents sometimes emit
         after headings (3+ newlines collapse to 2).
    """
    s = md_text

    # 1. Add markdown="1" to <details> and <summary> when missing.
    s = _DETAILS_OPEN_RE.sub(r'<details markdown="1"\1>', s)
    s = _SUMMARY_OPEN_RE.sub(r'<summary markdown="span"\1>', s)

    # 2. Force blank lines around <details> internals so block-level markdown
    #    inside the reveal renders. We split to avoid breaking <details> that
    #    are intentionally on one line.
    def open_tag_newline(match):
        return match.group(0) + "\n\n"
    s = re.sub(r"(<details\s[^>]*markdown=\"1\"[^>]*>)(?!\n)", open_tag_newline, s)
    s = re.sub(r"(?<!\n)\n?(</details>)", r"\n\n\1", s)

    # 3. Tag bare opening fences with a language. Walk lines; track whether
    #    we're inside a code block. ONLY opening fences without a language
    #    get tagged — closing fences stay bare. (The previous regex tagged
    #    every bare fence, including closers, which broke every code block.)
    s = _retag_opening_fences(s)

    # 4. Collapse runs of 3+ newlines to 2 (markdown only needs one blank line)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s


def render_markdown_to_html(md_text: str, title: str = "Tutorial") -> str:
    """Convert tutorial markdown to a self-contained dark-themed HTML page.

    Runs humanize_markdown() first to fix <details>/code-fence patterns that
    AI agents commonly emit but that don't render cleanly. Code fences get
    pygments syntax highlighting via codehilite.
    """
    md_text = humanize_markdown(md_text)
    md = md_lib.Markdown(
        extensions=[
            "fenced_code",
            "tables",
            "toc",
            "codehilite",
            "attr_list",
            "md_in_html",
        ],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": True, "pygments_style": "monokai"},
        },
        output_format="html5",
    )
    body_html = md.convert(md_text)
    return _HTML_HEAD.format(title=title, css=_HTML_CSS, body=body_html)


# ---------------------------------------------------------------------------
# HTML -> PDF (flat: <details> rendered fully expanded, no interactivity)
# ---------------------------------------------------------------------------

def render_html_to_pdf(html: str, out_path: Path) -> Path:
    """Render the HTML to PDF using weasyprint. <details> get force-opened
    via inline CSS so all content is visible in the static PDF."""
    # Force-open details by inlining `details { open: true }` is not a CSS
    # property, but `details > *:not(summary) { display: block !important }`
    # with `summary::before` showing an arrow does the visual job. The cleanest
    # path is to manipulate the DOM-string before handing to weasyprint.
    flat_html = html.replace("<details>", "<details open>").replace(
        "<details ", "<details open "
    )
    # Remove the print/screen toggling JS — weasyprint ignores JS anyway.
    from weasyprint import HTML  # imported lazily so app.py boot stays cheap
    HTML(string=flat_html).write_pdf(target=str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# DB helpers (used by app.py)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# publish_versions — deterministic Python replacement for cp-version-publisher
# ---------------------------------------------------------------------------
# Splits the consolidated tutorial.md into student/teacher audience versions
# without an LLM call. Same transformations the agent did, but predictable
# and idempotent. ~1 min faster + no LLM tokens.

def publish_versions(slug: str) -> dict:
    """Read socratic-tutorials/<slug>/tutorial.md and write tutorial.student.md,
    tutorial.teacher.md, and update metadata.json with versions/served_to.
    Returns a small report dict for the worker log."""
    sd = SOCRATIC_DIR / slug
    src_path  = sd / "tutorial.md"
    meta_path = sd / "metadata.json"
    if not src_path.exists() or not meta_path.exists():
        return {"ok": False, "error": f"missing tutorial.md or metadata.json in {sd}"}

    src  = src_path.read_text()
    meta = json.loads(meta_path.read_text())

    # ============================================================
    # STUDENT VERSION
    # ============================================================
    student = src

    # 1. Strip §11 "If you're teaching this" through the next horizontal rule
    student = re.sub(
        r"## 11\. If you'?re teaching this.*?(?=\n---\n|\Z)",
        "",
        student,
        flags=re.S,
    )
    # 2. Strip the editorial-decisions HTML comment block
    student = re.sub(
        r"<!--\s*EDITORIAL DECISIONS LOG.*?-->\s*",
        "",
        student,
        flags=re.S,
    )

    # 3. Wrap §6 algorithm pseudocode in <details>
    m6 = re.search(r"(## 6\. The full algorithm\n+)(.*?)(\n## 7\. Solution code)", student, re.S)
    if m6:
        new_block = (m6.group(1)
                     + "_You should be able to assemble this from your answers above. "
                       "Open the block to check, not to substitute for working through the ladder._\n\n"
                     + "<details markdown=\"1\"><summary markdown=\"span\">Show me the full algorithm pseudocode</summary>\n\n"
                     + m6.group(2).strip()
                     + "\n\n</details>\n"
                     + m6.group(3))
        student = student[:m6.start()] + new_block + student[m6.end():]

    # 4. Wrap C++ and Python solution blocks in collapsible <details>
    for lang_label, lang_re, summary in [
        ("cpp",    r"(### C\+\+ \(canonical[^)]*\)\n\n)(```cpp\n.*?\n```)",
                   "Reveal C++ solution (write your own first)"),
        ("python", r"(### Python \(readability[^)]*\)\n\n)(```python\n.*?\n```)",
                   "Reveal Python solution (compare to your own)"),
    ]:
        mm = re.search(lang_re, student, re.S)
        if mm:
            wrapped = (mm.group(1)
                       + f"<details markdown=\"1\"><summary markdown=\"span\">{summary}</summary>\n\n"
                       + mm.group(2)
                       + "\n\n</details>")
            student = student.replace(mm.group(0), wrapped)

    # 5. Add §7 preamble warning students against shortcutting
    if "## 7. Solution code" in student and "Write your own solution first" not in student:
        student = student.replace(
            "## 7. Solution code\n\n### C++",
            "## 7. Solution code\n\n_Write your own solution first. The reveals below exist for "
            "comparison and debugging — using them as a substitute for the ladder is the fastest "
            "way to plateau._\n\n### C++"
        )

    # 6. Add §3 nudge
    if "## 3. The Socratic ladder" in student and "earn the next idea" not in student:
        student = student.replace(
            "## 3. The Socratic ladder\n\n### Q1.",
            "## 3. The Socratic ladder\n\n_Try each question yourself before opening the hint or "
            "answer. The point is to earn the next idea, not to read the answer key._\n\n### Q1."
        )

    # 7. Top banner (only if not already added by an earlier publisher run)
    if "This is the student / contestant view" not in student:
        problem_name = meta.get("problem", {}).get("name") or "Tutorial"
        banner = (
            "> _**This is the student / contestant view.** Hints, answers, MCQ keys, "
            "snippet fills, and the full solution are hidden by default — click each "
            "▶ to reveal. The point is to earn the next idea, not to read the answer key._\n\n---\n\n"
        )
        # Insert banner immediately after the first line (the # title)
        student = re.sub(
            r"(^# [^\n]+\n)(?=\n*> _\*\*Topic|\n*## 1\.|\n*\n)",
            r"\1\n" + banner,
            student,
            count=1,
            flags=re.M,
        )

    # 8. Footer
    if "earn the ladder" not in student and "one rung at a time" not in student:
        student = student.rstrip() + (
            "\n\n---\n\n_Stuck? Open the hint, then the answer, one rung at a time. "
            "If a hint isn't enough, open the answer — that's how the ladder is meant to be used. "
            "If a whole rung loses you, that's signal: bring it to your team's "
            "problem-discussion session._\n"
        )

    # ============================================================
    # TEACHER VERSION
    # ============================================================
    teacher = src

    # 1. Top banner
    if "This is the coach / admin view" not in teacher:
        banner_t = (
            "> _**This is the coach / admin view.** Every hint, answer, key, and "
            "solution is shown inline. The student version (`tutorial.student.md`) is "
            "also published — open it to preview what your team will see when they "
            "click \"AI Coach\"._\n\n"
        )
        teacher = re.sub(
            r"(^# [^\n]+\n)(?=\n*> _\*\*Topic|\n*## 1\.|\n*\n)",
            r"\1\n" + banner_t,
            teacher,
            count=1,
            flags=re.M,
        )

    # 2. "At a glance" callout from metadata
    if "At a glance" not in teacher:
        problem = meta.get("problem", {})
        prereqs = ", ".join(problem.get("prerequisites", []) or []) or "n/a"
        plan = meta.get("teach_plan", {})
        total = sum(plan.get(k, 0) for k in ("hook_min", "buildup_min", "code_min", "variations_min"))
        edge_first = (meta.get("edge_cases") or ["n/a"])[0]
        callout = (
            "> **At a glance**\n"
            f"> - **Key insight:** {meta.get('key_insight', 'n/a')}\n"
            f"> - **Session length:** {total} minutes\n"
            f"> - **Prerequisites worth re-checking:** {prereqs}\n"
            f"> - **First edge case to hand-trace:** {edge_first}\n\n"
        )
        # Insert callout after the banner blockquote
        teacher = re.sub(
            r"(> _\*\*This is the coach / admin view\.\*\*[^\n]+_\n\n)",
            r"\1" + callout,
            teacher,
            count=1,
        )

    (sd / "tutorial.student.md").write_text(student)
    (sd / "tutorial.teacher.md").write_text(teacher)

    # Update metadata
    meta.setdefault("versions", {})
    meta["versions"]["student"] = "tutorial.student.md"
    meta["versions"]["teacher"] = "tutorial.teacher.md"
    meta["versions"]["source_of_truth"] = "tutorial.md"
    meta.setdefault("served_to", {})
    meta["served_to"].setdefault("Contestant", "student")
    meta["served_to"].setdefault("Coach",      "teacher")
    meta["served_to"].setdefault("Admin",      "teacher")
    meta_path.write_text(json.dumps(meta, indent=2))

    return {
        "ok": True,
        "student_md_lines": len(student.splitlines()),
        "teacher_md_lines": len(teacher.splitlines()),
    }


def get_tutorial_row(conn: sqlite3.Connection, problem_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM problem_tutorials WHERE problem_id = ?", (problem_id,)
    ).fetchone()
    return dict(row) if row else None


def upsert_tutorial_from_artifacts(conn: sqlite3.Connection, problem_id: int) -> dict:
    """Inspect socratic-tutorials/<slug>/ on disk and write a problem_tutorials
    row that mirrors what's there. Idempotent. Returns the row dict."""
    p = conn.execute(
        "SELECT id, name, url, platform, contest_name, contest_year, "
        "       problem_index, difficulty FROM problems WHERE id = ?",
        (problem_id,),
    ).fetchone()
    if not p:
        raise ValueError(f"problem id {problem_id} not found")
    slug = slug_for_problem(p)
    sd = slug_dir(slug)

    student_md = sd / "tutorial.student.md"
    teacher_md = sd / "tutorial.teacher.md"
    student_pdf = sd / "tutorial.student.pdf"
    teacher_pdf = sd / "tutorial.teacher.pdf"
    meta_path  = sd / "metadata.json"

    if not (student_md.exists() and teacher_md.exists() and meta_path.exists()):
        # mark queued so the batch generator picks it up
        conn.execute(
            "INSERT INTO problem_tutorials (problem_id, slug, status) "
            "VALUES (?, ?, 'queued') "
            "ON CONFLICT(problem_id) DO UPDATE SET slug = excluded.slug, "
            "status = CASE WHEN problem_tutorials.status IN ('done','generating') "
            "              THEN problem_tutorials.status ELSE 'queued' END",
            (problem_id, slug),
        )
        conn.commit()
        return get_tutorial_row(conn, problem_id) or {}

    meta = json.loads(meta_path.read_text())
    rel = lambda path: str(path.relative_to(PROJECT_ROOT))
    conn.execute(
        """INSERT INTO problem_tutorials
           (problem_id, slug, status, generated_at, generator_version,
            student_md_path, teacher_md_path,
            student_pdf_path, teacher_pdf_path,
            key_insight, rung_count, mcq_count, snippet_count,
            editorial_found, research_confidence)
           VALUES (?, ?, 'done', ?, 'v1',
                   ?, ?,
                   ?, ?,
                   ?, ?, ?, ?,
                   ?, ?)
           ON CONFLICT(problem_id) DO UPDATE SET
             slug = excluded.slug,
             status = 'done',
             generated_at = excluded.generated_at,
             generator_version = excluded.generator_version,
             student_md_path = excluded.student_md_path,
             teacher_md_path = excluded.teacher_md_path,
             student_pdf_path = excluded.student_pdf_path,
             teacher_pdf_path = excluded.teacher_pdf_path,
             key_insight = excluded.key_insight,
             rung_count = excluded.rung_count,
             mcq_count = excluded.mcq_count,
             snippet_count = excluded.snippet_count,
             editorial_found = excluded.editorial_found,
             research_confidence = excluded.research_confidence,
             error_message = NULL""",
        (
            problem_id, slug, datetime.utcnow().isoformat(timespec="seconds") + "Z",
            rel(student_md), rel(teacher_md),
            rel(student_pdf) if student_pdf.exists() else None,
            rel(teacher_pdf) if teacher_pdf.exists() else None,
            meta.get("key_insight"),
            len(meta.get("ladder", [])),
            len(meta.get("mcqs", [])),
            len(meta.get("snippets", [])),
            1 if meta.get("editorial_found") else 0,
            meta.get("research_confidence"),
        ),
    )
    conn.commit()
    return get_tutorial_row(conn, problem_id) or {}


def has_unlocked(conn: sqlite3.Connection, user_id: int, problem_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM tutorial_unlocks WHERE user_id = ? AND problem_id = ?",
        (user_id, problem_id),
    ).fetchone()
    return row is not None


def record_unlock(conn: sqlite3.Connection, user_id: int, problem_id: int,
                  claimed_minutes: int, threshold_minutes: int) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO tutorial_unlocks "
        "(user_id, problem_id, claimed_minutes, threshold_minutes) "
        "VALUES (?, ?, ?, ?)",
        (user_id, problem_id, claimed_minutes, threshold_minutes),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Render-on-demand & cache
# ---------------------------------------------------------------------------

def _read_md(rel_path: str) -> str:
    return (PROJECT_ROOT / rel_path).read_text(encoding="utf-8")


def render_audience_html(tutorial: dict, audience: str) -> str:
    """audience = 'student' | 'teacher'. Returns a self-contained HTML string."""
    if audience not in ("student", "teacher"):
        raise ValueError(f"unknown audience: {audience}")
    path_field = "student_md_path" if audience == "student" else "teacher_md_path"
    md_path = tutorial.get(path_field)
    if not md_path:
        raise FileNotFoundError(f"no {audience} md_path on tutorial row")
    md_text = _read_md(md_path)
    title = f"{audience.title()} Tutorial — {tutorial.get('slug')}"
    return render_markdown_to_html(md_text, title=title)


def render_audience_pdf(tutorial: dict, audience: str, force: bool = False) -> Path:
    """Render the PDF for an audience, caching at tutorial.<audience>.pdf in
    the slug directory. Returns the absolute path."""
    if audience not in ("student", "teacher"):
        raise ValueError(f"unknown audience: {audience}")
    slug = tutorial["slug"]
    sd = slug_dir(slug)
    out = sd / f"tutorial.{audience}.pdf"
    if out.exists() and not force:
        return out
    html = render_audience_html(tutorial, audience)
    return render_html_to_pdf(html, out)


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------

def list_problems_needing_tutorial(conn: sqlite3.Connection,
                                   limit: Optional[int] = None) -> list[dict]:
    """Returns problems that don't yet have a 'done' tutorial row."""
    sql = """
        SELECT p.id, p.name, p.url, p.platform, p.contest_name, p.contest_year,
               p.problem_index, p.rating, p.difficulty, p.topic, p.importance,
               COALESCE(t.status, 'missing') AS tutorial_status
        FROM problems p
        LEFT JOIN problem_tutorials t ON t.problem_id = p.id
        WHERE COALESCE(t.status, 'missing') != 'done'
        ORDER BY (p.importance = 'Critical') DESC,
                 (p.importance = 'High')     DESC,
                 p.rating
    """
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [dict(r) for r in conn.execute(sql).fetchall()]
