from __future__ import annotations

import pandas as pd

from gronestats.dashboard.models import MatchSummary
from gronestats.dashboard.views.matches import build_optional_layer_empty_state, build_shotmap_panel_state
from gronestats.dashboard.views.pitch import build_match_goalmouth_figure


def _make_summary(
    *,
    season_has_shot_layer: bool,
    season_has_momentum_layer: bool,
    shot_events: pd.DataFrame | None = None,
    shot_events_metadata: dict[str, object] | None = None,
) -> MatchSummary:
    return MatchSummary(
        match_id=1,
        match_row=pd.Series({"match_id": 1, "home": "Alianza", "away": "Melgar"}),
        home_team_color="#111111",
        away_team_color="#222222",
        curated_stats=pd.DataFrame(),
        grouped_stats={},
        player_rows=pd.DataFrame(),
        standout_players=pd.DataFrame(),
        insight_cards=[],
        home_context_matches=pd.DataFrame(),
        away_context_matches=pd.DataFrame(),
        catalog_neighbors={},
        origin_context={},
        team_average_positions=pd.DataFrame(),
        average_position_metadata={},
        shot_events=shot_events if shot_events is not None else pd.DataFrame(),
        shot_events_metadata=shot_events_metadata or {},
        season_has_shot_layer=season_has_shot_layer,
        season_has_momentum_layer=season_has_momentum_layer,
    )


def test_build_optional_layer_empty_state_distinguishes_match_level_shot_gap() -> None:
    summary = _make_summary(season_has_shot_layer=True, season_has_momentum_layer=False)

    message, note = build_optional_layer_empty_state(summary, "shotmap")

    assert message == "No hay `shot_events` publicados para este match_id."
    assert note is not None
    assert "este partido" in note


def test_build_optional_layer_empty_state_distinguishes_season_level_momentum_gap() -> None:
    summary = _make_summary(season_has_shot_layer=False, season_has_momentum_layer=False)

    message, note = build_optional_layer_empty_state(summary, "momentum")

    assert message == "La temporada activa aun no publica `match_momentum`."
    assert note is None


def test_build_shotmap_panel_state_prefers_goal_mouth_when_pitch_coordinates_are_missing() -> None:
    summary = _make_summary(
        season_has_shot_layer=True,
        season_has_momentum_layer=False,
        shot_events=pd.DataFrame({"match_id": [1]}),
        shot_events_metadata={
            "has_pitch_map": False,
            "has_goal_mouth_map": True,
            "pitch_event_count": 0,
            "goal_mouth_event_count": 14,
        },
    )

    state = build_shotmap_panel_state(summary)

    assert state["show_empty"] is False
    assert state["has_pitch_map"] is False
    assert state["has_goal_mouth_map"] is True
    assert "solo visual de arco" in str(state["note"])


def test_build_shotmap_panel_state_marks_empty_when_events_have_no_usable_geometry() -> None:
    summary = _make_summary(
        season_has_shot_layer=True,
        season_has_momentum_layer=False,
        shot_events=pd.DataFrame({"match_id": [1]}),
        shot_events_metadata={
            "has_pitch_map": False,
            "has_goal_mouth_map": False,
            "pitch_event_count": 0,
            "goal_mouth_event_count": 0,
        },
    )

    state = build_shotmap_panel_state(summary)

    assert state["show_empty"] is True
    assert "geometria usable" in str(state["note"]).lower()
    assert "coordenadas utilizables" in str(state["message"]).lower()


def test_build_match_goalmouth_figure_renders_when_goal_mouth_coordinates_exist() -> None:
    shot_events = pd.DataFrame(
        {
            "side": ["Local", "Visita"],
            "goal_mouth_y": [48.4, 54.0],
            "goal_mouth_z": [19.0, 2.5],
            "has_goal_mouth_coordinates": [True, True],
            "shot_type_norm": ["save", "goal"],
            "shot_type": ["save", "goal"],
            "minute_label": ["11", "20"],
            "name": ["Jugador A", "Jugador B"],
            "team_name": ["Alianza", "Melgar"],
            "goal_mouth_location": ["low-centre", "low-left"],
            "situation": ["regular", "regular"],
            "body_part": ["left-foot", "right-foot"],
        }
    )

    figure = build_match_goalmouth_figure(
        shot_events,
        home_team="Alianza",
        away_team="Melgar",
        metadata={"home_shots": 1, "home_on_target": 1, "home_goals": 0, "away_shots": 1, "away_on_target": 1, "away_goals": 1},
    )

    assert len(figure.data) == 2
    assert figure.layout.title.text == "Definiciones sobre el arco"
