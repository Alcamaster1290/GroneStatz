from __future__ import annotations

import argparse
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent

DEFAULT_PLAYERS_DIR = REPO_ROOT / "gronestats" / "images" / "players"
DEFAULT_TEAMS_DIR = REPO_ROOT / "gronestats" / "images" / "teams"

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _color_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _guess_background_color(img: Image.Image) -> Tuple[int, int, int] | None:
    w, h = img.size
    pixels = img.load()
    corners = [
        pixels[0, 0],
        pixels[w - 1, 0],
        pixels[0, h - 1],
        pixels[w - 1, h - 1],
    ]
    transparent_corners = sum(1 for corner in corners if len(corner) == 4 and corner[3] == 0)
    if transparent_corners >= 2:
        return None
    rgb_corners = [corner[:3] for corner in corners]
    return Counter(rgb_corners).most_common(1)[0][0]


def _apply_transparent_background(img: Image.Image, tolerance: int) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")

    bg = _guess_background_color(img)
    if bg is None:
        return img
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            dist = _color_distance((r, g, b), bg)
            if dist <= tolerance:
                alpha_factor = dist / max(tolerance, 1)
                pixels[x, y] = (r, g, b, int(a * alpha_factor))

    return img


def _iter_images(directory: Path) -> Iterable[Path]:
    if not directory.exists():
        return []
    return [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS]


def convert_directory(directory: Path, tolerance: int, remove_originals: bool) -> int:
    count = 0
    for path in _iter_images(directory):
        try:
            with Image.open(path) as img:
                img = _apply_transparent_background(img, tolerance=tolerance)
                output = path.with_suffix(".png")
                output.parent.mkdir(parents=True, exist_ok=True)
                img.save(output, format="PNG")
            if remove_originals and path.suffix.lower() != ".png":
                path.unlink(missing_ok=True)
            count += 1
        except Exception as exc:
            logging.warning("image_skip %s (%s)", path, exc)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert player/team images to PNG with transparent background.")
    parser.add_argument("--players-dir", type=Path, default=DEFAULT_PLAYERS_DIR)
    parser.add_argument("--teams-dir", type=Path, default=DEFAULT_TEAMS_DIR)
    parser.add_argument("--tolerance", type=int, default=30)
    parser.add_argument("--remove-originals", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    players_count = convert_directory(args.players_dir, args.tolerance, args.remove_originals)
    teams_count = convert_directory(args.teams_dir, args.tolerance, args.remove_originals)

    logging.info("converted_players=%s", players_count)
    logging.info("converted_teams=%s", teams_count)


if __name__ == "__main__":
    main()
