#!/usr/bin/env python3
"""Build the initial lexicon database with optional external data enrichment."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from database.lexicon import build_lexicon, _load_external_data


def load_external_if_available() -> dict | None:
    external_dir = Path(__file__).parent.parent / "data" / "external"
    if external_dir.exists():
        data = _load_external_data(external_dir)
        has_any = any(v for v in data.values() if v)
        if has_any:
            print(f"Loaded external data from {external_dir}")
            print(f"  Meanings: {len(data['meanings'])} chars")
            print(f"  Strokes: {len(data['strokes'])} chars")
            print(f"  Name freq: {len(data['name_freq'])} chars")
            print(f"  Gender prob: {len(data['gender_prob'])} chars")
            return data
        else:
            print("External data directory exists but no data loaded")
    else:
        print("No external data found (run fetch_external_data.py first)")
    return None


async def main():
    db_path = str(Path(__file__).parent.parent / "data" / "lexicon.db")
    external_data = load_external_if_available()
    await build_lexicon(db_path, verbose=True, external_data=external_data)


if __name__ == "__main__":
    asyncio.run(main())
