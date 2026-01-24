from __future__ import annotations

import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

from app.core.config import get_settings
from app.services.data_pipeline import ingest_parquets_to_duckdb

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    settings = get_settings()
    ingest_parquets_to_duckdb(settings)
    print("duckdb_ingest_ok")
