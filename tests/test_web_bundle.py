from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from gronestats.web_bundle.schema import SCHEMA_VERSION, TABLES
from gronestats.web_bundle.validate import validate_bundle


def _write_minimal_bundle(path: Path, *, schema_version: str = SCHEMA_VERSION) -> None:
    """Un bundle con todas las tablas del esquema y una fila cada una."""
    path.mkdir(parents=True, exist_ok=True)
    for index, (name, spec) in enumerate(TABLES.items()):
        pd.DataFrame([{column: index for column in spec.columns}]).to_parquet(path / f"{name}.parquet", index=False)
    (path / "manifest.json").write_text(json.dumps({"schema_version": schema_version, "release_id": "test"}), encoding="utf-8")


def test_a_complete_bundle_has_no_errors(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)

    assert validate_bundle(tmp_path) == []


def test_a_missing_table_is_reported_by_name(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    (tmp_path / "standings.parquet").unlink()

    errors = validate_bundle(tmp_path)

    assert any("standings" in error and "falta" in error for error in errors)


def test_a_missing_column_is_reported_with_table_and_column(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    matches = pd.read_parquet(tmp_path / "matches.parquet").drop(columns=["estadio"])
    matches.to_parquet(tmp_path / "matches.parquet", index=False)

    errors = validate_bundle(tmp_path)

    assert any("matches" in error and "estadio" in error for error in errors)


def test_a_duplicated_key_is_reported(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    matches = pd.read_parquet(tmp_path / "matches.parquet")
    pd.concat([matches, matches], ignore_index=True).to_parquet(tmp_path / "matches.parquet", index=False)

    errors = validate_bundle(tmp_path)

    assert any("matches" in error and "clave" in error for error in errors)


def test_another_major_schema_version_is_rejected(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path, schema_version="2.0.0")

    errors = validate_bundle(tmp_path)

    assert any("schema_version" in error for error in errors)


def test_a_missing_manifest_is_reported(tmp_path: Path) -> None:
    _write_minimal_bundle(tmp_path)
    (tmp_path / "manifest.json").unlink()

    assert any("manifest" in error for error in validate_bundle(tmp_path))
