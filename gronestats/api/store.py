"""Un release abierto en DuckDB (solo lectura) y el almacén que lo recarga sin cortar el servicio.

La API lee siempre de ``releases/<id>/`` (inmutable); ``current`` es solo el puntero. Así cambiar de release no rompe las
consultas en curso, y un release nuevo que no cumple el esquema deja sirviendo al anterior.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from gronestats.web_bundle.schema import TABLES
from gronestats.web_bundle.validate import validate_bundle


class ReleaseError(RuntimeError):
    """El release no se puede abrir: no cumple el esquema o falta el puntero."""


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Filas como diccionarios JSON: NaN y NA pasan a ``None`` y las fechas a texto ISO."""
    return json.loads(frame.to_json(orient="records", date_format="iso", date_unit="s"))


class Release:
    def __init__(self, path: Path, images_dir: Path | None = None) -> None:
        self.path = Path(path)
        errors = validate_bundle(self.path)
        if errors:
            raise ReleaseError("; ".join(errors))
        self.manifest: dict[str, Any] = json.loads((self.path / "manifest.json").read_text(encoding="utf-8"))
        self.images_dir = Path(images_dir) if images_dir is not None else None
        self._con = duckdb.connect(":memory:")
        for name in TABLES:
            self._con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{(self.path / f'{name}.parquet').as_posix()}')")
        self._teams = {int(row["team_id"]): row for row in records(self.q("SELECT * FROM teams"))}
        self._crests = self._stems("teams")

    @property
    def release_id(self) -> str:
        return str(self.manifest["release_id"])

    def q(self, sql: str, params: list[Any] | tuple[Any, ...] = ()) -> pd.DataFrame:
        cursor = self._con.cursor()  # un cursor por consulta: la conexión no se comparte entre hilos
        try:
            return cursor.execute(sql, list(params)).df()
        finally:
            cursor.close()

    def _stems(self, folder: str) -> dict[int, str]:
        directory = self.images_dir / folder if self.images_dir is not None else None
        if directory is None or not directory.exists():
            return {}
        return {int(path.stem): path.name for path in directory.iterdir() if path.is_file() and path.stem.isdigit()}

    def team(self, team_id: int | None) -> dict[str, Any] | None:
        """Equipo con su escudo (URL de la API) o ``None`` si no existe."""
        if team_id is None or pd.isna(team_id) or int(team_id) not in self._teams:
            return None
        team = dict(self._teams[int(team_id)])
        team["crest"] = f"/assets/teams/{self._crests[int(team_id)]}" if int(team_id) in self._crests else None
        return team

    @staticmethod
    def photo_url(filename: str | None) -> str | None:
        return f"/assets/players/{filename}" if filename else None


class Store:
    """El release que se está sirviendo. ``reload`` abre el que apunta ``current`` y, si falla, no toca el actual."""

    def __init__(self, bundle_dir: Path, images_dir: Path | None) -> None:
        self.bundle_dir = Path(bundle_dir)
        self.images_dir = images_dir
        self._lock = threading.Lock()
        self.release = Release(self._resolve(), images_dir)

    def _resolve(self) -> Path:
        if (self.bundle_dir / "manifest.json").exists():  # se pasó la carpeta de un release
            return self.bundle_dir
        pointer = self.bundle_dir / "current" / "manifest.json"
        if not pointer.exists():
            raise ReleaseError(f"no hay release en {self.bundle_dir}: falta current/manifest.json")
        release_id = json.loads(pointer.read_text(encoding="utf-8"))["release_id"]
        immutable = self.bundle_dir / "releases" / release_id
        return immutable if immutable.exists() else self.bundle_dir / "current"

    def reload(self) -> Release:
        candidate = Release(self._resolve(), self.images_dir)
        with self._lock:
            self.release = candidate
        return candidate
