#!/usr/bin/env python3
"""
List every actor referenced in data/quotes.json, with how many quotes
each has and whether they have a portrait set in data/speakers.json.

Usage:
    python3 list_actors.py
    python3 list_actors.py --quotes ../data/quotes.json --speakers ../data/speakers.json
    python3 list_actors.py --missing-only   # only show speakers without a portrait
"""
import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE_QUOTES_DIR = HERE.parent / "sources" / "disco-elysium" / "quotes"
DEFAULT_QUOTES = SOURCE_QUOTES_DIR / "quotes.json"
DEFAULT_SPEAKERS = SOURCE_QUOTES_DIR / "speakers.json"


def speakers_in_quote(quote: dict):
    if quote.get("type") == "exchange":
        return [line["speaker"] for line in quote.get("lines", [])]
    return [quote.get("speaker")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quotes", default=str(DEFAULT_QUOTES))
    ap.add_argument("--speakers", default=str(DEFAULT_SPEAKERS))
    ap.add_argument("--missing-only", action="store_true",
                     help="Only list speakers that don't have a portrait yet.")
    args = ap.parse_args()

    quotes_path = Path(args.quotes)
    speakers_path = Path(args.speakers)

    if not quotes_path.exists():
        raise SystemExit(f"ERROR: {quotes_path} not found")

    quotes_data = json.loads(quotes_path.read_text(encoding="utf-8"))
    speakers = {}
    if speakers_path.exists():
        speakers = json.loads(speakers_path.read_text(encoding="utf-8"))
        speakers.pop("_readme", None)

    counts = Counter()
    for q in quotes_data.get("quotes", []):
        for slug in speakers_in_quote(q):
            if slug:
                counts[slug] += 1

    rows = []
    for slug, n in counts.items():
        info = speakers.get(slug, {})
        rows.append({
            "slug": slug,
            "name": info.get("name", "(not in speakers.json)"),
            "type": info.get("type", "?"),
            "has_portrait": bool(info.get("image")),
            "quote_count": n,
        })

    rows.sort(key=lambda r: (-r["quote_count"], r["slug"]))

    if args.missing_only:
        rows = [r for r in rows if not r["has_portrait"]]

    if not rows:
        print("Nothing to show." if args.missing_only else "No speakers found in quotes.json.")
        return

    name_w = max(len(r["name"]) for r in rows)
    slug_w = max(len(r["slug"]) for r in rows)

    print(f"{'SLUG'.ljust(slug_w)}  {'NAME'.ljust(name_w)}  {'TYPE':<10}  {'PORTRAIT':<8}  QUOTES")
    for r in rows:
        print(
            f"{r['slug'].ljust(slug_w)}  {r['name'].ljust(name_w)}  "
            f"{r['type']:<10}  {'yes' if r['has_portrait'] else 'no':<8}  {r['quote_count']}"
        )

    print(f"\n{len(rows)} distinct speaker(s), {sum(counts.values())} total quote-speaker references.")
    missing = sum(1 for r in rows if not r["has_portrait"])
    if missing and not args.missing_only:
        print(f"{missing} of them have no portrait yet (run with --missing-only to just see those).")


if __name__ == "__main__":
    main()
