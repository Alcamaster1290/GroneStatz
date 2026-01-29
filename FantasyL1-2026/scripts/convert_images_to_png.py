from __future__ import annotations

import argparse
import logging
import math
import shutil
from collections import Counter
from collections import deque
from pathlib import Path
from typing import Iterable, Tuple

from PIL import Image

BASE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BASE_DIR.parent

DEFAULT_PLAYERS_DIR = REPO_ROOT / "gronestats" / "images" / "players"
DEFAULT_TEAMS_DIR = REPO_ROOT / "gronestats" / "images" / "teams"
DEFAULT_PUBLIC_PLAYERS_DIR = BASE_DIR / "frontend" / "public" / "images" / "players"
DEFAULT_PUBLIC_TEAMS_DIR = BASE_DIR / "frontend" / "public" / "images" / "teams"

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _color_distance_sq(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


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

    tol = max(1, tolerance)
    tol_sq = tol * tol
    soft = max(4, int(tol * 0.4))
    soft_sq = soft * soft

    visited = bytearray(width * height)
    queue: deque[Tuple[int, int]] = deque()

    def idx(x: int, y: int) -> int:
        return y * width + x

    def push_if_bg(x: int, y: int) -> None:
        if x < 0 or y < 0 or x >= width or y >= height:
            return
        index = idx(x, y)
        if visited[index]:
            return
        r, g, b, _ = pixels[x, y]
        dist_sq = _color_distance_sq((r, g, b), bg)
        if dist_sq <= tol_sq:
            visited[index] = 1
            queue.append((x, y))

    for x in range(width):
        push_if_bg(x, 0)
        push_if_bg(x, height - 1)
    for y in range(height):
        push_if_bg(0, y)
        push_if_bg(width - 1, y)

    while queue:
        x, y = queue.popleft()
        r, g, b, a = pixels[x, y]
        dist_sq = _color_distance_sq((r, g, b), bg)
        if dist_sq <= soft_sq:
            alpha = 0
        elif dist_sq <= tol_sq:
            dist = math.sqrt(dist_sq)
            alpha = int(a * (dist - soft) / max(tol - soft, 1))
        else:
            alpha = a
        pixels[x, y] = (r, g, b, alpha)

        push_if_bg(x - 1, y)
        push_if_bg(x + 1, y)
        push_if_bg(x, y - 1)
        push_if_bg(x, y + 1)

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


def sync_pngs(source_dir: Path, dest_dir: Path) -> int:
    if not source_dir.exists():
        return 0
    if source_dir.resolve() == dest_dir.resolve():
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    source_pngs = {p.name: p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() == ".png"}
    for name, source_path in source_pngs.items():
        dest_path = dest_dir / name
        try:
            if dest_path.exists() and dest_path.resolve() == source_path.resolve():
                continue
            shutil.copy2(source_path, dest_path)
        except shutil.SameFileError:
            continue
    removed = 0
    for dest_path in dest_dir.iterdir():
        if dest_path.is_file() and dest_path.suffix.lower() == ".png" and dest_path.name not in source_pngs:
            dest_path.unlink(missing_ok=True)
            removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert player/team images to PNG with transparent background.")
    parser.add_argument("--players-dir", type=Path, default=DEFAULT_PLAYERS_DIR)
    parser.add_argument("--teams-dir", type=Path, default=DEFAULT_TEAMS_DIR)
    parser.add_argument("--public-players-dir", type=Path, default=DEFAULT_PUBLIC_PLAYERS_DIR)
    parser.add_argument("--public-teams-dir", type=Path, default=DEFAULT_PUBLIC_TEAMS_DIR)
    parser.add_argument("--tolerance", type=int, default=30)
    parser.add_argument("--remove-originals", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    players_count = convert_directory(args.players_dir, args.tolerance, args.remove_originals)
    teams_count = convert_directory(args.teams_dir, args.tolerance, args.remove_originals)
    removed_public_players = sync_pngs(args.players_dir, args.public_players_dir)
    removed_public_teams = sync_pngs(args.teams_dir, args.public_teams_dir)

    logging.info("converted_players=%s", players_count)
    logging.info("converted_teams=%s", teams_count)
    logging.info("synced_public_players_removed=%s", removed_public_players)
    logging.info("synced_public_teams_removed=%s", removed_public_teams)


if __name__ == "__main__":
    main()
