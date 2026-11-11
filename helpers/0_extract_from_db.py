#!/usr/bin/env python3
"""
Stage 0: extract from disco.db (the disco-api SQLite export).

You don't need the disco-api application to run at all -- this reads the
.db file directly with Python's stdlib sqlite3 module.

Schema notes (reverse-engineered from the actual file, not assumed):

  actors(id, name, description, talkativeness)
      Every "speaker" -- including internal skills (Volition, Empathy,
      Electrochemistry, ...), the player ("You", id 387), a null actor
      used for joins ("HUB", id 0), and many game objects/items that
      have flavor-text "dialogue" (doors, books, radios, ...).

  dialogues(id, title, description, actor, conversant)
      One row per CONVERSATION (not per line). `title` is usually a
      location/scene breadcrumb like "WHIRLING F2 / TEQUILA DOOR" and
      is the best available proxy for DESIGN_SYSTEM.md's "location"
      field -- though for quest-like conversations it reads as a task
      name instead ("Find booze and drink it"). Good enough as-is;
      hand-edit obviously-wrong ones later if it bothers you.

  dentries(conversationid, id, title, dialoguetext, actor, conversant,
            isgroup, hascheck, hasalts, sequence, conditionstring, userscript)
      The actual per-line nodes, keyed by (conversationid, id) together
      -- `id` alone repeats across conversations. `dialoguetext` is the
      real spoken/read text; `title` is an editor-only preview label and
      should NOT be used as quote text. `dialoguetext == "0"` (the
      literal string) marks a node with no real text (menu/branch
      containers, isgroup=1) -- these are filtered out here, not left
      for the normalizer to guess about.

  dlinks / alternates / checks / modifiers / variables
      Conversation graph edges, conditional alternate lines, skill-check
      gates, and game-state variables, respectively. Not used by this
      script yet -- dlinks in particular is exactly what you'd want for
      building the "previous/current/next" exchange candidates described
      in the pipeline doc's revision section. Left as a documented next
      step rather than guessed at.

Output:
  data/raw/dialogue.jsonl      one real line per row, ready for 1_normalize.py
  data/speakers_raw.json       actor_id -> {name, type}, for 1_normalize.py --speakers

Usage:
    python3 0_extract_from_db.py --db /path/to/disco.db
"""
import argparse
import json
import sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
DEFAULT_OUT_DIALOGUE = DATA_DIR / "raw" / "dialogue.jsonl"
DEFAULT_OUT_SPEAKERS = DATA_DIR / "speakers_raw.json"

# Actor ids for the personified skills/attributes that actually speak
# lines in-game (talkativeness > 0 in the actors table). Confirmed by
# inspecting the actors table directly -- this id range is stable for
# this database but isn't guaranteed to match every future export.
SKILL_ACTOR_IDS = set(range(389, 409))  # Conceptualization .. Reaction Speed

PLAYER_ACTOR_ID = 387  # actors.name == "You"
HUB_ACTOR_ID = 0       # actors.name == "HUB", "null actor added to allow inner joins"

# Crude keyword heuristic for object/item "speakers" (doors, books, radios,
# newspapers, etc.) so they don't get lumped in as regular characters.
# Imperfect on purpose -- fix misclassifications by hand in
# data/speakers.json during curation rather than trying to perfect this.
OBJECT_NAME_HINTS = (
    "door", "radio", "certificate", "mug", "antenna", "trap:", "factory",
    "sandcastle", "grille", "marker", "figure in the dark", "vol. ",
    "look at ", "book", "newspaper", "telephone", "terminal", "machine",
)


def classify_actor(actor_id: int, name: str) -> str:
    if actor_id == PLAYER_ACTOR_ID:
        return "player"
    if actor_id == HUB_ACTOR_ID:
        return "hub"
    if actor_id in SKILL_ACTOR_IDS:
        return "skill"
    lowered = name.lower()
    if any(hint in lowered for hint in OBJECT_NAME_HINTS):
        return "object"
    return "character"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to disco.db")
    ap.add_argument("--out-dialogue", default=str(DEFAULT_OUT_DIALOGUE))
    ap.add_argument("--out-speakers", default=str(DEFAULT_OUT_SPEAKERS))
    ap.add_argument(
        "--include-player",
        action="store_true",
        help="Include player ('You') lines. Off by default -- the pipeline "
             "doc's default is to reject player-choice nodes (section 5.4); "
             "turn this on later for an opt-in 'detective mode'.",
    )
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"ERROR: {db_path} not found")

    out_dialogue = Path(args.out_dialogue)
    out_speakers = Path(args.out_speakers)
    out_dialogue.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # --- speaker registry -------------------------------------------------
    # Ground truth for "does this actor ever really speak?" is whether they
    # appear on a non-placeholder dentries row -- NOT the actors.talkativeness
    # column, which turns out to read 0 for at least 8 actors (Savoir Faire,
    # Interfacing, Composure, and the four Perception sub-skills) that
    # provably do speak in this export. Trust the data, not the stat field.
    cur.execute("""
        SELECT DISTINCT actor FROM dentries
        WHERE dialoguetext != '0' AND TRIM(dialoguetext) != ''
    """)
    actually_speaks = {row["actor"] for row in cur.fetchall()}

    cur.execute("SELECT id, name, description, talkativeness FROM actors")
    speakers_raw = {}
    for row in cur.fetchall():
        speakers_raw[str(row["id"])] = {
            "name": row["name"],
            "type": classify_actor(row["id"], row["name"]),
            "talkativeness": row["talkativeness"],
            "speaks_at_least_once": row["id"] in actually_speaks,
        }
    out_speakers.write_text(
        json.dumps(speakers_raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Wrote {len(speakers_raw)} speakers -> {out_speakers}")

    # --- conversation -> location lookup -----------------------------------
    cur.execute("SELECT id, title FROM dialogues")
    location_by_conversation = {row["id"]: row["title"] for row in cur.fetchall()}

    # --- dialogue lines -----------------------------------------------------
    where = "WHERE dialoguetext != '0' AND TRIM(dialoguetext) != ''"
    if not args.include_player:
        where += f" AND actor != {PLAYER_ACTOR_ID}"
    # HUB never carries real text (verified against this export), but the
    # filter costs nothing and protects against a future export where it might.
    where += f" AND actor != {HUB_ACTOR_ID}"

    cur.execute(f"""
        SELECT conversationid, id, dialoguetext, actor, conversant,
               hascheck, hasalts
        FROM dentries
        {where}
    """)

    n = 0
    with out_dialogue.open("w", encoding="utf-8") as fout:
        for row in cur.fetchall():
            record = {
                "id": f"{row['conversationid']}:{row['id']}",
                "text": row["dialoguetext"],
                "actor_id": row["actor"],
                "conversant_id": row["conversant"],
                "conversation_id": row["conversationid"],
                "location": location_by_conversation.get(row["conversationid"]),
                "has_check": bool(row["hascheck"]),
                "has_alternates": bool(row["hasalts"]),
                "source": "disco.db",
            }
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1

    print(f"Wrote {n} dialogue lines -> {out_dialogue}")
    print(
        f"(excluded {'player lines, ' if not args.include_player else ''}"
        "empty/placeholder nodes, and the HUB null-actor rows)"
    )


if __name__ == "__main__":
    main()
