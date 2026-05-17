from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_LEAGUE_NAME = "Liga 1 Peru"


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def league_data_root(league: str = DEFAULT_LEAGUE_NAME, *, repo_root: Path | None = None) -> Path:
    root = repo_root or repository_root()
    return root / "gronestats" / "data" / league


def league_warehouse_dir(league: str = DEFAULT_LEAGUE_NAME, *, repo_root: Path | None = None) -> Path:
    return league_data_root(league, repo_root=repo_root) / "warehouse"


def league_warehouse_db_path(
    league: str = DEFAULT_LEAGUE_NAME,
    *,
    repo_root: Path | None = None,
    filename: str = "gronestats.duckdb",
) -> Path:
    return league_warehouse_dir(league, repo_root=repo_root) / filename


@dataclass(frozen=True)
class PublishedTargetLayout:
    root_dir: Path

    @property
    def releases_dir(self) -> Path:
        return self.root_dir / "releases"

    @property
    def current_dir(self) -> Path:
        return self.root_dir / "current"

    def release_dir(self, release_id: str) -> Path:
        return self.releases_dir / release_id


@dataclass(frozen=True)
class SeasonDataLayout:
    repo_root: Path
    league: str
    season: int

    @property
    def league_dir(self) -> Path:
        return league_data_root(self.league, repo_root=self.repo_root)

    @property
    def season_dir(self) -> Path:
        return self.league_dir / str(self.season)

    @property
    def warehouse_dir(self) -> Path:
        return self.league_dir / "warehouse"

    @property
    def warehouse_db_path(self) -> Path:
        return self.warehouse_dir / "gronestats.duckdb"

    @property
    def raw_dir(self) -> Path:
        return self.season_dir / "raw"

    @property
    def staging_dir(self) -> Path:
        return self.season_dir / "staging"

    @property
    def curated_dir(self) -> Path:
        return self.season_dir / "curated"

    @property
    def dashboard(self) -> PublishedTargetLayout:
        return PublishedTargetLayout(self.season_dir / "dashboard")

    @property
    def fantasy(self) -> PublishedTargetLayout:
        return PublishedTargetLayout(self.season_dir / "fantasy")

    @property
    def legacy_normalized_dir(self) -> Path:
        return self.season_dir / "parquets" / "normalized"


def season_layout(
    season: int,
    *,
    league: str = DEFAULT_LEAGUE_NAME,
    repo_root: Path | None = None,
) -> SeasonDataLayout:
    return SeasonDataLayout(
        repo_root=repo_root or repository_root(),
        league=league,
        season=int(season),
    )
