"""
generate_tutorials.py — batch CLI to manage AI tutorial generation.

Usage
-----
    python3 generate_tutorials.py status                # progress dashboard
    python3 generate_tutorials.py list-pending [--limit N]
    python3 generate_tutorials.py register <slug>       # register an existing
                                                          on-disk tutorial
    python3 generate_tutorials.py register-all          # scan socratic-tutorials/
                                                          and register every slug
    python3 generate_tutorials.py render-pdfs           # (re-)render PDFs for
                                                          every 'done' tutorial
    python3 generate_tutorials.py mark-queued [--filter ...]
                                                        # mark problems as queued
                                                          for the orchestrator

This CLI does NOT itself invoke the Claude pipeline — that runs in Claude Code
via the `cp-tutorial-orchestrator` subagent. The CLI's role is to:
  - tell you which problems still need tutorials (so you can feed batches to
    the orchestrator)
  - register the artifacts the orchestrator wrote, into the DB
  - keep PDFs and DB rows in sync

Typical workflow
----------------
1. Start a Claude Code session at the project root.
2. Run `python3 generate_tutorials.py list-pending --limit 10` to see what's
   next.
3. In Claude Code: "Use cp-tutorial-orchestrator on these 10 problems: <ids>"
4. When the orchestrator finishes, run `python3 generate_tutorials.py
   register-all` to import everything new into the DB and render PDFs.
5. Refresh the web app — those problems now show the AI Tutorial button.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import tutorials as T


def _conn():
    c = sqlite3.connect(T.DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def cmd_status(_args):
    conn = _conn()
    total = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    by_status = {r["s"]: r["n"] for r in conn.execute(
        "SELECT COALESCE(status,'missing') AS s, COUNT(*) AS n "
        "FROM problem_tutorials GROUP BY s"
    )}
    done = by_status.get("done", 0)
    print(f"Problems in bank:        {total}")
    print(f"Tutorials done:          {done}  ({100*done//max(total,1)}%)")
    for k, v in by_status.items():
        if k != "done":
            print(f"  {k:14s}: {v}")
    untracked = total - sum(by_status.values())
    print(f"  not in registry: {untracked}  (no row in problem_tutorials)")


def cmd_list_pending(args):
    conn = _conn()
    pending = T.list_problems_needing_tutorial(conn, limit=args.limit)
    if not pending:
        print("All problems have completed tutorials.")
        return
    for p in pending:
        flag = f"[{p['tutorial_status']}]"
        rating = f"r{p['rating']}" if p['rating'] else "r?"
        print(f"  {p['id']:4d} {flag:13s} {rating:5s} "
              f"{(p['platform'] or '?'):10s} {(p['name'] or '')[:55]}")


def cmd_register(args):
    """Register a single slug folder as a 'done' tutorial in the DB."""
    conn = _conn()
    sd = T.SOCRATIC_DIR / args.slug
    if not (sd / "metadata.json").exists():
        print(f"  metadata.json missing in {sd}", file=sys.stderr)
        sys.exit(2)
    meta = json.loads((sd / "metadata.json").read_text())
    url = (meta.get("problem") or {}).get("url")
    if not url:
        print(f"  metadata.json has no problem.url", file=sys.stderr)
        sys.exit(2)
    row = T.find_problem_by_url(conn, url)
    if not row:
        print(f"  no problem with url={url} in DB; insert it first", file=sys.stderr)
        sys.exit(2)
    pid = row["id"]
    result = T.upsert_tutorial_from_artifacts(conn, pid)
    print(f"  registered: problem_id={pid} slug={result['slug']} "
          f"status={result['status']}")


def cmd_register_all(_args):
    """Scan socratic-tutorials/ and register every folder we recognise."""
    conn = _conn()
    n_ok, n_skip = 0, 0
    for child in sorted(T.SOCRATIC_DIR.iterdir() if T.SOCRATIC_DIR.exists() else []):
        if not child.is_dir():
            continue
        meta = child / "metadata.json"
        if not meta.exists():
            print(f"  skip (no metadata.json): {child.name}")
            n_skip += 1
            continue
        try:
            d = json.loads(meta.read_text())
            url = (d.get("problem") or {}).get("url")
            if not url:
                print(f"  skip (no url in metadata): {child.name}")
                n_skip += 1
                continue
            row = T.find_problem_by_url(conn, url)
            if not row:
                print(f"  skip (problem not in DB): {child.name}  url={url}")
                n_skip += 1
                continue
            T.upsert_tutorial_from_artifacts(conn, row["id"])
            print(f"  registered: id={row['id']:4d} slug={child.name}")
            n_ok += 1
        except Exception as e:
            print(f"  failed: {child.name} — {e}")
            n_skip += 1
    print(f"Done: {n_ok} registered, {n_skip} skipped.")


def cmd_render_pdfs(_args):
    """(Re-)render PDFs for every 'done' tutorial that lacks them, or with
    --force, for all of them."""
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM problem_tutorials WHERE status = 'done'"
    ).fetchall()
    print(f"Rendering PDFs for {len(rows)} done tutorial(s)...")
    for r in rows:
        d = dict(r)
        try:
            sp = T.render_audience_pdf(d, "student")
            tp = T.render_audience_pdf(d, "teacher")
            print(f"  {d['slug']}: student={sp.stat().st_size}B  teacher={tp.stat().st_size}B")
        except Exception as e:
            print(f"  {d['slug']}: PDF render failed — {e}")


def cmd_mark_queued(args):
    """Mark a set of problems as queued so the orchestrator knows to do them."""
    conn = _conn()
    sql = """SELECT p.id, p.url, p.platform, p.name, p.contest_year, p.problem_index, p.difficulty
             FROM problems p
             LEFT JOIN problem_tutorials t ON t.problem_id = p.id
             WHERE COALESCE(t.status, 'missing') = 'missing'"""
    if args.platform:
        sql += f" AND p.platform = '{args.platform.replace(chr(39), '')}'"
    if args.contest_id:
        sql += f" AND EXISTS (SELECT 1 FROM contest_problems cp WHERE cp.problem_id=p.id AND cp.contest_id={int(args.contest_id)})"
    rows = list(conn.execute(sql))
    n = 0
    for r in rows:
        slug = T.slug_for_problem(r)
        conn.execute(
            "INSERT OR IGNORE INTO problem_tutorials (problem_id, slug, status) "
            "VALUES (?, ?, 'queued')",
            (r["id"], slug),
        )
        n += 1
    conn.commit()
    print(f"Queued {n} problem(s) for tutorial generation.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Show progress")

    p_list = sub.add_parser("list-pending", help="List problems still needing tutorials")
    p_list.add_argument("--limit", type=int, default=20)

    p_reg = sub.add_parser("register", help="Register a single slug folder")
    p_reg.add_argument("slug")

    sub.add_parser("register-all", help="Scan socratic-tutorials/ and register all")

    sub.add_parser("render-pdfs", help="(Re-)render PDFs for done tutorials")

    p_q = sub.add_parser("mark-queued", help="Mark problems as queued for orchestrator")
    p_q.add_argument("--platform", help="Filter by platform (e.g. Codeforces)")
    p_q.add_argument("--contest-id", help="Filter by contest id")

    args = ap.parse_args()
    {
        "status":         cmd_status,
        "list-pending":   cmd_list_pending,
        "register":       cmd_register,
        "register-all":   cmd_register_all,
        "render-pdfs":    cmd_render_pdfs,
        "mark-queued":    cmd_mark_queued,
    }[args.cmd](args)


if __name__ == "__main__":
    main()
