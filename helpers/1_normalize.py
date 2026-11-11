#!/usr/bin/env python3
"""
Stage 1: normalize.

Input:  data/raw/dialogue.jsonl
        One JSON object per line, minimally:
          {"id": ..., "text": ..., "actor_id": ..., "conversant_id": ...,
           "conversation_id": ..., "source": "disco.db"}

        This file is NOT produced by this repo. You need to export it
        yourself from whatever holds the actual Disco Elysium dialogue
        (e.g. disco-api, or a DiscoBrowser SQLite export). See README.md.

Output: data/normalized/dialogue.jsonl
        Same records, plus derived/disposable classification fields
        (DESIGN doc section 3). The original "text" field is never
        modified.

Usage:
    python3 1_normalize.py --speakers ../data/speakers_raw.json
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DEFAULT_IN = DATA_DIR / "raw" / "dialogue.jsonl"
DEFAULT_OUT = DATA_DIR / "normalized" / "dialogue.jsonl"

# --- crude heuristics -------------------------------------------------
# These are intentionally simple and explainable (per the pipeline doc's
# "keep the score explainable" rule). Tune them against your real corpus;
# they will not be perfect out of the box.

STAGE_DIRECTION_RE = re.compile(
    r"\b(he|she|it|they)\s+(looks?|nods?|sighs?|shrugs?|smiles?|frowns?|"
    r"turns?|walks?|stares?|glances?)\b",
    re.IGNORECASE,
)
QUESTION_RE = re.compile(r"\?\s*$")
EXCLAMATION_RE = re.compile(r"!\s*$")
PROFANITY_RE = re.compile(
    r"\b(fuck|shit|damn|bitch|asshole)\w*\b", re.IGNORECASE
)
SYSTEM_TEXT_RE = re.compile(
    r"^\s*(\[|\{|<|VAR_|DEBUG|TODO|XXX|PLACEHOLDER)", re.IGNORECASE
)
PLAYER_CHOICE_HINT_RE = re.compile(
    r"^\s*\[.*\]\s*$"
)  # many dialogue exports bracket player choice text


def classify(text: str) -> dict:
    stripped = text.strip()
    word_count = len(stripped.split())
    char_count = len(stripped)

    return {
        "word_count": word_count,
        "character_count": char_count,
        "has_stage_direction": bool(STAGE_DIRECTION_RE.search(stripped)),
        "has_question": bool(QUESTION_RE.search(stripped)),
        "has_exclamation": bool(EXCLAMATION_RE.search(stripped)),
        "has_profanity": bool(PROFANITY_RE.search(stripped)),
        "looks_like_system_text": bool(SYSTEM_TEXT_RE.search(stripped)),
        "looks_like_player_choice": bool(PLAYER_CHOICE_HINT_RE.match(stripped)),
    }


def load_speaker_types(path: Path) -> dict:
    """
    Optional: data/speakers_raw.json mapping actor_id -> {"name":..., "type":...}
    so normalization can tag is_skill / is_narration accurately instead of
    guessing from text alone. If absent, everything defaults to "unknown".
    """
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="infile", default=str(DEFAULT_IN))
    ap.add_argument("--out", dest="outfile", default=str(DEFAULT_OUT))
    ap.add_argument("--speakers", dest="speakers", default=str(DATA_DIR / "speakers_raw.json"))
    args = ap.parse_args()

    infile = Path(args.infile)
    outfile = Path(args.outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)

    if not infile.exists():
        print(f"ERROR: input file not found: {infile}", file=sys.stderr)
        print(
            "This script expects a raw dialogue export at that path. "
            "See README.md for where that data has to come from.",
            file=sys.stderr,
        )
        sys.exit(1)

    speaker_types = load_speaker_types(Path(args.speakers)) if args.speakers else {}

    n_in = 0
    n_out = 0
    with infile.open(encoding="utf-8") as fin, outfile.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            n_in += 1
            node = json.loads(line)
            text = node.get("text", "") or ""

            actor_id = node.get("actor_id")
            actor_info = speaker_types.get(str(actor_id), {})
            actor_type = actor_info.get("type", "unknown")

            derived = classify(text)
            derived.update(
                {
                    "actor_name": actor_info.get("name"),
                    "actor_type": actor_type,
                    "is_skill": actor_type == "skill",
                    "is_narration": actor_type == "narrator",
                    "is_player_choice": derived["looks_like_player_choice"],
                }
            )

            record = dict(node)
            record["derived"] = derived
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            n_out += 1

    print(f"Normalized {n_out}/{n_in} records -> {outfile}")


if __name__ == "__main__":
    main()
