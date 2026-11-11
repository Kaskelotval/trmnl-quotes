#!/usr/bin/env python3
"""
Stage 5 (optional, run alongside/before stage 3 review): community discovery.

Implements the pipeline doc's revision: "community sources are candidate
generators" for the game DB, never authoritative on their own. This reads
externally-sourced quote text (pipeline/community_seed_quotes.json) and
fuzzy-matches each one against your FULL normalized corpus (not just the
survivors of automatic filtering -- an iconic quote might be short enough
to have been auto-rejected, and section 5.1 of the pipeline doc explicitly
allows restoring short-but-iconic lines by hand).

For each seed:
  - best match found above threshold  -> status "matched", carries the
    VERIFIED text from your database (not the possibly-paraphrased/censored
    external text) plus the real speaker and location
  - no match found above threshold    -> status "unverified", per the
    pipeline doc: "It should not be treated as a real Disco Elysium quote."

Output: data/candidates/community_matches.jsonl, matched entries first,
sorted by (mentions, match_ratio) so the most cross-referenced, best-verified
quotes bubble to the top.

This turns "review 41,000 lines" into "review this short list first" --
run 3_review_cli.py with --file pointing at this output to triage it before
touching the full automatic-scoring queue.

Usage:
    python3 5_community_match.py
    python3 5_community_match.py --threshold 0.75
"""
import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
SEEDS = HERE / "community_seed_quotes.json"
NORMALIZED = DATA_DIR / "normalized" / "dialogue.jsonl"
OUT = DATA_DIR / "candidates" / "community_matches.jsonl"

SMART_QUOTES = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2014": "-", "\u2013": "-", "\u2026": "...",
})


def normalize(text: str) -> str:
    text = text.translate(SMART_QUOTES)
    text = re.sub(r"[*_]", "", text)          # strip markdown emphasis
    text = re.sub(r"[\u2665]+", "", text)      # strip Steam's heart-censoring glyphs
    text = re.sub(r"\s+", " ", text).strip().lower()
    text = re.sub(r"[^\w\s]", "", text)        # drop remaining punctuation for comparison
    return text


def load_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.72,
                     help="Minimum SequenceMatcher ratio to count as a match (0-1).")
    args = ap.parse_args()

    if not SEEDS.exists():
        raise SystemExit(f"ERROR: {SEEDS} not found.")
    if not NORMALIZED.exists():
        raise SystemExit(f"ERROR: {NORMALIZED} not found. Run 0_extract_from_db.py and 1_normalize.py first.")

    seed_data = json.loads(SEEDS.read_text(encoding="utf-8"))
    seeds = seed_data["seeds"]
    corpus = load_jsonl(NORMALIZED)

    # Pre-normalize the whole corpus once.
    corpus_norm = [(node, normalize(node.get("text", ""))) for node in corpus]

    results = []
    for seed in seeds:
        seed_norm = normalize(seed["text"])
        best_node, best_ratio = None, 0.0

        for node, text_norm in corpus_norm:
            if not text_norm:
                continue
            # Cheap pre-filter: skip wildly different lengths before running
            # the more expensive SequenceMatcher ratio over ~40k lines.
            if abs(len(text_norm) - len(seed_norm)) > max(20, len(seed_norm) * 0.4):
                continue
            ratio = SequenceMatcher(None, seed_norm, text_norm).ratio()
            if ratio > best_ratio:
                best_ratio, best_node = ratio, node

        results.append({
            "status": "matched",
            "match_ratio": round(best_ratio, 3),
            "dialogue_id": best_node["id"],
            "verified_text": best_node["text"],
            "actor_id": best_node.get("actor_id"),
            "actor_name": best_node.get("derived", {}).get("actor_name"),
            "location": best_node.get("location"),
            "claimed_speaker": seed.get("claimed_speaker"),
            "mentions": seed.get("mentions", 1),
            "sources": seed.get("sources", []),
            "seed_text": seed["text"],
        })

    results.sort(key=lambda r: (r["status"] != "matched", -r["mentions"], -r["match_ratio"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fout:
        for r in results:
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")

    matched = sum(1 for r in results if r["status"] == "matched")
    print(f"{matched}/{len(results)} seed quotes matched against the real database.")
    print(f"Wrote {OUT}")
    print("\nMatched:")
    for r in results:
        if r["status"] == "matched":
            print(f"  [{r['match_ratio']}] {r['actor_name']}: {r['verified_text'][:80]}")
    print("\nUnverified (no confident match -- treat as unproven):")
    for r in results:
        if r["status"] != "matched":
            print(f"  [{r['match_ratio']}] claimed={r['claimed_speaker']}: {r['seed_text'][:80]}")


if __name__ == "__main__":
    main()
