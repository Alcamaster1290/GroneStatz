from __future__ import annotations

from datetime import datetime

import pandas as pd

from gronestats.dashboard.data import filter_regular_season_matches, normalize_matches
from gronestats.dashboard.metrics import (
    PLAYER_ACCUMULATED_SCOPE,
    add_per90_metrics,
    build_catalog_neighbors,
    build_league_overview,
    build_match_insight_cards,
    build_match_player_rows,
    build_match_standout_players,
    build_match_team_average_positions,
    build_leaderboards,
    build_player_profile,
    build_player_visual_matches,
    build_players_table,
    build_team_context_matches,
    calculate_standings,
    calculate_team_splits,
)
from gronestats.dashboard.models import DatasetBundle, FilterState


def _make_dashboard_bundle(
    *,
    player_match: pd.DataFrame,
    players: pd.DataFrame | None = None,
    teams: pd.DataFrame | None = None,
    matches: pd.DataFrame | None = None,
    average_positions: pd.DataFrame | None = None,
    heatmap_points: pd.DataFrame | None = None,
) -> DatasetBundle:
    player_match_work = player_match.copy()
    for column, default in {
        "fecha_dt": pd.Timestamp("2025-01-01"),
        "home": "Alianza",
        "away": "Melgar",
        "scoreline": "1 - 0",
    }.items():
        if column not in player_match_work.columns:
            player_match_work[column] = default

    return DatasetBundle(
        matches=matches
        if matches is not None
        else pd.DataFrame(
            {
                "match_id": [1],
                "round_number": [1],
                "tournament": ["Liga 1, Apertura"],
                "tournament_label": ["Apertura"],
                "round_label": ["Apertura · R1"],
                "fecha_dt": pd.to_datetime(["2025-01-01"]),
                "home_id": [10],
                "away_id": [20],
                "home": ["Alianza"],
                "away": ["Melgar"],
                "home_score": [1],
                "away_score": [0],
                "scoreline": ["1 - 0"],
            }
        ),
        teams=teams if teams is not None else pd.DataFrame({"team_id": [10, 20], "team_name": ["Alianza", "Melgar"]}),
        players=players
        if players is not None
        else pd.DataFrame(
            {
                "player_id": [1, 2],
                "name": ["Jugador Valido", None],
                "short_name": ["Jugador Valido", None],
                "position": ["F", None],
                "team_id": [10, None],
            }
        ),
        player_match=player_match_work,
        player_totals=pd.DataFrame(),
        team_stats=pd.DataFrame(),
        average_positions=average_positions if average_positions is not None else pd.DataFrame(),
        heatmap_points=heatmap_points if heatmap_points is not None else pd.DataFrame(),
        loaded_at=datetime(2026, 3, 12, 12, 0, 0),
    )


def test_calculate_standings_builds_expected_table() -> None:
    matches = pd.DataFrame(
        {
            "match_id": [1, 2, 3],
            "round_number": [1, 1, 2],
            "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
            "home_id": [10, 30, 20],
            "away_id": [20, 10, 30],
            "home": ["Alianza", "Cristal", "Melgar"],
            "away": ["Melgar", "Alianza", "Cristal"],
            "home_score": [2, 1, 0],
            "away_score": [0, 1, 3],
            "scoreline": ["2 - 0", "1 - 1", "0 - 3"],
        }
    )

    standings = calculate_standings(matches)

    assert standings.iloc[0]["team_name"] == "Cristal"
    assert standings.iloc[0]["Pts"] == 4
    assert standings.iloc[1]["team_name"] == "Alianza"
    assert standings.iloc[1]["Pts"] == 4
    assert standings.iloc[2]["team_name"] == "Melgar"
    assert standings.iloc[2]["Pts"] == 0


def test_calculate_team_splits_separates_home_and_away() -> None:
    team_rows = pd.DataFrame(
        {
            "match_id": [1, 2, 3],
            "venue": ["Local", "Visita", "Local"],
            "points": [3, 1, 0],
            "goals_for": [2, 1, 0],
            "goals_against": [0, 1, 1],
        }
    )

    splits = calculate_team_splits(team_rows).set_index("venue")

    assert splits.loc["Local", "matches"] == 2
    assert splits.loc["Local", "points"] == 3
    assert splits.loc["Visita", "ppg"] == 1.0


def test_add_per90_metrics_handles_zero_minutes() -> None:
    frame = pd.DataFrame(
        {
            "minutesplayed": [90, 180, 0],
            "goals": [1, 2, 3],
            "assists": [0, 1, 2],
            "saves": [0, 5, 1],
            "fouls": [1, 2, 3],
        }
    )

    result = add_per90_metrics(frame)

    assert result.loc[0, "goals_per90"] == 1.0
    assert result.loc[1, "assists_per90"] == 0.5
    assert result.loc[2, "goal_actions_per90"] == 0.0


def test_build_leaderboards_returns_expected_sections() -> None:
    players = pd.DataFrame(
        {
            "name": ["A", "B", "C"],
            "team_name": ["X", "Y", "Z"],
            "goals": [5, 2, 1],
            "assists": [1, 4, 0],
            "minutesplayed": [500, 450, 120],
            "matches_played": [6, 6, 2],
        }
    )

    leaders = build_leaderboards(players)

    assert list(leaders.keys()) == ["Goles", "Asistencias", "Minutos"]
    assert leaders["Goles"].iloc[0]["Jugador"] == "A"
    assert leaders["Asistencias"].iloc[0]["Jugador"] == "B"
    assert leaders["Minutos"].iloc[0]["Jugador"] == "A"


def test_build_catalog_neighbors_tracks_previous_and_next() -> None:
    catalog = pd.DataFrame(
        {
            "match_id": [10, 20, 30],
            "partido": ["A vs B", "B vs C", "C vs D"],
        }
    )

    neighbors = build_catalog_neighbors(catalog, 20)

    assert neighbors["current_index"] == 1
    assert neighbors["previous_match_id"] == 10
    assert neighbors["next_match_id"] == 30


def test_build_team_context_matches_marks_before_and_after() -> None:
    matches = pd.DataFrame(
        {
            "match_id": [1, 2, 3, 4, 5],
            "round_number": [1, 2, 3, 4, 5],
            "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08", "2025-01-15", "2025-01-22", "2025-01-29"]),
            "home_id": [1, 2, 1, 3, 1],
            "away_id": [2, 1, 3, 1, 2],
            "home": ["A", "B", "A", "C", "A"],
            "away": ["B", "A", "C", "A", "B"],
            "home_score": [1, 0, 2, 1, 3],
            "away_score": [0, 1, 1, 1, 0],
            "scoreline": ["1 - 0", "0 - 1", "2 - 1", "1 - 1", "3 - 0"],
        }
    )

    context = build_team_context_matches(matches, team_id=1, match_id=3, limit=4)

    assert context["Relacion"].tolist() == ["2 antes", "1 antes", "1 despues", "2 despues"]
    assert 3 not in context["match_id"].tolist()


def test_build_players_table_excludes_players_without_usable_name() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 1],
                "player_id": [1, 2],
                "team_id": [10, None],
                "name": ["Jugador Valido", None],
                "position": ["F", None],
                "rating": [7.2, 6.5],
                "minutesplayed": [90, 90],
                "goals": [1, 3],
                "assists": [0, 0],
                "saves": [0, 0],
                "fouls": [1, 1],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            }
        )
    )

    table = build_players_table(bundle, FilterState(round_range=(1, 1), min_minutes=0))

    assert table["player_id"].tolist() == [1]
    assert table.iloc[0]["name"] == "Jugador Valido"


def test_build_player_profile_returns_none_for_player_without_identity() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [2],
                "team_id": [None],
                "name": [None],
                "position": [None],
                "rating": [6.5],
                "minutesplayed": [90],
                "goals": [0],
                "assists": [0],
                "saves": [0],
                "fouls": [1],
                "penaltywon": [0],
                "penaltysave": [0],
                "penaltyconceded": [0],
                "fecha_dt": pd.to_datetime(["2025-01-01"]),
            }
        ),
        players=pd.DataFrame({"player_id": [2], "name": [None], "short_name": [None], "position": [None], "team_id": [None]}),
    )

    profile = build_player_profile(bundle, FilterState(round_range=(1, 1), min_minutes=0), player_id=2)

    assert profile is None


def test_build_match_player_rows_keeps_named_rows_without_team_as_non_navigable() -> None:
    player_match = pd.DataFrame(
        {
            "match_id": [1, 1],
            "player_id": [10, 11],
            "team_id": [1, None],
            "name": ["Jugador Local", "Dato suelto"],
            "position": ["F", "M"],
            "minutesplayed": [90, 30],
            "goals": [1, 0],
            "assists": [0, 1],
            "saves": [0, 0],
            "fouls": [1, 0],
            "rating": [7.3, 6.0],
        }
    )
    match_row = pd.Series({"match_id": 1, "home_id": 1, "away_id": 2, "home": "Alianza", "away": "Melgar"})

    rows = build_match_player_rows(player_match, match_row)

    assert rows["name"].tolist() == ["Jugador Local", "Dato suelto"]
    assert rows["is_navigable"].tolist() == [True, False]
    assert rows.iloc[1]["team_name"] == "Sin equipo"
    assert rows.iloc[1]["side"] == "Sin lado"


def test_build_match_standout_players_ignores_non_navigable_candidates() -> None:
    player_rows = pd.DataFrame(
        {
            "side": ["Local", "Local", "Visita"],
            "player_id": [1, 2, 3],
            "team_id": [10, None, 20],
            "name": ["Valido", "Fantasma", "Visita"],
            "position": ["F", "F", "M"],
            "goals": [1, 4, 0],
            "assists": [0, 0, 1],
            "rating": [7.1, 8.0, 7.4],
            "minutesplayed": [90, 90, 90],
            "impact": [1, 4, 1],
            "is_navigable": [True, False, True],
        }
    )

    standout = build_match_standout_players(player_rows)

    assert standout["name"].tolist() == ["Valido", "Visita"]
    assert standout["player_id"].tolist() == [1, 3]


def test_build_match_insight_cards_degrades_without_standout_players() -> None:
    cards = build_match_insight_cards(
        pd.Series({"match_id": 1, "home_score": 2, "away_score": 1}),
        pd.DataFrame(),
        pd.DataFrame(),
    )

    assert cards[2]["value"] == "Sin figura clara"
    assert cards[3]["value"] == "Sin figura clara"


def test_build_player_visual_matches_returns_only_matches_with_positional_data() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame({"match_id": [1, 2]}),
        matches=pd.DataFrame(
            {
                "match_id": [1, 2, 3, 99],
                "round_number": [1, 2, 3, 28],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08", "2025-01-15", "2025-07-20"]),
                "home_id": [10, 10, 10, 10],
                "away_id": [20, 30, 40, 50],
                "home": ["Alianza", "Alianza", "Alianza", "Alianza"],
                "away": ["Melgar", "Cristal", "Cusco", "Universitario"],
                "home_score": [1, 2, 3, 1],
                "away_score": [0, 1, 2, 1],
                "scoreline": ["1 - 0", "2 - 1", "3 - 2", "1 - 1"],
            }
        ),
        average_positions=pd.DataFrame({"match_id": [1], "player_id": [1], "average_x": [45.0], "average_y": [51.0]}),
        heatmap_points=pd.DataFrame({"match_id": [2, 99], "player_id": [1, 1], "x": [30.0, 45.0], "y": [50.0, 52.0]}),
    )

    visual_matches = build_player_visual_matches(bundle, FilterState(round_range=(1, 20), min_minutes=0), player_id=1)

    assert visual_matches["match_id"].tolist() == [2, 1]
    assert visual_matches["has_average_position"].tolist() == [False, True]
    assert visual_matches["has_heatmap"].tolist() == [True, False]


def test_build_player_profile_prefers_context_match_for_visual_panel() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "name": ["Jugador Valido", "Jugador Valido"],
                "position": ["F", "F"],
                "rating": [7.2, 7.1],
                "minutesplayed": [90, 90],
                "goals": [1, 0],
                "assists": [0, 1],
                "saves": [0, 0],
                "fouls": [1, 1],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
                "home": ["Alianza", "Melgar"],
                "away": ["Melgar", "Alianza"],
                "scoreline": ["1 - 0", "0 - 1"],
            }
        ),
        average_positions=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "team_name": ["Alianza", "Alianza"],
                "name": ["Jugador Valido", "Jugador Valido"],
                "shirt_number": [9, 9],
                "position": ["F", "F"],
                "average_x": [44.0, 52.0],
                "average_y": [49.0, 58.0],
                "points_count": [24, 18],
                "is_starter": [True, True],
            }
        ),
        heatmap_points=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "x": [28.0, 30.0],
                "y": [53.0, 55.0],
            }
        ),
        matches=pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 2],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
                "home_id": [10, 20],
                "away_id": [20, 10],
                "home": ["Alianza", "Melgar"],
                "away": ["Melgar", "Alianza"],
                "home_score": [1, 0],
                "away_score": [0, 1],
                "scoreline": ["1 - 0", "0 - 1"],
            }
        ),
    )

    profile = build_player_profile(
        bundle,
        FilterState(round_range=(1, 2), min_minutes=0),
        player_id=1,
        context_match_id=2,
    )

    assert profile is not None
    assert profile.default_visual_match_id == 2
    assert profile.default_visual_scope == "Partido contextual"
    assert profile.contextual_average_position_row is not None
    assert int(profile.contextual_average_position_row["match_id"]) == 2
    assert len(profile.contextual_heatmap_points) == 1
    assert len(profile.accumulated_heatmap_points) == 2
    assert profile.accumulated_average_position_row is not None


def test_build_player_profile_excludes_rating_from_summary_and_percentiles() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [1],
                "team_id": [10],
                "name": ["Jugador Valido"],
                "position": ["F"],
                "rating": [7.2],
                "minutesplayed": [90],
                "goals": [1],
                "assists": [1],
                "saves": [0],
                "fouls": [1],
                "penaltywon": [0],
                "penaltysave": [0],
                "penaltyconceded": [0],
                "fecha_dt": pd.to_datetime(["2025-01-01"]),
            }
        )
    )

    profile = build_player_profile(bundle, FilterState(round_range=(1, 1), min_minutes=0), player_id=1)

    assert profile is not None
    assert "Rating" not in profile.summary
    assert "Rating" not in profile.percentiles["Metric"].tolist()


def test_build_player_profile_builds_weighted_accumulated_average_position() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "name": ["Jugador Valido", "Jugador Valido"],
                "position": ["F", "F"],
                "rating": [7.0, 7.1],
                "minutesplayed": [90, 90],
                "goals": [1, 0],
                "assists": [0, 1],
                "saves": [0, 0],
                "fouls": [1, 1],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
            }
        ),
        average_positions=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "team_name": ["Alianza", "Alianza"],
                "name": ["Jugador Valido", "Jugador Valido"],
                "shirt_number": [9, 9],
                "position": ["F", "F"],
                "average_x": [10.0, 30.0],
                "average_y": [20.0, 40.0],
                "points_count": [10, 30],
                "is_starter": [True, True],
            }
        ),
        matches=pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 2],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
                "home_id": [10, 20],
                "away_id": [20, 10],
                "home": ["Alianza", "Melgar"],
                "away": ["Melgar", "Alianza"],
                "home_score": [1, 0],
                "away_score": [0, 1],
                "scoreline": ["1 - 0", "0 - 1"],
            }
        ),
    )

    profile = build_player_profile(bundle, FilterState(round_range=(1, 2), min_minutes=0), player_id=1)

    assert profile is not None
    assert profile.accumulated_average_position_row is not None
    assert round(float(profile.accumulated_average_position_row["average_x"]), 2) == 25.0
    assert round(float(profile.accumulated_average_position_row["average_y"]), 2) == 35.0
    assert int(profile.accumulated_average_position_row["matches_count"]) == 2
    assert int(profile.accumulated_average_position_row["points_count_total"]) == 40


def test_build_player_profile_defaults_to_accumulated_when_context_has_no_visuals() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "name": ["Jugador Valido", "Jugador Valido"],
                "position": ["F", "F"],
                "rating": [7.2, 7.1],
                "minutesplayed": [90, 90],
                "goals": [1, 0],
                "assists": [0, 1],
                "saves": [0, 0],
                "fouls": [1, 1],
                "penaltywon": [0, 0],
                "penaltysave": [0, 0],
                "penaltyconceded": [0, 0],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
            }
        ),
        average_positions=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [1],
                "team_id": [10],
                "team_name": ["Alianza"],
                "name": ["Jugador Valido"],
                "shirt_number": [9],
                "position": ["F"],
                "average_x": [44.0],
                "average_y": [49.0],
                "points_count": [24],
                "is_starter": [True],
            }
        ),
        heatmap_points=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [1],
                "team_id": [10],
                "x": [28.0],
                "y": [53.0],
            }
        ),
        matches=pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 2],
                "fecha_dt": pd.to_datetime(["2025-01-01", "2025-01-08"]),
                "home_id": [10, 20],
                "away_id": [20, 10],
                "home": ["Alianza", "Melgar"],
                "away": ["Melgar", "Alianza"],
                "home_score": [1, 0],
                "away_score": [0, 1],
                "scoreline": ["1 - 0", "0 - 1"],
            }
        ),
    )

    profile = build_player_profile(
        bundle,
        FilterState(round_range=(1, 2), min_minutes=0),
        player_id=1,
        context_match_id=2,
    )

    assert profile is not None
    assert profile.default_visual_scope == PLAYER_ACCUMULATED_SCOPE
    assert profile.contextual_average_position_row is None
    assert profile.contextual_heatmap_points.empty
    assert profile.accumulated_average_position_row is not None


def test_build_match_standout_players_breaks_ties_without_rating() -> None:
    player_rows = pd.DataFrame(
        {
            "side": ["Local", "Local"],
            "player_id": [1, 2],
            "team_id": [10, 10],
            "name": ["Jugador A", "Jugador B"],
            "position": ["F", "F"],
            "goals": [1, 1],
            "assists": [0, 0],
            "minutesplayed": [70, 90],
            "impact": [1, 1],
            "is_navigable": [True, True],
        }
    )

    standout = build_match_standout_players(player_rows)

    assert standout.iloc[0]["name"] == "Jugador B"


def test_filter_regular_season_matches_excludes_playoff_rounds() -> None:
    matches = pd.DataFrame(
        {
            "match_id": [1, 2, 3, 4],
            "round_number": [19, 1, 19, 28],
            "tournament": [
                "Liga 1, Apertura",
                "Liga 1, Clausura",
                "Liga 1, Clausura",
                "Primera Division, Grand Final",
            ],
            "home": ["A", "B", "C", "H"],
            "away": ["D", "E", "F", "G"],
        }
    )

    result = filter_regular_season_matches(matches)

    assert result["match_id"].tolist() == [1, 2, 3]
    assert "Primera Division, Grand Final" not in result["tournament"].tolist()


def test_normalize_matches_preserves_tournament_and_builds_round_label() -> None:
    matches = pd.DataFrame(
        {
            "match_id": [1, 2],
            "round_number": [1, 1],
            "tournament": ["Liga 1, Apertura", "Liga 1, Clausura"],
            "fecha": ["01/01/2025 15:00", "02/01/2025 18:00"],
            "home_id": [10, 20],
            "away_id": [20, 10],
            "home": ["Alianza", "Melgar"],
            "away": ["Melgar", "Alianza"],
            "home_score": [1, 0],
            "away_score": [0, 1],
        }
    )

    normalized = normalize_matches(matches)

    assert normalized["tournament"].tolist() == ["Liga 1, Apertura", "Liga 1, Clausura"]
    assert normalized["tournament_label"].tolist() == ["Apertura", "Clausura"]
    assert normalized["round_label"].tolist() == ["Apertura · R1", "Clausura · R1"]


def test_build_league_overview_does_not_collapse_duplicate_rounds_between_tournaments() -> None:
    matches = normalize_matches(
        pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 1],
                "tournament": ["Liga 1, Apertura", "Liga 1, Clausura"],
                "fecha": ["01/01/2025 15:00", "02/07/2025 18:00"],
                "home_id": [10, 20],
                "away_id": [20, 10],
                "home": ["Alianza", "Melgar"],
                "away": ["Melgar", "Alianza"],
                "home_score": [1, 2],
                "away_score": [0, 1],
                "estadio": ["A", "B"],
                "ciudad": ["Lima", "Arequipa"],
                "arbitro": ["X", "Y"],
            }
        )
    )
    bundle = _make_dashboard_bundle(player_match=pd.DataFrame(), matches=matches)

    overview = build_league_overview(
        bundle,
        FilterState(round_range=(1, 1), min_minutes=0, tournaments=("Liga 1, Apertura", "Liga 1, Clausura")),
    )

    assert overview.goals_by_round["round_label"].tolist() == ["Apertura · R1", "Clausura · R1"]
    assert overview.goals_by_round["goals"].tolist() == [1, 3]


def test_build_match_team_average_positions_falls_back_to_minutes_when_starter_flag_missing() -> None:
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 1, 1, 1],
                "player_id": [101, 102, 201, 202],
                "team_id": [10, 10, 20, 20],
                "name": ["A", "B", "C", "D"],
                "position": ["F", "M", "F", "M"],
                "minutesplayed": [90, 84, 90, 82],
                "goals": [0, 0, 0, 0],
                "assists": [0, 0, 0, 0],
                "saves": [0, 0, 0, 0],
                "fouls": [0, 0, 0, 0],
                "rating": [7.0, 6.8, 7.1, 6.6],
            }
        ),
        average_positions=pd.DataFrame(
            {
                "match_id": [1, 1, 1, 1],
                "player_id": [101, 102, 201, 202],
                "team_id": [10, 10, 20, 20],
                "team_name": ["Alianza", "Alianza", "Melgar", "Melgar"],
                "name": ["A", "B", "C", "D"],
                "shirt_number": [9, 8, 9, 8],
                "position": ["F", "M", "F", "M"],
                "average_x": [45.0, 52.0, 44.0, 48.0],
                "average_y": [48.0, 54.0, 49.0, 57.0],
                "points_count": [20, 18, 22, 17],
                "is_starter": [pd.NA, pd.NA, pd.NA, pd.NA],
            }
        ),
    )
    player_rows = build_match_player_rows(
        bundle.player_match,
        pd.Series({"match_id": 1, "home_id": 10, "away_id": 20, "home": "Alianza", "away": "Melgar"}),
    )

    positions, metadata = build_match_team_average_positions(
        bundle,
        pd.Series({"match_id": 1, "home_id": 10, "away_id": 20, "home": "Alianza", "away": "Melgar"}),
        player_rows,
    )

    assert len(positions) == 4
    assert metadata["home_strategy"] == "minutos"
    assert metadata["away_strategy"] == "minutos"


def test_build_player_profile_accumulated_scope_uses_regular_tournaments_even_if_filter_is_playoff_only() -> None:
    matches = normalize_matches(
        pd.DataFrame(
            {
                "match_id": [1, 2],
                "round_number": [1, 28],
                "tournament": ["Liga 1, Apertura", "Primera Division, Grand Final"],
                "fecha": ["01/01/2025 15:00", "20/12/2025 20:00"],
                "home_id": [10, 10],
                "away_id": [20, 20],
                "home": ["Alianza", "Alianza"],
                "away": ["Melgar", "Melgar"],
                "home_score": [1, 2],
                "away_score": [0, 1],
                "estadio": ["Matute", "Matute"],
                "ciudad": ["Lima", "Lima"],
                "arbitro": ["A", "B"],
            }
        )
    )
    bundle = _make_dashboard_bundle(
        player_match=pd.DataFrame(
            {
                "match_id": [1, 2],
                "player_id": [1, 1],
                "team_id": [10, 10],
                "name": ["Jugador Valido", "Jugador Valido"],
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
        ),
        matches=matches,
        average_positions=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [1],
                "team_id": [10],
                "team_name": ["Alianza"],
                "name": ["Jugador Valido"],
                "shirt_number": [9],
                "position": ["F"],
                "average_x": [44.0],
                "average_y": [49.0],
                "points_count": [24],
                "is_starter": [True],
            }
        ),
        heatmap_points=pd.DataFrame(
            {
                "match_id": [1],
                "player_id": [1],
                "team_id": [10],
                "team_name": ["Alianza"],
                "name": ["Jugador Valido"],
                "x": [28.0],
                "y": [53.0],
            }
        ),
    )

    profile = build_player_profile(
        bundle,
        FilterState(round_range=(1, 28), min_minutes=0, tournaments=("Primera Division, Grand Final",)),
        player_id=1,
        context_match_id=2,
    )

    assert profile is not None
    assert profile.default_visual_scope == PLAYER_ACCUMULATED_SCOPE
    assert profile.accumulated_average_position_row is not None
    assert int(profile.accumulated_average_position_row["matches_count"]) == 1
    assert profile.visual_coverage["regular_average_match_count"] == 1
    assert profile.visual_coverage["regular_heatmap_match_count"] == 1
