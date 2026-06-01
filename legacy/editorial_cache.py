"""
editorial_cache.py — extract & cache per-problem editorial text once per contest.

Without this module, every per-problem agent run re-parses the same contest
PDF and re-translates Chinese text. That wastes ~3 min per problem AND many
LLM tokens. Here we do it ONCE per contest and cache the results on disk.

Layout (rooted at PROJECT_ROOT/tutorials/<contest-slug>/.editorial-cache/):

  language.txt              # detected language: en, zh, es, etc.
  extracted.txt             # raw pdftotext -layout output
  problems/A.md             # per-problem section, ENGLISH (translated if needed)
  problems/B.md
  problems/...
  index.json                # {"A": {"name": "Almost Aligned", "section_lines": [8, 25]}, ...}

The cache is invalidated when the source file's mtime is newer than the
cache's. Removing the .editorial-cache/ folder triggers a fresh extract.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import pathlib
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Run `pdftotext -layout` (preferred) or fall back to pdfminer.six."""
    if shutil.which("pdftotext"):
        # Use a temp file so we don't have to write next to the source PDF
        # (which may live on a read-only or restricted-permission mount).
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
            tmp_path = tf.name
        try:
            subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), tmp_path],
                check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            text = pathlib.Path(tmp_path).read_text(errors="ignore")
        finally:
            try: os.unlink(tmp_path)
            except OSError: pass
        return text
    # pdfminer fallback
    try:
        from pdfminer.high_level import extract_text
        return extract_text(str(pdf_path))
    except Exception as e:
        raise RuntimeError(
            f"No PDF text extractor available. Install poppler "
            f"(`brew install poppler`) or pdfminer.six. {e}"
        )


# ---------------------------------------------------------------------------
# Language detection — simple heuristic, no external deps
# ---------------------------------------------------------------------------

_LANG_RANGES = {
    "zh":  (0x4E00, 0x9FFF),     # CJK Unified Ideographs
    "ja":  (0x3040, 0x30FF),     # Hiragana + Katakana
    "ko":  (0xAC00, 0xD7AF),     # Hangul syllables
    "ru":  (0x0400, 0x04FF),     # Cyrillic
    "ar":  (0x0600, 0x06FF),     # Arabic
}


def detect_language(text: str) -> str:
    """Return a 2-letter ISO code: 'en' if plain ASCII-heavy, else the
    dominant non-ASCII script's code. Sample the first 5000 chars for speed."""
    sample = text[:5000]
    if not sample:
        return "en"
    counts = {code: 0 for code in _LANG_RANGES}
    for ch in sample:
        cp = ord(ch)
        for code, (lo, hi) in _LANG_RANGES.items():
            if lo <= cp <= hi:
                counts[code] += 1
                break
    # Spanish/Portuguese: detect via common diacritics + words (best-effort)
    if "á" in sample or "ñ" in sample or "ó" in sample or "é" in sample:
        if "que" in sample.lower() and "el " in sample.lower():
            counts["es"] = counts.get("es", 0) + 50
    top_lang = max(counts, key=counts.get) if counts else "en"
    return top_lang if counts.get(top_lang, 0) > 50 else "en"


# ---------------------------------------------------------------------------
# Per-problem section splitter
# ---------------------------------------------------------------------------

# Matches "Problem A", "Problem A:", "Problem A –", "题目 A", "Tarea A" etc.
_PROBLEM_HEADER_RE = re.compile(
    r"^\s*(?:Problem|Tarea|Problema|题目|题|問題)\s+([A-Z])(?:[\s\.\:–—\-]|$)",
    re.M | re.IGNORECASE,
)


def split_by_problem(extracted_text: str) -> dict[str, str]:
    """Find every "Problem X" header, return {letter: section_text}.
    The section runs from the header until the next problem header (or EOF)."""
    matches = list(_PROBLEM_HEADER_RE.finditer(extracted_text))
    if not matches:
        return {}
    out = {}
    for i, m in enumerate(matches):
        letter = m.group(1).upper()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(extracted_text)
        section = extracted_text[start:end].rstrip()
        if letter in out:
            # If we matched twice, prefer the longer section (often the first
            # match is just a TOC entry)
            if len(section) > len(out[letter]):
                out[letter] = section
        else:
            out[letter] = section
    return out


# ---------------------------------------------------------------------------
# Translation — calls `claude -p` once per source language
# ---------------------------------------------------------------------------

def translate_to_english(text: str, source_lang: str) -> str:
    """Call `claude -p --bare` with a focused translation prompt. Idempotent
    (running on already-English text returns it ~unchanged)."""
    if source_lang == "en":
        return text
    if not shutil.which("claude"):
        # Fallback: return original with a marker so coach knows it's untranslated
        return f"[TRANSLATION SKIPPED — claude CLI not available]\n\n{text}"

    prompt = (
        f"Translate the following competitive-programming editorial text from "
        f"{source_lang} to English. Preserve LaTeX/formula text verbatim — only "
        f"translate prose. Preserve code blocks verbatim. Preserve section "
        f"headers like 'Problem A' / 'Problem B'. Output ONLY the translated "
        f"text, no preamble.\n\n--- BEGIN ---\n{text}\n--- END ---"
    )
    res = subprocess.run(
        ["claude", "-p", prompt,
         "--dangerously-skip-permissions",
         "--output-format", "text"],
        cwd=str(PROJECT_ROOT),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=600,    # 10 min cap; long PDFs may take a while
    )
    if res.returncode != 0:
        raise RuntimeError(f"claude translation failed (rc={res.returncode}): "
                           f"{(res.stdout or '')[:300]}")
    return res.stdout or text


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

# Cache lives under problem-repository/.cache/editorial/<contest-folder-name>/
# rather than alongside the source PDF — the tutorials/ folder may be
# read-only or under user-managed permissions.
_CACHE_ROOT = Path(__file__).resolve().parent / ".cache" / "editorial"


def _cache_dir(contest_dir: Path) -> Path:
    return _CACHE_ROOT / contest_dir.name


def _is_cache_fresh(cache_dir: Path, source_path: Path) -> bool:
    """Cache is fresh iff it exists and was created after the source's mtime."""
    if not cache_dir.exists():
        return False
    flag = cache_dir / "language.txt"
    if not flag.exists():
        return False
    return flag.stat().st_mtime >= source_path.stat().st_mtime


def build_cache(source_path: Path, *, force: bool = False) -> Path:
    """Build (or reuse) the editorial cache for the contest containing
    `source_path`. Returns the cache directory."""
    contest_dir = source_path.parent
    cache = _cache_dir(contest_dir)
    if not force and _is_cache_fresh(cache, source_path):
        return cache

    # Fresh build
    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True)

    # 1. Extract
    if source_path.suffix == ".pdf":
        text = extract_pdf_text(source_path)
    else:
        text = source_path.read_text(errors="ignore")
    (cache / "extracted.txt").write_text(text)

    # 2. Detect language
    lang = detect_language(text)
    (cache / "language.txt").write_text(lang)

    # 3. Split by problem (BEFORE translation — preserves original headers)
    raw_sections = split_by_problem(text)

    # 4. Translate per-section if needed (one translation call per section
    #    keeps each call within token limits and produces clean output)
    eng_dir = cache / "problems"
    eng_dir.mkdir()
    index = {}
    if not raw_sections:
        # Fall back: stash whole text under a single "?" key
        eng_dir.joinpath("_all.md").write_text(
            translate_to_english(text, lang) if lang != "en" else text
        )
        index["_all"] = {"len": len(text)}
    else:
        for letter, section in raw_sections.items():
            if lang != "en":
                eng = translate_to_english(section, lang)
            else:
                eng = section
            eng_dir.joinpath(f"{letter}.md").write_text(eng)
            # First non-blank line is usually "Problem X – Name"
            first = next((ln for ln in section.splitlines() if ln.strip()), "")
            index[letter] = {"first_line": first[:120], "raw_len": len(section)}

    (cache / "index.json").write_text(json.dumps(index, indent=2))
    return cache


def get_problem_section(source_path: Path, problem_letter: str) -> Optional[Path]:
    """Build/use the cache and return the path to the per-problem English
    extract for `problem_letter` (e.g. 'A'), or None if not found."""
    cache = build_cache(source_path)
    if not problem_letter:
        return None
    p = cache / "problems" / f"{problem_letter.upper()}.md"
    return p if p.exists() else None


# ---------------------------------------------------------------------------
# CLI for ad-hoc use
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python editorial_cache.py <pdf_or_md_path> [problem_letter]")
        sys.exit(1)
    source = Path(sys.argv[1]).resolve()
    cache = build_cache(source)
    print(f"Cache built at: {cache}")
    print(f"Language: {(cache / 'language.txt').read_text()}")
    idx = json.loads((cache / 'index.json').read_text())
    print(f"Problems indexed: {sorted(idx.keys())}")
    if len(sys.argv) >= 3:
        letter = sys.argv[2].upper()
        p = cache / "problems" / f"{letter}.md"
        if p.exists():
            print(f"\n=== Problem {letter} ===")
            print(p.read_text()[:1000])
        else:
            print(f"No section for problem {letter}")
