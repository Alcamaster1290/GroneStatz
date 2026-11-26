"""Comprobación de un release contra el esquema: tablas, columnas, claves únicas y versión mayor."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

from gronestats.web_bundle.schema import SCHEMA_VERSION, TABLES, major


def validate_bundle(path: Path) -> list[str]:
    """Lista de errores (vacía si el release cumple el contrato)."""
    path = Path(path)
    errors: list[str] = []
    manifest_path = path / "manifest.json"
    if not manifest_path.exists():
        errors.append("manifest.json: no existe")
    else:
        version = json.loads(manifest_path.read_text(encoding="utf-8")).get("schema_version")
        if version is None or major(version) != major(SCHEMA_VERSION):
            errors.append(f"manifest.json: schema_version {version!r} incompatible con {SCHEMA_VERSION} (otra versión mayor)")
    for name, spec in TABLES.items():
        file = path / f"{name}.parquet"
        if not file.exists():
            errors.append(f"{name}: falta la tabla")
            continue
        present = set(pq.read_schema(file).names)
        missing = [column for column in spec.columns if column not in present]
        if missing:
            errors.append(f"{name}: faltan columnas {missing}")
            continue
        if spec.key:
            keys = pd.read_parquet(file, columns=list(spec.key))
            duplicated = int(keys.duplicated().sum())
            if duplicated:
                errors.append(f"{name}: {duplicated} filas repiten la clave {list(spec.key)}")
    return errors
