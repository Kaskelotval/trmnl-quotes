#!/usr/bin/env python3
"""
Drop raw portrait images into one folder, get e-ink-ready PNGs in another.

Workflow this is built for:
  1. Find/crop portrait images for characters (any size, any format).
  2. Name each file after the speaker's slug in data/speakers.json,
    e.g. kim_kitsuragi.jpg, volition.png, insulindian_phasmid.webp.
  3. Drop them all in portraits_raw/ (or wherever --input points).
  4. Run this script.

It will, for each image:
  - convert to grayscale
  - auto-contrast it (helps a lot on e-ink -- flat/washed-out source
    images end up muddy once the display dithers them)
  - optionally center-crop to a target aspect ratio (e.g. 3:4, to match
    the game's own portrait framing) before resizing
  - resize to a fixed width, keeping aspect ratio
  - save as an optimized PNG in the output folder

By default it also updates the Disco Elysium speakers.json for you: if a speaker's
slug matches an image's filename (minus extension), its "image" field
gets set to the right path. Existing "image" values already pointing
somewhere are left alone unless --overwrite-speakers is passed.

Usage:
    python3 prepare_portraits.py
    python3 prepare_portraits.py --width 200 --aspect 3:4
    python3 prepare_portraits.py --input portraits_raw --output ../sources/disco-elysium/images
"""
import argparse
import json
import os
from pathlib import Path
from typing import Optional
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
SOURCE_DIR = REPO_ROOT / "sources" / "disco-elysium"
SOURCE_QUOTES_DIR = SOURCE_DIR / "quotes"
DEFAULT_INPUT = HERE / "portraits_raw"
DEFAULT_OUTPUT = SOURCE_DIR / "images"
DEFAULT_SPEAKERS = SOURCE_QUOTES_DIR / "speakers.json"

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}


def parse_aspect(spec: str) -> float:
    """'3:4' -> 0.75 (width/height)."""
    try:
        w, h = spec.split(":")
        return float(w) / float(h)
    except (ValueError, ZeroDivisionError):
        raise argparse.ArgumentTypeError(
            f"--aspect must look like '3:4' or '4:3', got: {spec!r}"
        )


def crop_to_aspect(img: Image.Image, target_ratio: float) -> Image.Image:
    """Center-crop img (no distortion) to match target_ratio (width/height)."""
    w, h = img.size
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 1e-3:
        return img  # already close enough

    if current_ratio > target_ratio:
        # too wide -- crop the sides
        new_w = round(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        # too tall -- crop top/bottom
        new_h = round(w / target_ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


def process_image(src: Path, dest: Path, width: int, aspect: Optional[float],
                   autocontrast: bool) -> tuple[int, int, int]:
    with Image.open(src) as img:
        img = ImageOps.exif_transpose(img)  # respect phone-camera rotation tags
        img = img.convert("L")  # grayscale

        if autocontrast:
            img = ImageOps.autocontrast(img, cutoff=1)

        if aspect:
            img = crop_to_aspect(img, aspect)

        w, h = img.size
        height = round(width * h / w)
        img = img.resize((width, height), Image.LANCZOS)

        dest.parent.mkdir(parents=True, exist_ok=True)
        img.save(dest, format="PNG", optimize=True)

        return width, height, dest.stat().st_size


def update_speakers_json(speakers_path: Path, processed: dict, output_dir: Path,
                          overwrite: bool) -> None:
    if not speakers_path.exists():
        print(f"  (no {speakers_path} found -- skipping speakers.json update)")
        return

    data = json.loads(speakers_path.read_text(encoding="utf-8"))
    rel_output_dir = Path(os.path.relpath(output_dir.resolve(), speakers_path.parent.resolve()))

    updated, skipped_existing, unmatched = [], [], []
    for slug, filename in processed.items():
        if slug not in data:
            unmatched.append(slug)
            continue
        entry = data[slug]
        if entry.get("image") and not overwrite:
            skipped_existing.append(slug)
            continue
        entry["image"] = str(rel_output_dir / filename).replace("\\", "/")
        updated.append(slug)

    speakers_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    if updated:
        print(f"  Updated speakers.json image path for: {', '.join(updated)}")
    if skipped_existing:
        print(f"  Left existing image path alone for: {', '.join(skipped_existing)} "
              f"(pass --overwrite-speakers to replace)")
    if unmatched:
        print(f"  NOTE: no speaker in speakers.json matches filename(s): {', '.join(unmatched)} "
              f"-- check the slug spelling (see list_actors.py)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(DEFAULT_INPUT))
    ap.add_argument("--output", default=str(DEFAULT_OUTPUT))
    ap.add_argument("--width", type=int, default=200)
    ap.add_argument("--aspect", type=parse_aspect, default=None,
                     help="Center-crop to this aspect ratio before resizing, "
                          "e.g. '3:4' or '4:3'. Omit to keep each source "
                          "image's original proportions.")
    ap.add_argument("--no-autocontrast", action="store_true",
                     help="Skip auto-contrast (on by default -- helps a lot on e-ink).")
    ap.add_argument("--speakers", default=str(DEFAULT_SPEAKERS))
    ap.add_argument("--no-update-speakers", action="store_true")
    ap.add_argument("--overwrite-speakers", action="store_true",
                     help="Replace an existing 'image' value in speakers.json instead of leaving it.")
    args = ap.parse_args()

    input_dir = Path(args.input)
    output_dir = Path(args.output)
    project_root = REPO_ROOT

    if not input_dir.exists():
        raise SystemExit(
            f"ERROR: {input_dir} not found. Create it and drop portrait images in, "
            f"named after each speaker's slug (see pipeline/list_actors.py)."
        )

    images = sorted(p for p in input_dir.iterdir() if p.suffix.lower() in SUPPORTED_EXTS)
    if not images:
        raise SystemExit(f"No supported images found in {input_dir} ({', '.join(SUPPORTED_EXTS)}).")

    print(f"Processing {len(images)} image(s) from {input_dir} -> {output_dir}")
    if args.aspect:
        print(f"  cropping to aspect ratio {args.aspect}, width={args.width}px")
    else:
        print(f"  keeping original aspect ratio, width={args.width}px")

    processed = {}
    for src in images:
        slug = src.stem
        dest = output_dir / f"{slug}.png"
        w, h, size_bytes = process_image(
            src, dest, args.width, args.aspect, autocontrast=not args.no_autocontrast
        )
        size_kb = size_bytes / 1024
        flag = "  <- consider compressing further (pngquant)" if size_kb > 15 else ""
        print(f"  {src.name:30s} -> {dest.relative_to(project_root)}  ({w}x{h}, {size_kb:.1f}KB){flag}")
        processed[slug] = dest.name

    if not args.no_update_speakers:
        print("\nUpdating speakers.json...")
        update_speakers_json(
            Path(args.speakers), processed, output_dir, args.overwrite_speakers
        )

    print(f"\nDone. {len(processed)} portrait(s) ready in {output_dir}")


if __name__ == "__main__":
    main()
