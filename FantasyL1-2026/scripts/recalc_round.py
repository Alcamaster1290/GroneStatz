from __future__ import annotations

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = BASE_DIR / "backend"
sys.path.append(str(BACKEND_DIR))

# Stub for v1.0: points calculation not implemented yet.

if __name__ == "__main__":
    print("recalc_round_stub_v1")
