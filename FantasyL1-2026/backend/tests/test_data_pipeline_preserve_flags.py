import sys
import types

sys.modules.setdefault(
    "duckdb",
    types.SimpleNamespace(DuckDBPyConnection=object, connect=lambda *args, **kwargs: None),
)

from app.services.data_pipeline import _upsert_players


class DummySession:
    def __init__(self) -> None:
        self.statement = None
        self.params = None

    def execute(self, statement, params):  # noqa: ANN001
        self.statement = statement
        self.params = params


def _sample_row() -> dict:
    return {
        "player_id": 1,
        "name": "Jugador Uno",
        "short_name": "J. Uno",
        "position": "M",
        "team_id": 2305,
        "price_current": 6.2,
        "minutesplayed": 0,
        "matches_played": 0,
        "goals": 0,
        "assists": 0,
        "saves": 0,
        "fouls": 0,
    }


def test_upsert_players_includes_preserve_flags_in_payload() -> None:
    db = DummySession()
    _upsert_players(
        db,
        [_sample_row()],
        preserve_existing_price_current=True,
        preserve_existing_base_stats=True,
    )

    assert isinstance(db.params, list)
    assert db.params[0]["preserve_existing_price_current"] is True
    assert db.params[0]["preserve_existing_base_stats"] is True


def test_upsert_players_sql_has_conditional_preserve_clauses() -> None:
    db = DummySession()
    _upsert_players(
        db,
        [_sample_row()],
        preserve_existing_price_current=False,
        preserve_existing_base_stats=False,
    )

    sql = str(db.statement)
    assert "WHEN :preserve_existing_price_current THEN players_catalog.price_current" in sql
    assert "WHEN :preserve_existing_base_stats THEN players_catalog.minutesplayed" in sql
    assert "WHEN :preserve_existing_base_stats THEN players_catalog.matches_played" in sql
