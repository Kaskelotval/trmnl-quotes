#!/usr/bin/env python3
"""
Stage 4: compile the curated runtime corpus.

Joins:
    - helpers/data/candidates/candidates.jsonl (text + speaker info)
    - helpers/data/curated/decisions.jsonl     (review decisions)
    - sources/disco-elysium/quotes/speakers.json

into:
    - sources/disco-elysium/quotes/quotes.json (canonical source quote data)

Approved records are merged into the existing quote collection by id, so
hand-maintained quotes are preserved.

Usage:
    python3 4_build_curated.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
SOURCE_QUOTES_DIR = HERE.parent / "sources" / "disco-elysium" / "quotes"
CANDIDATES = DATA_DIR / "candidates" / "candidates.jsonl"
COMMUNITY_MATCHES = DATA_DIR / "candidates" / "community_matches.jsonl"
DECISIONS = DATA_DIR / "curated" / "decisions.jsonl"
SPEAKERS = SOURCE_QUOTES_DIR / "speakers.json"
OUT = SOURCE_QUOTES_DIR / "quotes.json"


def load_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    candidates = {c["id"]: c for c in load_jsonl(CANDIDATES)}

    # Community-matched quotes (5_community_match.py) may not appear in
    # candidates.jsonl at all -- e.g. a short-but-iconic line that automatic
    # rejection filtered out before scoring. Fold matched ones
    # in here, in the same shape 4_build_curated.py already expects, so an
    # approval from either review queue resolves correctly.
    for c in load_jsonl(COMMUNITY_MATCHES):
        if c.get("status") != "matched":
            continue
        cid = c["dialogue_id"]
        if cid not in candidates:  # don't clobber a richer automatic-pipeline record
            candidates[cid] = {
                "id": cid,
                "text": c["verified_text"],
                "actor_id": c.get("actor_id"),
                "location": c.get("location"),
                "derived": {"actor_name": c.get("actor_name")},
            }

    decisions = load_jsonl(DECISIONS)
    speakers = json.loads(SPEAKERS.read_text(encoding="utf-8")) if SPEAKERS.exists() else {}

    # Reverse lookup: numeric actor_id (as written by 0_extract_from_db.py and
    # build_speaker_registry.py) -> slug. This is exact, unlike matching on
    # name text, since speakers.json stores the actor_id it came from.
    actor_id_to_slug = {}
    for slug, info in speakers.items():
        if isinstance(info, dict) and "actor_id" in info:
            actor_id_to_slug[info["actor_id"]] = slug

    # last decision per id wins (in case of re-review)
    latest = {}
    for d in decisions:
        latest[d["id"]] = d["status"]

    existing_data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    quotes_by_id = {
        quote["id"]: quote
        for quote in existing_data.get("quotes", [])
        if isinstance(quote, dict) and quote.get("id")
    }
    unmapped_speakers = set()

    for cid, status in latest.items():
        if status != "approved":
            continue
        node = candidates.get(cid)
        if node is None:
            print(f"WARNING: decision for {cid} has no matching candidate, skipping.")
            continue

        derived = node.get("derived", {})
        actor_id = node.get("actor_id")
        speaker_id = actor_id_to_slug.get(actor_id)
        if speaker_id is None:
            unmapped_speakers.add(derived.get("actor_name") or f"actor_id {actor_id}")
            speaker_id = "unknown"

        quotes_by_id[f"dialogue-{cid}"] = {
            "id": f"dialogue-{cid}",
            "status": "approved",
            "type": "single",
            "text": node.get("text", "").strip(),
            "speaker": speaker_id,
            "game": "Disco Elysium",
            "location": node.get("location"),
            "context": node.get("context"),
            "source_id": cid,
            "display_safe": True,
        }

    quotes = list(quotes_by_id.values())

    payload = {"quotes": quotes}

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {len(quotes)} approved quotes -> {OUT}")
    if unmapped_speakers:
        print("\nThese speakers appeared in approved quotes but aren't in "
              "sources/disco-elysium/quotes/speakers.json yet (mapped to 'unknown' for now):")
        for name in sorted(unmapped_speakers):
            print(f"  - {name}")
        print("Add them to speakers.json and rerun to fix the mapping.")


if __name__ == "__main__":
    main()
