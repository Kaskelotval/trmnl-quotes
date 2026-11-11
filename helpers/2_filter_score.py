#!/usr/bin/env python3
"""
Stage 2: automatic rejection + candidate scoring.

Input:  data/normalized/dialogue.jsonl  (from 1_normalize.py)
Output: data/candidates/candidates.jsonl, sorted best-first.

This stage is deliberately aggressive about rejection (pipeline doc
section 5) and deliberately simple/explainable about scoring (section 6-7):
the score is a prioritization mechanism for human review, not a
quality verdict.

Usage:
    python3 2_filter_score.py
    python3 2_filter_score.py --min-words 5 --max-chars 350
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DEFAULT_IN = DATA_DIR / "normalized" / "dialogue.jsonl"
DEFAULT_OUT = DATA_DIR / "candidates" / "candidates.jsonl"

NEGATIVE_OPENERS = ("and ", "but ", "so ", "then ", "also ")
REFERENCE_WORDS = {"that", "this", "it", "him", "her", "them", "those", "these"}


def reject_reason(node: dict, min_words: int, max_chars: int) -> str:
    """Return a short rejection reason, or None if the node survives
    automatic rejection (pipeline doc section 5)."""
    d = node.get("derived", {})
    text = (node.get("text") or "").strip()

    if not text:
        return "empty_text"
    if d.get("looks_like_system_text"):
        return "system_or_debug_text"
    if d.get("is_player_choice"):
        return "player_choice"
    if d.get("word_count", 0) < min_words:
        return "too_short"
    if d.get("character_count", 0) > max_chars:
        # not deleted upstream, but not auto-carried into candidates either --
        # classify as long/very_long for possible manual extraction instead.
        return "too_long_for_auto_candidate"
    if d.get("is_narration") and not any(c.isalpha() for c in text.replace('"', "")):
        return "pure_narration"
    return None


def standalone_score(text: str, d: dict) -> int:
    score = 0
    lower = text.strip().lower()

    if text.strip().endswith((".", "!", "?", "\u2014", "\u2026")):
        score += 1
    if not any(lower.startswith(op) for op in NEGATIVE_OPENERS):
        score += 1
    first_words = set(lower.split()[:6])
    if not (first_words & REFERENCE_WORDS):
        score += 1
    if d.get("has_question") or d.get("has_exclamation"):
        score += 1
    if d.get("word_count", 0) >= 8:
        score += 1  # more room to be a complete thought
    return score


def linguistic_score(text: str, d: dict) -> int:
    score = 0
    if any(p in text for p in ("\u2014", ":", ";")):
        score += 1  # aphoristic punctuation, often signals a turn of phrase
    if d.get("word_count", 0) >= 6 and d.get("word_count", 0) <= 40:
        score += 1
    return score


def length_score(d: dict) -> int:
    c = d.get("character_count", 0)
    if 40 <= c <= 250:
        return 2
    if 250 < c <= 350:
        return 1
    return 0


def narration_penalty(d: dict) -> int:
    return 1 if d.get("has_stage_direction") else 0


def score_node(node: dict) -> dict:
    d = node.get("derived", {})
    text = node.get("text", "")

    s = {
        "standalone_score": standalone_score(text, d),
        "linguistic_score": linguistic_score(text, d),
        "length_score": length_score(d),
        "narration_penalty": narration_penalty(d),
    }
    s["total"] = (
        s["standalone_score"]
        + s["linguistic_score"]
        + s["length_score"]
        - s["narration_penalty"]
    )
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default=str(DEFAULT_IN))
    ap.add_argument("--out", dest="outfile", default=str(DEFAULT_OUT))
    ap.add_argument("--min-words", type=int, default=5)
    ap.add_argument("--max-chars", type=int, default=350)
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)

    if not infile.exists():
        raise SystemExit(f"ERROR: {infile} not found. Run 1_normalize.py first.")

    kept, rejected = 0, 0
    reasons = {}
    scored = []

    with infile.open(encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            node = json.loads(line)
            reason = reject_reason(node, args.min_words, args.max_chars)
            if reason:
                rejected += 1
                reasons[reason] = reasons.get(reason, 0) + 1
                continue
            node["score"] = score_node(node)
            scored.append(node)
            kept += 1

    scored.sort(key=lambda n: n["score"]["total"], reverse=True)

    with outfile.open("w", encoding="utf-8") as fout:
        for node in scored:
            fout.write(json.dumps(node, ensure_ascii=False) + "\n")

    print(f"Kept {kept} candidates, rejected {rejected} -> {outfile}")
    print("Rejection reasons:")
    for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  {reason}: {count}")


if __name__ == "__main__":
    main()
