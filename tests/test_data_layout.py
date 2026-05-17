from __future__ import annotations

from pathlib import Path

from gronestats.data_layout import season_layout


def test_season_layout_resolves_dashboard_and_fantasy_targets(tmp_path: Path) -> None:
    layout = season_layout(2026, league="Liga 1 Peru", repo_root=tmp_path)

    assert layout.season_dir == tmp_path / "gronestats" / "data" / "Liga 1 Peru" / "2026"
    assert layout.warehouse_dir == tmp_path / "gronestats" / "data" / "Liga 1 Peru" / "warehouse"
    assert layout.warehouse_db_path == layout.warehouse_dir / "gronestats.duckdb"
    assert layout.raw_dir == layout.season_dir / "raw"
    assert layout.staging_dir == layout.season_dir / "staging"
    assert layout.curated_dir == layout.season_dir / "curated"
    assert layout.dashboard.current_dir == layout.season_dir / "dashboard" / "current"
    assert layout.dashboard.release_dir("20260407_010203") == layout.season_dir / "dashboard" / "releases" / "20260407_010203"
    assert layout.fantasy.current_dir == layout.season_dir / "fantasy" / "current"
    assert layout.fantasy.release_dir("20260407_010203") == layout.season_dir / "fantasy" / "releases" / "20260407_010203"
