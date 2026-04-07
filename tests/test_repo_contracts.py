from __future__ import annotations

import importlib
import warnings
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_text_files() -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.py", "*.ps1", "*.md"):
        files.extend(REPO_ROOT.glob(pattern))
        files.extend((REPO_ROOT / "gronestats").rglob(pattern))
        files.extend((REPO_ROOT / "FantasyL1-2026").rglob(pattern))
        files.extend((REPO_ROOT / "scripts").rglob(pattern))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path in seen or ".venv" in path.parts or "__pycache__" in path.parts:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def test_no_active_legacy_parquet_references_outside_legacy_and_docs() -> None:
    offenders: list[str] = []
    for path in _tracked_text_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative.startswith("docs/"):
            continue
        if "/legacy/" in relative:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "parquets/normalized" in content:
            offenders.append(relative)
    assert offenders == []


def test_no_productive_imports_from_processing_legacy_outside_wrappers() -> None:
    allowed = {
        "gronestats/processing/build_positional_parquets.py",
        "gronestats/processing/data_loader_unprep_liga1_2025.py",
        "gronestats/processing/normalize_parquets.py",
        "gronestats/processing/prep_and_test_data_liga1_2025.py",
        "gronestats/processing/st_create_parquets.py",
        "gronestats/processing/st_parquets_dashboard.py",
        "gronestats/processing/st_parquets_updater.py",
    }
    offenders: list[str] = []
    for path in _tracked_text_files():
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative in allowed or "/legacy/" in relative:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        if "gronestats.processing.legacy" in content:
            offenders.append(relative)
    assert offenders == []


def test_legacy_wrappers_still_resolve() -> None:
    modules = [
        "gronestats.processing.st_create_parquets",
        "gronestats.processing.build_positional_parquets",
        "gronestats.processing.normalize_parquets",
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for module_name in modules:
            module = importlib.import_module(module_name)
            assert module is not None
