"""
HEAD/GET each practice URL in the merged v3 set and tag rows with the result.
Rows that come back 4xx / 5xx / connection-error get `practice_status` = "broken"
and are dropped when we rebuild the v4 sheet.

Usage (local — sandbox can't reach codeforces / acmicpc / vjudge):
    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 check_practice_urls.py

Outputs:
    ../ucup_plus_icpc_archive_v3_checked.json
"""
from __future__ import annotations
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
IN_PATH  = PROJECT_DIR / "ucup_plus_icpc_archive_v3.json"
OUT_PATH = PROJECT_DIR / "ucup_plus_icpc_archive_v3_checked.json"

# Pretend to be a recent Chrome — Codeforces & some Korean sites filter generic UAs.
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
ACCEPT_HDRS = {
    "User-Agent":      UA,
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ko;q=0.6",
    "Accept-Encoding": "identity",   # avoid decompression headaches
}
TIMEOUT = 15


def _fetch_body(url: str, max_bytes: int = 80_000):
    req = urllib.request.Request(url, headers=ACCEPT_HDRS)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.status, resp.read(max_bytes).decode("utf-8", errors="ignore")


def _is_acmicpc_usable(body: str) -> bool:
    """A BOJ /category/detail page is 'deployable' only if it lists problems
    and offers a virtual-contest button.  Empty / problem-less category pages
    return 200 OK but are useless to coaches.

    We accept a page if either:
        - it has at least one /problem/<num> link, OR
        - it contains Korean/English markers for a virtual contest button.
    """
    if not body:
        return False
    if 'href="/problem/' in body:
        return True
    if "가상 대회" in body or "virtual contest" in body.lower() or "virtual" in body.lower() and "contest" in body.lower():
        return True
    return False


def check(url: str):
    """Return (status_str, http_code).  status_str ∈ {ok, broken, error}."""
    host = (urllib.parse.urlparse(url).hostname or "").lower()

    # Codeforces blocks HEAD with 403 from non-browser UAs even on real pages —
    # we always trust gym/contest URLs and don't mark them as broken.
    if "codeforces.com" in host:
        try:
            code, _ = _fetch_body(url, max_bytes=2048)
            return (("ok" if 200 <= code < 400 else "broken"), code)
        except urllib.error.HTTPError as e:
            # 403 here is the well-known anti-bot rejection — treat as ok.
            if e.code == 403:
                return ("ok", 403)
            return ("broken", e.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            return ("error", None)

    # acmicpc.net category pages need a body sniff to confirm they're a usable
    # category (problem links / virtual-contest button present).
    if host.endswith("acmicpc.net") and "/category/detail/" in url:
        try:
            code, body = _fetch_body(url)
            if not (200 <= code < 400):
                return ("broken", code)
            return (("ok" if _is_acmicpc_usable(body) else "broken"), code)
        except urllib.error.HTTPError as e:
            return ("broken", e.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            return ("error", None)

    # Default path — HEAD with GET fallback.
    try:
        req = urllib.request.Request(url, method="HEAD", headers=ACCEPT_HDRS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            code = resp.status
        if 200 <= code < 400:
            return ("ok", code)
        return ("broken", code)
    except urllib.error.HTTPError as e:
        if e.code in (405, 403, 501):
            try:
                code, _ = _fetch_body(url, max_bytes=512)
                return (("ok" if 200 <= code < 400 else "broken"), code)
            except urllib.error.HTTPError as e2:
                return ("broken", e2.code)
            except (urllib.error.URLError, TimeoutError, OSError):
                return ("error", None)
        return ("broken", e.code)
    except (urllib.error.URLError, TimeoutError, OSError):
        return ("error", None)


def main():
    if not IN_PATH.exists():
        print(f"!! input not found: {IN_PATH}")
        sys.exit(1)
    rows = json.loads(IN_PATH.read_text())
    targets = [(i, r["practice_url"]) for i, r in enumerate(rows) if r.get("practice_url")]
    print(f"[in]  {len(rows)} rows ({len(targets)} have practice URLs)")

    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(check, url): (i, url) for i, url in targets}
        for n, fut in enumerate(as_completed(futures), start=1):
            i, url = futures[fut]
            status, code = fut.result()
            results[i] = (status, code)
            if n % 25 == 0:
                print(f"  [{n}/{len(targets)}] checked")

    # Annotate rows
    counts = {"ok": 0, "broken": 0, "error": 0}
    for i, r in enumerate(rows):
        if i in results:
            r["practice_status"], r["practice_http_code"] = results[i]
            counts[r["practice_status"]] += 1
        else:
            r["practice_status"] = None
            r["practice_http_code"] = None

    OUT_PATH.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
    print()
    print(f"[out] wrote {OUT_PATH}")
    print(f"      ok:     {counts['ok']}")
    print(f"      broken: {counts['broken']}")
    print(f"      error:  {counts['error']}")
    print()
    print("Tell me to rebuild the v4 sheet that drops the broken/error rows.")


if __name__ == "__main__":
    main()
