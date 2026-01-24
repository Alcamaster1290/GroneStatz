from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

from app.core.config import get_settings
from app.services.data_pipeline import ingest_parquets_to_duckdb, sync_duckdb_to_postgres

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def snapshot_parquets(path: Path) -> Dict[str, Tuple[int, int]]:
    state: Dict[str, Tuple[int, int]] = {}
    for file in sorted(path.glob("*.parquet")):
        try:
            stat = file.stat()
        except FileNotFoundError:
            continue
        state[str(file)] = (int(stat.st_mtime), stat.st_size)
    return state


def run_pipeline(settings) -> None:
    ingest_parquets_to_duckdb(settings)
    sync_duckdb_to_postgres(settings)


def main() -> None:
    settings = get_settings()

    parser = argparse.ArgumentParser(
        description="Watch parquet directory and refresh DuckDB + Postgres."
    )
    parser.add_argument("--dir", default=settings.PARQUET_DIR, help="Parquet directory to watch.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval seconds.")
    parser.add_argument(
        "--debounce",
        type=float,
        default=3.0,
        help="Seconds to wait after last change before running."
    )
    parser.add_argument(
        "--run-on-start",
        action="store_true",
        help="Run pipeline immediately on start."
    )
    args = parser.parse_args()

    watch_dir = Path(args.dir)
    if not watch_dir.exists():
        raise FileNotFoundError(f"parquet_dir_not_found: {watch_dir}")

    if str(watch_dir) != settings.PARQUET_DIR:
        settings.PARQUET_DIR = str(watch_dir)

    logging.info("watching_parquets: %s", watch_dir)
    state = snapshot_parquets(watch_dir)

    if args.run_on_start:
        logging.info("watch_run_start")
        run_pipeline(settings)
        state = snapshot_parquets(watch_dir)

    pending = False
    last_change = 0.0

    try:
        while True:
            time.sleep(args.interval)
            current = snapshot_parquets(watch_dir)
            if current != state:
                pending = True
                last_change = time.monotonic()
                state = current
                continue

            if pending and time.monotonic() - last_change >= args.debounce:
                logging.info("watch_change_detected")
                run_pipeline(settings)
                state = snapshot_parquets(watch_dir)
                pending = False
    except KeyboardInterrupt:
        logging.info("watch_stopped")


if __name__ == "__main__":
    main()
