"""Arranque local de la API: ``py -3.11 -m gronestats.api`` (127.0.0.1:8000)."""

from __future__ import annotations

import os

import uvicorn

from gronestats.api.app import create_app


def main() -> None:
    uvicorn.run(create_app(), host=os.getenv("GRONESTATS_API_HOST", "127.0.0.1"), port=int(os.getenv("GRONESTATS_API_PORT", "8000")))


if __name__ == "__main__":
    main()
