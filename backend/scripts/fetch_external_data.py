#!/usr/bin/env python3
"""Download and process external data sources: chinese-xinhua + Chinese-Names-Corpus."""

import json
import sys
import os
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

EXTERNAL_DIR = Path(__file__).parent.parent / "data" / "external"

# Multiple mirrors — try in order
XINHUA_URLS = [
    "https://raw.githubusercontent.com/pwxcoo/chinese-xinhua/master/data/word.json",
    "https://cdn.jsdelivr.net/gh/pwxcoo/chinese-xinhua/data/word.json",
]
NAMES_GENDER_URLS = [
    "https://raw.githubusercontent.com/wainshine/Chinese-Names-Corpus/master"
    "/Chinese_Names_Corpus/Chinese_Names_Corpus_Gender%EF%BC%88120W%EF%BC%89.txt",
    "https://cdn.jsdelivr.net/gh/wainshine/Chinese-Names-Corpus@master"
    "/Chinese_Names_Corpus/Chinese_Names_Corpus_Gender%EF%BC%88120W%EF%BC%89.txt",
]


def download_file(
    urls: str | list[str], dest: Path, desc: str = ""
) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  Already exists: {dest.name}")
        return True

    if isinstance(urls, str):
        urls = [urls]

    for url in urls:
        try:
            print(f"  Downloading {desc or url}...", end=" ", flush=True)
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest, "wb") as f:
                    f.write(resp.read())
            size_mb = dest.stat().st_size / (1024 * 1024)
            if size_mb < 0.01:
                # Probably an error page — remove and try next mirror
                dest.unlink()
                print(f"too small ({size_mb*1024:.0f} KB), retrying...")
                continue
            print(f"done ({size_mb:.1f} MB)")
            return True
        except Exception as e:
            print(f"mirror failed: {type(e).__name__}")
            # Remove partial download if any
            if dest.exists():
                dest.unlink()
            continue

    print(f"  FAILED: all mirrors unreachable for {desc}")
    print("  Hint: manually download the file and place it at:")
    print(f"    {dest}")
    return False


def process_word_json(word_path: Path) -> dict:
    """Process word.json into lookup dicts for meanings, strokes, pinyins."""
    with open(word_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    meanings: dict[str, str] = {}
    strokes: dict[str, int] = {}
    pinyins: dict[str, str] = {}

    for entry in data:
        ch = entry.get("word", "")
        if not ch or len(ch) != 1:
            continue

        expl = entry.get("explanation", "").strip()
        if expl:
            meanings[ch] = expl

        s = entry.get("strokes", "")
        if s:
            try:
                strokes[ch] = int(s)
            except (ValueError, TypeError):
                pass

        py = entry.get("pinyin", "").strip().lower()
        if py:
            pinyins[ch] = py

    out = {"meanings": meanings, "strokes": strokes, "pinyins": pinyins}
    out_path = word_path.parent / "word_processed.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)

    print(f"  Processed {len(meanings)} meanings, {len(strokes)} strokes, {len(pinyins)} pinyins")
    return out


def process_names_gender(names_path: Path, stats_out: Path) -> dict:
    """Parse name+gender file and compute per-character statistics.

    Expected line format: "name\tM" or "name\tF" (tab-separated).
    """
    char_male: dict[str, int] = {}
    char_female: dict[str, int] = {}
    char_total: dict[str, int] = {}
    total_lines = 0

    with open(names_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total_lines += 1

            parts = line.split("\t")
            if len(parts) < 2:
                continue

            name = parts[0].strip()
            gender = parts[1].strip().upper()

            for ch in name:
                if "\u4e00" <= ch <= "\u9fff":
                    char_total[ch] = char_total.get(ch, 0) + 1
                    if gender == "M":
                        char_male[ch] = char_male.get(ch, 0) + 1
                    elif gender == "F":
                        char_female[ch] = char_female.get(ch, 0) + 1

    if not char_total:
        print("  WARNING: no valid CJK characters found, check file format")
        return {}

    stats: dict[str, dict] = {}
    for ch in char_total:
        total = char_total[ch]
        male_count = char_male.get(ch, 0)
        female_count = char_female.get(ch, 0)
        m_prob = male_count / total if total > 0 else 0.5
        freq = total / total_lines if total_lines > 0 else 0

        stats[ch] = {
            "freq": round(freq, 8),
            "gender_m_prob": round(m_prob, 4),
            "male_count": male_count,
            "female_count": female_count,
            "total": total,
        }

    with open(stats_out, "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False)

    print(f"  Processed {len(stats)} chars from {total_lines:,} names")
    return stats


def main():
    EXTERNAL_DIR.mkdir(parents=True, exist_ok=True)
    print("Fetching external data sources...")

    word_path = EXTERNAL_DIR / "word.json"
    if download_file(XINHUA_URLS, word_path, "chinese-xinhua word.json"):
        process_word_json(word_path)

    names_gender_path = EXTERNAL_DIR / "chinese_names_gender.txt"
    if download_file(NAMES_GENDER_URLS, names_gender_path, "Chinese-Names-Corpus (120W with gender)"):
        stats_path = EXTERNAL_DIR / "char_stats.json"
        if not stats_path.exists():
            process_names_gender(names_gender_path, stats_path)

    print(f"\nExternal data ready in {EXTERNAL_DIR}")


if __name__ == "__main__":
    main()
