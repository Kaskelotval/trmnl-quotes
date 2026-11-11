#!/usr/bin/env python3
"""
Stage 3: human review.

The pipeline doc calls this "the critical component" -- a fast
approve/reject/needs_context loop over the *scored* candidates, so a
human never has to read the entire game's dialogue.

Input:  data/candidates/candidates.jsonl (from 2_filter_score.py)
Output: data/curated/decisions.jsonl (append-only decision log; safe to
        stop and resume -- already-decided ids are skipped on restart)

Controls:
    a = approve        r = reject
    c = needs_context   s = skip for now (ask again next run)
    q = quit

Usage:
    python3 3_review_cli.py
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
CANDIDATES = DATA_DIR / "candidates" / "candidates.jsonl"
COMMUNITY_MATCHES = DATA_DIR / "candidates" / "community_matches.jsonl"
DECISIONS = DATA_DIR / "curated" / "decisions.jsonl"


def load_jsonl(path: Path):
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def already_decided_ids(decisions: list) -> set:
    return {d["id"] for d in decisions}


def normalize_for_review(node: dict, is_community: bool) -> dict:
    """Map either candidates.jsonl or community_matches.jsonl (matched
    entries only) into one shape for rendering/deciding, without losing
    the original record."""
    if is_community:
        return {
            "id": node["dialogue_id"],
            "text": node["verified_text"],
            "actor_name": node.get("actor_name"),
            "actor_type": None,
            "score": None,
            "community": {"mentions": node.get("mentions"), "sources": node.get("sources")},
        }
    d = node.get("derived", {})
    return {
        "id": node["id"],
        "text": node.get("text", ""),
        "actor_name": d.get("actor_name") or node.get("actor_id"),
        "actor_type": d.get("actor_type", "unknown"),
        "score": node.get("score", {}).get("total"),
        "community": None,
    }


def render(item: dict) -> str:
    lines = ["-" * 70]
    meta = f"id: {item['id']}"
    if item["score"] is not None:
        meta += f"   score: {item['score']}"
    if item["community"]:
        meta += f"   community mentions: {item['community']['mentions']}"
    lines.append(meta)
    lines.append(f"speaker: {item['actor_name']}" + (f"  (type: {item['actor_type']})" if item['actor_type'] else ""))
    if item["community"] and item["community"].get("sources"):
        lines.append(f"sources: {', '.join(item['community']['sources'])}")
    lines.append("")
    lines.append(f'  "{item["text"].strip()}"')
    lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--file", choices=["candidates", "community"], default="candidates",
        help="Review the full auto-scored queue (default) or just the "
             "community-verified shortlist from 5_community_match.py first.",
    )
    args = ap.parse_args()

    DECISIONS.parent.mkdir(parents=True, exist_ok=True)
    is_community = args.file == "community"
    source_path = COMMUNITY_MATCHES if is_community else CANDIDATES

    raw = load_jsonl(source_path)
    if is_community:
        raw = [n for n in raw if n.get("status") == "matched"]
    if not raw:
        raise SystemExit(
            f"No reviewable items found at {source_path}. "
            + ("Run 5_community_match.py first." if is_community else "Run 2_filter_score.py first.")
        )

    candidates = [normalize_for_review(n, is_community) for n in raw]

    decisions = load_jsonl(DECISIONS)
    done_ids = already_decided_ids(decisions)

    pending = [c for c in candidates if c["id"] not in done_ids]
    print(f"{len(pending)} candidates left to review "
          f"({len(done_ids)} already decided).")

    with DECISIONS.open("a", encoding="utf-8") as fout:
        for i, node in enumerate(pending, 1):
            print(render(node))
            print(f"[{i}/{len(pending)}]  (a)pprove  (r)eject  (c)needs_context  "
                  f"(s)kip  (q)uit")
            choice = input("> ").strip().lower()

            if choice == "q":
                print("Stopping. Progress is saved -- rerun to resume.")
                break
            if choice == "s":
                continue

            status = {"a": "approved", "r": "rejected", "c": "needs_context"}.get(choice)
            if status is None:
                print("Unrecognized input, treating as skip.")
                continue

            decision = {"id": node["id"], "status": status}
            fout.write(json.dumps(decision, ensure_ascii=False) + "\n")
            fout.flush()

    print("Done. Run 4_build_curated.py to merge approved quotes into the source quotes.json.")


if __name__ == "__main__":
    main()
