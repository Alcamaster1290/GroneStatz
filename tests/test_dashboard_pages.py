from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from gronestats.dashboard import pages
from gronestats.dashboard.data import build_team_options, describe_active_scope
from gronestats.dashboard.models import ConsolidatedSeasonOverview, DatasetBundle, FilterState, SeasonDataset


class _DummyContext:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def markdown(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None


def _make_bundle() -> DatasetBundle:
    matches = pd.DataFrame(
        {
            "match_id": [10, 20],
            "round_number": [1, 28],
            "tournament": ["Liga 1, Apertura", "Primera Division, Grand Final"],
            "tournament_label": ["Apertura", "Grand Final"],
            "round_label": ["Apertura Â· R1", "Grand Final Â· R28"],
            "fecha_dt": pd.to_datetime(["2025-01-01", "2025-12-20"]),
            "fecha": ["01/01/2025 15:00", "20/12/2025 20:00"],
            "home_id": [10, 10],
            "away_id": [20, 20],
            "home": ["Alianza", "Alianza"],
            "away": ["Melgar", "Melgar"],
            "home_score": [1, 2],
            "away_score": [0, 1],
            "scoreline": ["1 - 0", "2 - 1"],
            "partido": ["Alianza 1 - 0 Melgar", "Alianza 2 - 1 Melgar"],
            "estadio": ["Matute", "Matute"],
            "ciudad": ["Lima", "Lima"],
            "arbitro": ["A", "B"],
        }
    )
    teams = pd.DataFrame({"team_id": [10, 20], "team_name": ["Alianza", "Melgar"]})
    players = pd.DataFrame(
        {
            "player_id": [1, 2],
            "name": ["Jugador A", "Jugador B"],
            "short_name": ["Jugador A", "Jugador B"],
            "position": ["F", "M"],
            "team_id": [10, 20],
        }
    )
    player_match = pd.DataFrame(
        {
            "match_id": [10, 20],
            "player_id": [1, 1],
            "team_id": [10, 10],
            "name": ["Jugador A", "Jugador A"],
            "position": ["F", "F"],
            "minutesplayed": [90, 90],
            "goals": [1, 0],
            "assists": [0, 1],
            "saves": [0, 0],
            "fouls": [1, 1],
            "penaltywon": [0, 0],
            "penaltysave": [0, 0],
            "penaltyconceded": [0, 0],
            "fecha_dt": pd.to_datetime(["2025-01-01", "2025-12-20"]),
            "home": ["Alianza", "Alianza"],
            "away": ["Melgar", "Melgar"],
            "scoreline": ["1 - 0", "2 - 1"],
            "round_label": ["Apertura Â· R1", "Grand Final Â· R28"],
        }
    )
    return DatasetBundle(
        season_year=2025,
        season_label="Liga 1 2025",
        data_dir=Path("gronestats/data/Liga 1 Peru/2025/dashboard/current"),
        matches=matches,
        teams=teams,
        players=players,
        player_match=player_match,
        player_totals=pd.DataFrame(),
        team_stats=pd.DataFrame(),
        average_positions=pd.DataFrame(),
        heatmap_points=pd.DataFrame(),
        validation_status="passed",
        validation_warnings=tuple(),
        manifest={},
        validation={},
        loaded_at=datetime(2026, 3, 15, 12, 0, 0),
    )


def _install_streamlit_stubs(monkeypatch, session_state: dict[str, object]) -> None:
    monkeypatch.setattr(pages.st, "session_state", session_state, raising=False)

    def _columns(spec, **kwargs):
        count = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        return [_DummyContext() for _ in range(count)]

    def _selectbox(label, options, key=None, **kwargs):
        values = list(options)
        current = session_state.get(key)
        if current in values:
            return current
        selected = values[0] if values else None
        if key is not None:
            session_state[key] = selected
        return selected

    monkeypatch.setattr(pages.st, "columns", _columns, raising=False)
    monkeypatch.setattr(pages.st, "selectbox", _selectbox, raising=False)
    monkeypatch.setattr(pages.st, "text_input", lambda label, **kwargs: session_state.get(kwargs.get("key"), ""), raising=False)
    monkeypatch.setattr(pages.st, "markdown", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(pages.st, "popover", lambda *args, **kwargs: _DummyContext(), raising=False)


def test_describe_active_scope_formats_tournaments_and_rounds() -> None:
    summary = describe_active_scope(
        pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 7],
                "tournament": ["Liga 1, Apertura", "Liga 1, Clausura"],
            }
        ),
        FilterState(round_range=(1, 7), min_minutes=0, tournaments=("Liga 1, Apertura", "Liga 1, Clausura")),
    )

    assert summary == "Apertura + Clausura | R1-R7"


def test_render_overview_page_smoke(monkeypatch) -> None:
    bundle = _make_bundle()
    captured = {}
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: captured.setdefault("header", kwargs))
    monkeypatch.setattr(pages, "build_league_overview", lambda *args, **kwargs: "overview-data")
    monkeypatch.setattr(pages, "render_overview", lambda overview: {"type": "page", "overview": overview})

    action = pages.render_overview_page(bundle, FilterState(round_range=(1, 19), min_minutes=0), scope_summary="Apertura | R1-R19")

    assert action == {"type": "page", "overview": "overview-data"}
    assert captured["header"]["scope_summary"] == "Apertura | R1-R19"


def test_render_seasons_page_smoke(monkeypatch) -> None:
    bundle = _make_bundle()
    season_catalog = (
        SeasonDataset(
            season_year=2025,
            season_label="Liga 1 2025",
            data_dir=Path("gronestats/data/Liga 1 Peru/2025/dashboard/current"),
            manifest={"release_id": "20260403_233333"},
            validation={"status": "passed", "warnings": []},
        ),
    )
    overview = ConsolidatedSeasonOverview(
        total_seasons=1,
        total_matches=2,
        total_players=2,
        total_goals=3,
        goals_per_match=1.5,
        passed_seasons=1,
        warning_seasons=0,
        seasons_table=pd.DataFrame({"season_year": [2025], "season_label": ["Liga 1 2025"]}),
    )
    captured = {}
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: captured.setdefault("header", kwargs))
    monkeypatch.setattr(pages, "render_seasons_overview", lambda *args, **kwargs: {"type": "season"})

    action = pages.render_seasons_page(bundle, season_catalog, overview)

    assert action == {"type": "season"}
    assert captured["header"]["season_label"] == "Liga 1 2025"
    assert captured["header"]["coverage_label"] == bundle.coverage_label


def test_render_teams_page_smoke_clamps_invalid_focus(monkeypatch) -> None:
    bundle = _make_bundle()
    session_state = {"focus_team_id": 999}
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    monkeypatch.setattr(pages, "render_team_view", lambda profile, **kwargs: profile)
    captured = {}
    monkeypatch.setattr(
        pages,
        "build_team_profile",
        lambda _bundle, _filters, team_id: captured.setdefault("team_id", team_id) or {"team_id": team_id},
    )

    pages.render_teams_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura | R1-R19",
    )

    assert session_state["focus_team_id"] == 10
    assert captured["team_id"] == 10


def test_render_teams_page_passes_player_layer_flag(monkeypatch) -> None:
    bundle = _make_bundle()
    bundle = DatasetBundle(
        season_year=bundle.season_year,
        season_label=bundle.season_label,
        data_dir=bundle.data_dir,
        matches=bundle.matches,
        teams=bundle.teams,
        players=bundle.players.iloc[0:0].copy(),
        player_match=bundle.player_match.iloc[0:0].copy(),
        player_totals=bundle.player_totals,
        team_stats=bundle.team_stats,
        average_positions=bundle.average_positions,
        heatmap_points=bundle.heatmap_points,
        validation_status=bundle.validation_status,
        validation_warnings=bundle.validation_warnings,
        manifest=bundle.manifest,
        validation=bundle.validation,
        loaded_at=bundle.loaded_at,
    )
    session_state = {"focus_team_id": 10}
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    monkeypatch.setattr(pages, "build_team_profile", lambda *_args, **_kwargs: {"team_id": 10})
    captured: dict[str, object] = {}

    def _render_team_view(profile, **kwargs):
        captured["profile"] = profile
        captured.update(kwargs)
        return {"type": "team"}

    monkeypatch.setattr(pages, "render_team_view", _render_team_view)

    action = pages.render_teams_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura | R1-R19",
    )

    assert action == {"type": "team"}
    assert captured["player_layer_available"] is False


def test_render_players_page_smoke_handles_empty_table(monkeypatch) -> None:
    bundle = _make_bundle()
    session_state = {
        "players_team_filter": None,
        "players_position_filter": "Todas",
        "players_search": "",
        "focus_player_id": None,
    }
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    monkeypatch.setattr(pages, "render_section_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(pages, "build_players_table", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(pages, "render_players_table", lambda table: None)
    empty_messages: list[str] = []
    monkeypatch.setattr(pages, "render_empty_state", lambda message: empty_messages.append(message))

    action = pages.render_players_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura | R1-R19",
    )

    assert action is None
    assert empty_messages == ["Amplia filtros o reduce el minimo de minutos para ver perfiles."]


def test_render_players_page_reports_partial_season_without_player_match(monkeypatch) -> None:
    bundle = _make_bundle()
    bundle = DatasetBundle(
        season_year=bundle.season_year,
        season_label=bundle.season_label,
        data_dir=bundle.data_dir,
        matches=bundle.matches,
        teams=bundle.teams,
        players=bundle.players.iloc[0:0].copy(),
        player_match=bundle.player_match.iloc[0:0].copy(),
        player_totals=bundle.player_totals,
        team_stats=bundle.team_stats,
        average_positions=bundle.average_positions,
        heatmap_points=bundle.heatmap_points,
        validation_status=bundle.validation_status,
        validation_warnings=bundle.validation_warnings,
        manifest=bundle.manifest,
        validation=bundle.validation,
        loaded_at=bundle.loaded_at,
    )
    session_state = {
        "players_team_filter": None,
        "players_position_filter": "Todas",
        "players_search": "",
        "focus_player_id": None,
    }
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    empty_messages: list[str] = []
    monkeypatch.setattr(pages, "render_empty_state", lambda message: empty_messages.append(message))

    action = pages.render_players_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura | R1-R19",
    )

    assert action is None
    assert empty_messages == [
        "Esta temporada aun no publica `player_match`. El ranking y los perfiles se habilitan cuando entren estadisticas individuales."
    ]


def test_build_team_options_falls_back_to_match_labels_when_team_table_is_empty() -> None:
    bundle = _make_bundle()
    bundle = DatasetBundle(
        season_year=bundle.season_year,
        season_label=bundle.season_label,
        data_dir=bundle.data_dir,
        matches=bundle.matches,
        teams=bundle.teams.iloc[0:0].copy(),
        players=bundle.players,
        player_match=bundle.player_match,
        player_totals=bundle.player_totals,
        team_stats=bundle.team_stats,
        average_positions=bundle.average_positions,
        heatmap_points=bundle.heatmap_points,
        validation_status=bundle.validation_status,
        validation_warnings=bundle.validation_warnings,
        manifest=bundle.manifest,
        validation=bundle.validation,
        loaded_at=bundle.loaded_at,
    )

    team_options = build_team_options(bundle)

    assert team_options["team_id"].astype(int).tolist() == [10, 20]
    assert team_options["team_name"].tolist() == ["Alianza", "Melgar"]


def test_render_players_page_smoke_clamps_focus_before_profile(monkeypatch) -> None:
    bundle = _make_bundle()
    session_state = {
        "players_team_filter": None,
        "players_position_filter": "Todas",
        "players_search": "",
        "focus_player_id": 999,
        "player_context_match_id": None,
        "player_visual_match_id": None,
    }
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    monkeypatch.setattr(pages, "render_section_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pages,
        "build_players_table",
        lambda *args, **kwargs: pd.DataFrame(
            {
                "player_id": [1, 2],
                "name": ["Jugador A", "Jugador B"],
                "team_name": ["Alianza", "Melgar"],
                "position": ["F", "M"],
                "minutesplayed": [90, 80],
                "matches_played": [1, 1],
                "goals": [1, 0],
                "assists": [0, 1],
                "goals_per90": [1.0, 0.0],
                "assists_per90": [0.0, 1.0],
                "goal_actions_per90": [1.0, 1.0],
            }
        ),
    )
    monkeypatch.setattr(pages, "render_players_table", lambda table: None)
    captured = {}
    monkeypatch.setattr(
        pages,
        "build_player_profile",
        lambda _bundle, _filters, player_id, **kwargs: captured.setdefault("player_id", player_id) or {"player_id": player_id},
    )
    monkeypatch.setattr(pages, "render_player_profile", lambda profile: {"type": "player", "profile": profile})

    action = pages.render_players_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura | R1-R19",
    )

    assert session_state["focus_player_id"] == 1
    assert captured["player_id"] == 1
    assert action["type"] == "player"


def test_render_matches_page_smoke_clamps_focus_and_uses_scope_summary(monkeypatch) -> None:
    bundle = _make_bundle()
    session_state = {
        "matches_team_filter": None,
        "matches_venue_filter": "Todos",
        "matches_result_filter": "Todos",
        "focus_match_id": 999,
        "match_catalog_ids": [],
        "focus_match_index": 0,
    }
    _install_streamlit_stubs(monkeypatch, session_state)
    monkeypatch.setattr(pages, "render_app_header", lambda **kwargs: None)
    monkeypatch.setattr(pages, "render_section_title", lambda *args, **kwargs: None)
    monkeypatch.setattr(pages, "render_selection_note", lambda *args, **kwargs: None)
    monkeypatch.setattr(pages, "render_empty_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        pages,
        "build_match_catalog",
        lambda *args, **kwargs: pd.DataFrame(
            {
                "match_id": [10],
                "partido": ["Alianza 1 - 0 Melgar"],
                "home": ["Alianza"],
                "away": ["Melgar"],
                "round_number": [1],
                "round_label": ["Apertura Â· R1"],
                "fecha": ["01/01/2025 15:00"],
                "scoreline": ["1 - 0"],
                "estadio": ["Matute"],
                "ciudad": ["Lima"],
                "arbitro": ["A"],
            }
        ),
    )
    monkeypatch.setattr(pages, "render_match_catalog", lambda *args, **kwargs: None)
    captured = {}
    monkeypatch.setattr(
        pages,
        "build_match_summary",
        lambda _bundle, _filters, match_id, _catalog, origin_context=None: captured.setdefault("match_id", match_id) or {"match_id": match_id},
    )
    monkeypatch.setattr(pages, "render_match_detail", lambda summary: {"type": "match", "summary": summary})

    action = pages.render_matches_page(
        bundle,
        FilterState(round_range=(1, 19), min_minutes=0, tournaments=("Liga 1, Apertura", "Liga 1, Clausura")),
        [10, 20],
        {10: "Alianza", 20: "Melgar"},
        scope_summary="Apertura + Clausura | R1-R19",
    )

    assert session_state["focus_match_id"] == 10
    assert session_state["focus_match_index"] == 0
    assert captured["match_id"] == 10
    assert action["type"] == "match"
