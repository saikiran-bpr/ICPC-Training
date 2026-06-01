"""
For every contest in contests_v5.json with a tutorial PDF link:
  1. Download the PDF to  ../tutorials/<slug>/tutorial.<lang>.pdf
  2. If the language is not English, extract text with pdfplumber,
     translate page-by-page with deep-translator (Google), and save a
     readable markdown copy alongside it.
  3. Augment the JSON with the local file paths and write contests_v6.json.

Idempotent — re-running skips work for files that already exist.

Usage (local machine — sandbox can't reach codeforces / contest.ucup.ac):

    cd "/Users/dgour/Desktop/Claude/Projects/World Finals Training/problem-repository"
    .venv/bin/python3 -m pip install --upgrade pdfplumber deep-translator
    .venv/bin/python3 download_translate_tutorials.py

The script tolerates missing optional deps:
  - pdfplumber missing  →  PDFs are downloaded but not text-extracted
  - deep-translator missing → text is extracted but not translated
"""
from __future__ import annotations
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

REPO_DIR    = Path(__file__).resolve().parent
PROJECT_DIR = REPO_DIR.parent
IN_PATH   = PROJECT_DIR / "contests_v5.json"
OUT_PATH  = PROJECT_DIR / "contests_v6.json"
TUTS_DIR  = PROJECT_DIR / "tutorials"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
TIMEOUT = 30

# Optional deps — don't crash if missing.
try:
    import pdfplumber
except Exception:
    pdfplumber = None
    print("[note] pdfplumber not installed — text extraction will be skipped.")
try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None
    print("[note] deep-translator not installed — translation will be skipped.")


# ---------------------------------------------------------------------------
def slugify(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "contest"


def _safe_url(url: str) -> str:
    """URL-encode the path so spaces / non-ASCII don't break urllib."""
    parts = urllib.parse.urlsplit(url)
    safe_path = urllib.parse.quote(parts.path, safe="/()&:")
    safe_query = urllib.parse.quote(parts.query, safe="=&?:")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, safe_path, safe_query, parts.fragment))


def fetch_bytes(url: str, retries: int = 2) -> Optional[bytes]:
    safe = _safe_url(url)
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(safe, headers=HDRS)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            print(f"   !! download failed for {url}: {e}", file=sys.stderr)
            return None


def extract_text(pdf_path: Path) -> Optional[str]:
    if not pdfplumber:
        return None
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            chunks = []
            for i, page in enumerate(pdf.pages, start=1):
                try:
                    txt = page.extract_text() or ""
                except Exception as e:
                    txt = f"[page {i} extract error: {e}]"
                chunks.append(f"# Page {i}\n\n{txt.strip()}")
            return "\n\n".join(chunks)
    except Exception as e:
        print(f"   !! pdf parse error: {e}", file=sys.stderr)
        return None


def _split_into_chunks(text: str, chunk_size: int):
    """Pack text into ≤chunk_size strings, splitting on newlines first, then
    sentences, then characters as a last resort."""
    parts, buf, cur = [], [], 0
    for line in text.split("\n"):
        # If a single line is itself oversized, hard-split it
        while len(line) > chunk_size:
            head, line = line[:chunk_size], line[chunk_size:]
            if buf:
                parts.append("\n".join(buf)); buf, cur = [], 0
            parts.append(head)
        if cur + len(line) + 1 > chunk_size and buf:
            parts.append("\n".join(buf)); buf, cur = [], 0
        buf.append(line); cur += len(line) + 1
    if buf:
        parts.append("\n".join(buf))
    return parts


def _google_one(part: str, src_lang: str) -> Optional[str]:
    if not GoogleTranslator:
        return None
    try:
        return GoogleTranslator(source=src_lang, target="en").translate(part)
    except Exception:
        return None


def _mymemory_one(part: str, src_lang: str) -> Optional[str]:
    """MyMemory's free endpoint accepts ≤500 chars per request — the caller
    must pre-chunk to that size."""
    try:
        from deep_translator import MyMemoryTranslator
    except Exception:
        return None
    src = src_lang
    if src == "auto" or not src:
        src = "zh-CN"  # most common in our data
    elif "-" not in src and src.lower() != "auto":
        # MyMemory wants region codes; uppercase for known ones
        src = src.upper() if src.lower() in {"zh", "ja", "ko", "ru", "fr", "de", "es", "pt"} else src
    try:
        return MyMemoryTranslator(source=src, target="en-GB").translate(part)
    except Exception:
        return None


def translate_text(text: str, src_lang: str = "auto") -> Tuple[Optional[str], int, int]:
    """Try Google first (chunks ≤4500), fall back to MyMemory (chunks ≤450)
    per chunk. Returns (translated_or_None, ok_chunks, total_chunks)."""
    if not text:
        return None, 0, 0
    if not GoogleTranslator:
        return None, 0, 0

    parts = _split_into_chunks(text, 4500)
    out, ok = [], 0
    for i, part in enumerate(parts, start=1):
        # Google
        r = _google_one(part, src_lang)
        if r:
            out.append(r); ok += 1
            time.sleep(0.4)
            continue

        # Fall back to MyMemory — re-chunk this part into ≤450-char pieces
        sub_parts = _split_into_chunks(part, 450)
        sub_out, sub_ok = [], 0
        for j, sub in enumerate(sub_parts, start=1):
            r2 = _mymemory_one(sub, src_lang)
            if r2:
                sub_out.append(r2); sub_ok += 1
            else:
                sub_out.append(sub)   # keep original
            time.sleep(0.25)

        if sub_ok == len(sub_parts):
            out.append("\n".join(sub_out)); ok += 1
        else:
            # Mark as partial — MyMemory got some but not all sub-chunks
            out.append(
                f"[partial translation — {sub_ok}/{len(sub_parts)} sub-chunks via MyMemory; "
                f"untranslated segments kept as-is]\n\n" + "\n".join(sub_out)
            )
        print(f"   .. chunk {i}/{len(parts)}: google=fail, mymemory={sub_ok}/{len(sub_parts)}")
    return "\n\n".join(out), ok, len(parts)


# ---------------------------------------------------------------------------
def main():
    if not IN_PATH.exists():
        print(f"!! input not found: {IN_PATH}")
        sys.exit(1)
    rows = json.loads(IN_PATH.read_text())
    TUTS_DIR.mkdir(exist_ok=True)
    print(f"[in] {len(rows)} rows from {IN_PATH.name}")
    print(f"[out] tutorials/ → {TUTS_DIR}")

    new_rows = []
    for i, r in enumerate(rows, start=1):
        # Resolve tutorial URL + language (mirror of build_v5 logic)
        pdf_url = None
        lang    = (r.get("tutorial_lang") or "").lower() or None
        if r.get("tutorial_lang"):
            m = re.search(r"contest\.ucup\.ac/contest/(\d+)", r.get("ucup_url") or "")
            if m:
                pdf_url = f"https://contest.ucup.ac/download.php?type=attachments&id={m.group(1)}&r=1"
        if not pdf_url and r.get("solution_pdf"):
            pdf_url = r["solution_pdf"]
            if not lang:
                lang = "en"

        slug = slugify((r.get("primary") or "")[:80])
        cdir = TUTS_DIR / slug
        out  = dict(r)

        if not pdf_url:
            out["tutorial_pdf_local"]      = None
            out["tutorial_translated_md"]  = None
            new_rows.append(out)
            continue

        cdir.mkdir(exist_ok=True)
        pdf_local = cdir / f"tutorial.{lang or 'unknown'}.pdf"

        # --- download ---
        if pdf_local.exists() and pdf_local.stat().st_size > 0:
            print(f"[{i}/{len(rows)}] {slug:40s}  ↑ already have {pdf_local.name}")
        else:
            print(f"[{i}/{len(rows)}] {slug:40s}  ↓ {pdf_url[:70]}")
            data = fetch_bytes(pdf_url)
            if not data:
                out["tutorial_pdf_local"]     = None
                out["tutorial_translated_md"] = None
                new_rows.append(out)
                continue
            # Sanity check: PDFs start with %PDF
            if not data.startswith(b"%PDF"):
                # The UCup download endpoint sometimes returns an HTML error page
                # for nonexistent attachments. Skip gracefully.
                print(f"   !! response is not a PDF ({len(data)} bytes); skipping")
                out["tutorial_pdf_local"]     = None
                out["tutorial_translated_md"] = None
                new_rows.append(out)
                continue
            pdf_local.write_bytes(data)
            time.sleep(0.4)
        out["tutorial_pdf_local"] = str(pdf_local.relative_to(PROJECT_DIR))

        # --- translate (if non-English) ---
        if lang and lang.startswith("en"):
            out["tutorial_translated_md"] = None
            new_rows.append(out)
            continue

        md_local = cdir / "tutorial.en.md"
        if md_local.exists() and md_local.stat().st_size > 0:
            print(f"   ✓ already translated → {md_local.relative_to(PROJECT_DIR)}")
            out["tutorial_translated_md"] = str(md_local.relative_to(PROJECT_DIR))
            new_rows.append(out)
            continue

        text = extract_text(pdf_local)
        if not text:
            out["tutorial_translated_md"] = None
            new_rows.append(out)
            continue

        # Heuristic: deep-translator language code mapping
        src = "auto"
        if lang and lang.startswith("zh"):
            src = "zh-CN" if "cn" in lang else "zh-TW"
        elif lang in ("ja", "ko", "ru", "es", "fr", "de", "pt"):
            src = lang

        print(f"   ↪ translating {len(text)} chars from {src}")
        translated, ok_chunks, total_chunks = translate_text(text, src_lang=src)
        if translated is None:
            # Translator deps missing or empty input — write the source as a fallback
            md_local.write_text(
                f"[translator unavailable — source text follows]\n\n{text}",
                encoding="utf-8",
            )
        else:
            md_local.write_text(translated, encoding="utf-8")
            print(f"   ✓ translated {ok_chunks}/{total_chunks} chunk(s) → {md_local.name}")
        out["tutorial_translated_md"] = str(md_local.relative_to(PROJECT_DIR))
        new_rows.append(out)

    OUT_PATH.write_text(json.dumps(new_rows, indent=2, ensure_ascii=False))
    have_pdf = sum(1 for r in new_rows if r.get("tutorial_pdf_local"))
    have_tr  = sum(1 for r in new_rows if r.get("tutorial_translated_md"))
    print()
    print(f"[done]")
    print(f"  PDFs downloaded:    {have_pdf}/{len(new_rows)}")
    print(f"  English markdowns:  {have_tr}  (translations of non-English PDFs)")
    print(f"  → {OUT_PATH}")
    print()
    print("When this finishes, tell me and I'll rebuild the v6 review sheet "
          "with local Tutorial / Tutorial (en) columns.")


if __name__ == "__main__":
    main()
