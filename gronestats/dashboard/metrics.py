from __future__ import annotations

from collections import OrderedDict
import re

import pandas as pd

from gronestats.dashboard.config import COLORS, DEFAULT_DASHBOARD_TOURNAMENTS, PREFERRED_MATCH_STATS, RECENT_FORM_MATCHES, REGULAR_SEASON_MAX_ROUND, TOP_FORM_TEAMS
from gronestats.dashboard.models import DatasetBundle, FilterState, LeagueOverview, MatchSummary, PlayerProfile, TeamProfile


PLAYER_TOTAL_COLUMNS = [
    "minutesplayed",
    "matches_played",
    "goals",
    "assists",
    "saves",
    "fouls",
    "penaltywon",
    "penaltysave",
    "penaltyconceded",
]

PLAYER_AVERAGE_POSITION_MODE = "Mostrar solo posicion promedio"
PLAYER_HEATMAP_MODE = "Mostrar solo heatmap"
PLAYER_CONTEXTUAL_SCOPE = "Partido contextual"
PLAYER_ACCUMULATED_SCOPE = "Acumulado del tramo regular"

MATCH_STAT_GROUP_ORDER = [
    "Match overview",
    "Shots",
    "Attack",
    "Passes",
    "Defending",
    "Duels",
    "Goalkeeping",
    "Discipline",
]

HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def _format_stat_value(value: object, is_percent: bool = False) -> str:
    if pd.isna(value):
        return "-"
    numeric = float(value)
    if is_percent:
        return f"{numeric:.0f}%"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def _normalize_team_color(value: object, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if HEX_COLOR_PATTERN.match(text):
        return text.lower()
    return fallback


def _resolve_team_color(teams: pd.DataFrame, team_id: int | None, fallback: str) -> str:
    if team_id is None or teams.empty or "team_colors" not in teams.columns:
        return fallback
    subset = teams.loc[teams["team_id"] == team_id, "team_colors"]
    if subset.empty:
        return fallback
    return _normalize_team_color(subset.iloc[0], fallback)


def _is_percent_stat(row: pd.Series) -> bool:
    render_type = pd.to_numeric(pd.Series([row.get("RENDERTYPE")]), errors="coerce").fillna(0).iloc[0]
    key = str(row.get("KEY", "")).lower()
    return bool(render_type == 2 or "percent" in key or "percentage" in key or key == "ballpossession")


def _clean_stat_label(row: pd.Series) -> str:
    label = row.get("name")
    if pd.notna(label):
        return str(label)
    key = str(row.get("KEY", "")).strip()
    if not key:
        return "Sin etiqueta"
    return re.sub(r"(?<!^)([A-Z])", r" \1", key).strip().capitalize()


def _has_usable_text(value: object) -> bool:
    if value is None or pd.isna(value):
        return False
    text = str(value).strip()
    return bool(text) and text.lower() != "nan"


def _safe_text(value: object, fallback: str) -> str:
    return str(value).strip() if _has_usable_text(value) else fallback


def _safe_float(value: object, default: float = 0.0) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0]
    return float(numeric)


def _safe_int(value: object) -> int:
    return int(round(_safe_float(value, default=0.0)))


def _safe_optional_int(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return int(float(numeric))


def _build_match_label(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    work["partido"] = work["home"] + " " + work["scoreline"] + " " + work["away"]
    if "round_label" not in work.columns:
        work["round_label"] = work["round_number"].map(lambda value: f"R{_safe_int(value)}")
    return work


def _filter_presentable_players(frame: pd.DataFrame, *, require_team: bool = False) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    work = frame.copy()
    mask = work["player_id"].notna() if "player_id" in work.columns else pd.Series(False, index=work.index)
    if "name" in work.columns:
        mask &= work["name"].map(_has_usable_text)
    else:
        mask &= False
    if require_team:
        mask &= work["team_id"].notna() if "team_id" in work.columns else False
    return work.loc[mask].reset_index(drop=True)


def apply_match_filters(matches: pd.DataFrame, filters: FilterState) -> pd.DataFrame:
    if matches.empty:
        return matches
    work = matches.copy()
    if filters.tournaments and "tournament" in work.columns:
        work = work[work["tournament"].isin(filters.tournaments)]
    start_round, end_round = filters.round_range
    if "round_number" in work.columns:
        work = work[work["round_number"].between(start_round, end_round)]
    return work.copy()


def apply_regular_season_filters(matches: pd.DataFrame, filters: FilterState) -> pd.DataFrame:
    if matches.empty:
        return matches
    work = matches.copy()
    if "tournament" in work.columns and work["tournament"].notna().any():
        allowed = [tournament for tournament in DEFAULT_DASHBOARD_TOURNAMENTS if tournament in set(work["tournament"].dropna().astype(str))]
        if allowed:
            work = work[work["tournament"].isin(allowed)]
    elif "round_number" in work.columns:
        work = work[work["round_number"] <= REGULAR_SEASON_MAX_ROUND]

    start_round, end_round = filters.round_range
    if "round_number" in work.columns:
        work = work[work["round_number"].between(start_round, end_round)]
    return work.copy()


def _format_pair(home_value: object, away_value: object, is_percent: bool = False) -> str:
    return f"{_format_stat_value(home_value, is_percent=is_percent)} vs {_format_stat_value(away_value, is_percent=is_percent)}"


def _group_rank(value: object) -> tuple[int, str]:
    label = str(value) if pd.notna(value) else "Otros"
    try:
        return (MATCH_STAT_GROUP_ORDER.index(label), label)
    except ValueError:
        return (len(MATCH_STAT_GROUP_ORDER), label)


def _build_match_stat_subset(team_stats: pd.DataFrame, match_id: int) -> pd.DataFrame:
    if team_stats.empty:
        return pd.DataFrame()
    subset = team_stats[team_stats["match_id"] == match_id].copy()
    if subset.empty:
        return pd.DataFrame()
    subset["group_rank"] = subset["GROUP"].map(lambda value: _group_rank(value)[0])
    subset["group_label"] = subset["GROUP"].fillna("Otros").astype(str)
    return subset.sort_values(["group_rank", "group_label", "name", "KEY"], kind="mergesort").reset_index(drop=True)


def _build_match_stat_lookup(team_stats: pd.DataFrame, match_id: int) -> pd.DataFrame:
    subset = _build_match_stat_subset(team_stats, match_id)
    if subset.empty:
        return pd.DataFrame()
    return subset.drop_duplicates(subset=["KEY"], keep="first").set_index("KEY", drop=False)


def _get_match_stat_pair(lookup: pd.DataFrame, key: str) -> tuple[object, object]:
    if lookup.empty or key not in lookup.index:
        return (pd.NA, pd.NA)
    row = lookup.loc[key]
    home_value = row["HOMEVALUE"] if pd.notna(row.get("HOMEVALUE")) else row.get("HOMETOTAL")
    away_value = row["AWAYVALUE"] if pd.notna(row.get("AWAYVALUE")) else row.get("AWAYTOTAL")
    return (home_value, away_value)


def apply_round_filter(matches: pd.DataFrame, round_range: tuple[int, int]) -> pd.DataFrame:
    if matches.empty:
        return matches
    start_round, end_round = round_range
    mask = matches["round_number"].between(start_round, end_round)
    return matches.loc[mask].copy()


def build_team_match_rows(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()

    completed = matches.dropna(subset=["home_score", "away_score"]).copy()
    if completed.empty:
        return completed

    home = pd.DataFrame(
        {
            "match_id": completed["match_id"],
            "round_number": completed["round_number"],
            "tournament": completed["tournament"] if "tournament" in completed.columns else pd.NA,
            "tournament_label": completed["tournament_label"] if "tournament_label" in completed.columns else pd.NA,
            "round_label": completed["round_label"] if "round_label" in completed.columns else completed["round_number"].map(lambda value: f"R{int(value)}"),
            "fecha_dt": completed["fecha_dt"],
            "team_id": completed["home_id"],
            "team_name": completed["home"],
            "opponent_id": completed["away_id"],
            "opponent_name": completed["away"],
            "venue": "Local",
            "goals_for": completed["home_score"].astype(int),
            "goals_against": completed["away_score"].astype(int),
            "scoreline": completed["scoreline"],
        }
    )
    away = pd.DataFrame(
        {
            "match_id": completed["match_id"],
            "round_number": completed["round_number"],
            "tournament": completed["tournament"] if "tournament" in completed.columns else pd.NA,
            "tournament_label": completed["tournament_label"] if "tournament_label" in completed.columns else pd.NA,
            "round_label": completed["round_label"] if "round_label" in completed.columns else completed["round_number"].map(lambda value: f"R{int(value)}"),
            "fecha_dt": completed["fecha_dt"],
            "team_id": completed["away_id"],
            "team_name": completed["away"],
            "opponent_id": completed["home_id"],
            "opponent_name": completed["home"],
            "venue": "Visita",
            "goals_for": completed["away_score"].astype(int),
            "goals_against": completed["home_score"].astype(int),
            "scoreline": completed["scoreline"],
        }
    )
    rows = pd.concat([home, away], ignore_index=True)
    rows["goal_difference"] = rows["goals_for"] - rows["goals_against"]
    rows["result"] = rows["goal_difference"].map(lambda value: "W" if value > 0 else "D" if value == 0 else "L")
    rows["points"] = rows["result"].map({"W": 3, "D": 1, "L": 0}).astype(int)
    rows["fixture_label"] = rows["team_name"] + " vs " + rows["opponent_name"]
    return rows.sort_values(["fecha_dt", "match_id", "team_name"]).reset_index(drop=True)


def calculate_standings(matches: pd.DataFrame) -> pd.DataFrame:
    team_rows = build_team_match_rows(matches)
    if team_rows.empty:
        return pd.DataFrame()

    standings = (
        team_rows.groupby(["team_id", "team_name"], dropna=False)
        .agg(
            PJ=("match_id", "nunique"),
            G=("result", lambda values: int((values == "W").sum())),
            E=("result", lambda values: int((values == "D").sum())),
            P=("result", lambda values: int((values == "L").sum())),
            GF=("goals_for", "sum"),
            GC=("goals_against", "sum"),
            Pts=("points", "sum"),
        )
        .reset_index()
    )
    standings["DG"] = standings["GF"] - standings["GC"]
    standings["PPG"] = (standings["Pts"] / standings["PJ"]).round(2)
    standings = standings.sort_values(
        ["Pts", "DG", "GF", "team_name"],
        ascending=[False, False, False, True],
        kind="mergesort",
    ).reset_index(drop=True)
    standings.insert(0, "Pos", range(1, len(standings) + 1))
    return standings


def calculate_team_splits(team_rows: pd.DataFrame) -> pd.DataFrame:
    if team_rows.empty:
        return pd.DataFrame(columns=["venue", "matches", "points", "goals_for", "goals_against", "ppg", "gf_pg", "ga_pg"])

    splits = (
        team_rows.groupby("venue", dropna=False)
        .agg(
            matches=("match_id", "nunique"),
            points=("points", "sum"),
            goals_for=("goals_for", "sum"),
            goals_against=("goals_against", "sum"),
        )
        .reset_index()
    )
    for column, numerator in [("ppg", "points"), ("gf_pg", "goals_for"), ("ga_pg", "goals_against")]:
        splits[column] = (splits[numerator] / splits["matches"].replace(0, pd.NA)).fillna(0).round(2)
    return splits


def add_per90_metrics(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy()
    minutes = pd.to_numeric(work.get("minutesplayed", 0), errors="coerce").fillna(0).astype(float)
    base = minutes.div(90).replace(0, pd.NA)
    per90_map = {
        "goals_per90": "goals",
        "assists_per90": "assists",
        "goal_actions_per90": None,
        "saves_per90": "saves",
        "fouls_per90": "fouls",
    }
    for output, source in per90_map.items():
        if source is None:
            values = (
                pd.to_numeric(work.get("goals", 0), errors="coerce").fillna(0)
                + pd.to_numeric(work.get("assists", 0), errors="coerce").fillna(0)
            )
        else:
            values = pd.to_numeric(work.get(source, 0), errors="coerce").fillna(0)
        work[output] = values.astype(float).div(base).astype("Float64").fillna(0.0).round(2)
    return work


def aggregate_player_stats(
    player_match: pd.DataFrame,
    players: pd.DataFrame,
    teams: pd.DataFrame,
    match_ids: set[int] | None = None,
    team_id: int | None = None,
) -> pd.DataFrame:
    if player_match.empty:
        return pd.DataFrame()

    work = player_match.copy()
    if match_ids is not None:
        work = work[work["match_id"].isin(match_ids)]
    if team_id is not None:
        work = work[work["team_id"] == team_id]
    if work.empty:
        return pd.DataFrame()

    numeric_columns = [column for column in ["minutesplayed", "goals", "assists", "saves", "fouls", "penaltywon", "penaltysave", "penaltyconceded"] if column in work.columns]
    grouped = work.groupby("player_id", dropna=False).agg(
        matches_played=("match_id", "nunique"),
        **{column: (column, "sum") for column in numeric_columns},
    )
    grouped = grouped.reset_index()

    identity = (
        work.sort_values(["fecha_dt", "match_id"])
        .groupby("player_id", dropna=False)
        .tail(1)[["player_id", "name", "position", "team_id"]]
        .drop_duplicates(subset=["player_id"])
    )
    grouped = grouped.merge(identity, on="player_id", how="left")
    if "team_id" in grouped.columns:
        grouped["team_id"] = pd.to_numeric(grouped["team_id"], errors="coerce").astype("Int64")

    if not players.empty:
        player_columns = [column for column in ["player_id", "short_name", "dateofbirth"] if column in players.columns]
        grouped = grouped.merge(players[player_columns], on="player_id", how="left")
        if "short_name" in grouped.columns:
            grouped["name"] = grouped["short_name"].combine_first(grouped["name"])

    if not teams.empty:
        team_lookup = teams[["team_id", "team_name"]].drop_duplicates(subset=["team_id"])
        team_lookup["team_id"] = pd.to_numeric(team_lookup["team_id"], errors="coerce").astype("Int64")
        grouped = grouped.merge(team_lookup, on="team_id", how="left")

    for column in PLAYER_TOTAL_COLUMNS:
        if column not in grouped.columns:
            grouped[column] = 0
        grouped[column] = pd.to_numeric(grouped[column], errors="coerce").fillna(0)
    grouped["position"] = grouped["position"].astype(str).str.upper().replace({"NAN": pd.NA})
    grouped = add_per90_metrics(grouped)
    return grouped.sort_values(["minutesplayed", "goals", "assists"], ascending=[False, False, False]).reset_index(drop=True)


def build_full_season_player_stats(bundle: DatasetBundle) -> pd.DataFrame:
    if bundle.player_totals.empty:
        return aggregate_player_stats(bundle.player_match, bundle.players, bundle.teams)

    totals = bundle.player_totals.copy()
    for column in PLAYER_TOTAL_COLUMNS:
        if column not in totals.columns:
            totals[column] = 0
        totals[column] = pd.to_numeric(totals[column], errors="coerce").fillna(0)

    identity = bundle.players[["player_id", "name", "short_name", "position", "team_id"]].drop_duplicates(subset=["player_id"])
    totals = totals.merge(identity, on="player_id", how="left")
    if "team_id" in totals.columns:
        totals["team_id"] = pd.to_numeric(totals["team_id"], errors="coerce").astype("Int64")
    if "short_name" in totals.columns:
        totals["name"] = totals["short_name"].combine_first(totals["name"])

    if not bundle.teams.empty:
        team_lookup = bundle.teams[["team_id", "team_name"]].drop_duplicates(subset=["team_id"])
        team_lookup["team_id"] = pd.to_numeric(team_lookup["team_id"], errors="coerce").astype("Int64")
        totals = totals.merge(team_lookup, on="team_id", how="left")

    totals["position"] = totals["position"].astype(str).str.upper().replace({"NAN": pd.NA})
    totals = add_per90_metrics(totals)
    return totals.sort_values(["minutesplayed", "goals", "assists"], ascending=[False, False, False]).reset_index(drop=True)


def build_base_player_stats(bundle: DatasetBundle, filters: FilterState) -> pd.DataFrame:
    filtered_matches = apply_match_filters(bundle.matches, filters)
    if filtered_matches.empty:
        return pd.DataFrame()
    match_ids = set(filtered_matches["match_id"].dropna().astype(int).tolist())
    return aggregate_player_stats(bundle.player_match, bundle.players, bundle.teams, match_ids=match_ids)


def build_leaderboards(player_stats: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if player_stats.empty:
        return OrderedDict()

    work = player_stats.copy()
    if "player_id" not in work.columns:
        work["player_id"] = range(1, len(work) + 1)
    if "team_id" not in work.columns:
        work["team_id"] = pd.NA
    work = _filter_presentable_players(work)
    if work.empty:
        return OrderedDict()
    work["name"] = work["name"].map(lambda value: _safe_text(value, "Jugador sin identificar"))
    if "team_name" not in work.columns:
        work["team_name"] = "Sin equipo"
    else:
        work["team_name"] = work["team_name"].map(lambda value: _safe_text(value, "Sin equipo"))

    leaders = OrderedDict()
    leaders["Goles"] = (
        work.sort_values(["goals", "assists", "minutesplayed"], ascending=[False, False, False])
        .head(5)[["player_id", "team_id", "name", "team_name", "goals"]]
        .rename(columns={"name": "Jugador", "team_name": "Equipo", "goals": "Valor"})
    )
    leaders["Asistencias"] = (
        work.sort_values(["assists", "goals", "minutesplayed"], ascending=[False, False, False])
        .head(5)[["player_id", "team_id", "name", "team_name", "assists"]]
        .rename(columns={"name": "Jugador", "team_name": "Equipo", "assists": "Valor"})
    )
    leaders["Minutos"] = (
        work.sort_values(["minutesplayed", "matches_played"], ascending=[False, False])
        .head(5)[["player_id", "team_id", "name", "team_name", "minutesplayed"]]
        .rename(columns={"name": "Jugador", "team_name": "Equipo", "minutesplayed": "Valor"})
    )
    return leaders


def build_top_team_form(matches: pd.DataFrame) -> pd.DataFrame:
    team_rows = build_team_match_rows(matches)
    standings = calculate_standings(matches)
    if team_rows.empty or standings.empty:
        return pd.DataFrame()

    top_team_ids = standings.head(TOP_FORM_TEAMS)["team_id"].tolist()
    records: list[dict[str, object]] = []
    for team_id in top_team_ids:
        subset = team_rows[team_rows["team_id"] == team_id].sort_values(["fecha_dt", "match_id"])
        if subset.empty:
            continue
        recent = subset.tail(RECENT_FORM_MATCHES)
        records.append(
            {
                "team_id": team_id,
                "team_name": subset["team_name"].iloc[-1],
                "Pts": int(subset["points"].sum()),
                "GF": int(subset["goals_for"].sum()),
                "GC": int(subset["goals_against"].sum()),
                "Form": recent["result"].tolist(),
            }
        )
    return pd.DataFrame(records)


def build_top_matches(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()

    work = matches.copy()
    work["total_goals"] = work["home_score"].fillna(0).astype(int) + work["away_score"].fillna(0).astype(int)
    work["goal_margin"] = (work["home_score"].fillna(0).astype(int) - work["away_score"].fillna(0).astype(int)).abs()
    work = _build_match_label(work)
    return work.sort_values(
        ["total_goals", "goal_margin", "fecha_dt"],
        ascending=[False, False, False],
        kind="mergesort",
    ).head(8).reset_index(drop=True)


def build_league_overview(bundle: DatasetBundle, filters: FilterState) -> LeagueOverview:
    matches = apply_match_filters(bundle.matches, filters)
    standings = calculate_standings(matches)
    player_stats = _filter_presentable_players(build_base_player_stats(bundle, filters))
    total_goals = int(matches["home_score"].fillna(0).sum() + matches["away_score"].fillna(0).sum()) if not matches.empty else 0
    total_matches = int(matches["match_id"].nunique()) if not matches.empty else 0
    total_teams = int(standings["team_id"].nunique()) if not standings.empty else 0
    total_players = int(player_stats["player_id"].nunique()) if not player_stats.empty else 0
    goals_per_match = round(total_goals / total_matches, 2) if total_matches else 0.0

    if matches.empty:
        goals_by_round = pd.DataFrame(columns=["round_label", "goals"])
        venue_goals = pd.DataFrame(columns=["context", "goals"])
    else:
        goals_by_round = (
            matches.groupby(["tournament_label", "round_number", "round_label"], dropna=False)
            .agg(goals=("home_score", "sum"), away_goals=("away_score", "sum"))
            .reset_index()
        )
        goals_by_round["goals"] = goals_by_round["goals"] + goals_by_round["away_goals"]
        goals_by_round = goals_by_round.sort_values(["tournament_label", "round_number"], kind="mergesort")[["round_label", "goals"]]
        venue_goals = pd.DataFrame(
            {
                "context": ["Local", "Visita"],
                "goals": [
                    int(matches["home_score"].fillna(0).sum()),
                    int(matches["away_score"].fillna(0).sum()),
                ],
            }
        )

    return LeagueOverview(
        total_matches=total_matches,
        total_teams=total_teams,
        total_players=total_players,
        total_goals=total_goals,
        goals_per_match=goals_per_match,
        standings=standings,
        goals_by_round=goals_by_round,
        venue_goals=venue_goals,
        form_table=build_top_team_form(matches),
        leaders=build_leaderboards(player_stats),
        top_matches=build_top_matches(matches),
    )


def build_team_profile(bundle: DatasetBundle, filters: FilterState, team_id: int) -> TeamProfile | None:
    matches = apply_match_filters(bundle.matches, filters)
    team_rows = build_team_match_rows(matches)
    team_rows = team_rows[team_rows["team_id"] == team_id].copy()
    if team_rows.empty:
        return None

    team_lookup = bundle.teams.set_index("team_id")
    team_row = team_lookup.loc[team_id] if team_id in team_lookup.index else pd.Series(dtype="object")
    team_color = _resolve_team_color(bundle.teams, team_id, COLORS["accent"])
    summary = {
        "PJ": int(team_rows["match_id"].nunique()),
        "Pts": int(team_rows["points"].sum()),
        "G": int((team_rows["result"] == "W").sum()),
        "E": int((team_rows["result"] == "D").sum()),
        "P": int((team_rows["result"] == "L").sum()),
        "GF": int(team_rows["goals_for"].sum()),
        "GC": int(team_rows["goals_against"].sum()),
        "DG": int(team_rows["goal_difference"].sum()),
        "PPG": round(team_rows["points"].mean(), 2),
    }

    player_stats = aggregate_player_stats(
        bundle.player_match,
        bundle.players,
        bundle.teams,
        match_ids=set(team_rows["match_id"].astype(int).tolist()),
        team_id=team_id,
    )
    player_stats = _filter_presentable_players(player_stats)
    player_stats = player_stats[player_stats["minutesplayed"] >= 1]
    top_players = player_stats.sort_values(
        ["goals", "assists", "goal_actions_per90", "minutesplayed", "name"],
        ascending=[False, False, False, False, True],
    ).head(12)

    all_rows = build_team_match_rows(matches)
    comparison = pd.DataFrame(
        {
            "Metric": ["Puntos por partido", "Goles a favor / partido", "Goles en contra / partido", "Diferencia / partido"],
            "Equipo": [
                round(team_rows["points"].mean(), 2),
                round(team_rows["goals_for"].mean(), 2),
                round(team_rows["goals_against"].mean(), 2),
                round(team_rows["goal_difference"].mean(), 2),
            ],
            "Liga": [
                round(all_rows["points"].mean(), 2),
                round(all_rows["goals_for"].mean(), 2),
                round(all_rows["goals_against"].mean(), 2),
                round(all_rows["goal_difference"].mean(), 2),
            ],
        }
    )

    recent_matches = team_rows.sort_values(["fecha_dt", "match_id"], ascending=[False, False]).head(5).copy()
    recent_matches["resultado"] = recent_matches["result"].map({"W": "Victoria", "D": "Empate", "L": "Derrota"})
    recent_matches["marcador"] = recent_matches["goals_for"].astype(int).astype(str) + "-" + recent_matches["goals_against"].astype(int).astype(str)

    return TeamProfile(
        team_id=team_id,
        team_name=_safe_text(team_rows["team_name"].iloc[-1], f"Equipo {team_id}"),
        team_row=team_row,
        team_color=team_color,
        summary=summary,
        recent_matches=recent_matches,
        splits=calculate_team_splits(team_rows),
        top_players=top_players,
        comparison=comparison,
    )


def build_player_visual_matches(bundle: DatasetBundle, filters: FilterState, player_id: int) -> pd.DataFrame:
    filtered_matches = apply_match_filters(bundle.matches, filters)
    if filtered_matches.empty:
        return pd.DataFrame()

    match_ids = set(filtered_matches["match_id"].dropna().astype(int).tolist())
    average_match_ids = set()
    heatmap_match_ids = set()

    if not bundle.average_positions.empty:
        average_match_ids = set(
            bundle.average_positions[
                (bundle.average_positions["player_id"] == player_id)
                & (bundle.average_positions["match_id"].isin(match_ids))
            ]["match_id"].dropna().astype(int).tolist()
        )
    if not bundle.heatmap_points.empty:
        heatmap_match_ids = set(
            bundle.heatmap_points[
                (bundle.heatmap_points["player_id"] == player_id)
                & (bundle.heatmap_points["match_id"].isin(match_ids))
            ]["match_id"].dropna().astype(int).tolist()
        )

    visual_ids = sorted(average_match_ids | heatmap_match_ids)
    if not visual_ids:
        return pd.DataFrame()

    visual_matches = filtered_matches[filtered_matches["match_id"].isin(visual_ids)].copy()
    if visual_matches.empty:
        return pd.DataFrame()

    visual_matches = _build_match_label(visual_matches)
    visual_matches["has_average_position"] = visual_matches["match_id"].isin(average_match_ids)
    visual_matches["has_heatmap"] = visual_matches["match_id"].isin(heatmap_match_ids)
    return visual_matches.sort_values(["fecha_dt", "match_id"], ascending=[False, False]).reset_index(drop=True)


def _resolve_visual_match_id(
    visual_matches: pd.DataFrame,
    *,
    context_match_id: int | None = None,
    visual_match_id: int | None = None,
) -> int | None:
    if visual_matches.empty:
        return None
    options = visual_matches["match_id"].dropna().astype(int).tolist()
    if visual_match_id in options:
        return int(visual_match_id)
    if context_match_id in options:
        return int(context_match_id)
    return int(options[0]) if options else None


def _resolve_contextual_payload_match_id(
    visual_matches: pd.DataFrame,
    *,
    context_match_id: int | None = None,
    visual_match_id: int | None = None,
) -> int | None:
    if visual_matches.empty:
        return None
    options = visual_matches["match_id"].dropna().astype(int).tolist()
    if visual_match_id in options:
        return int(visual_match_id)
    if context_match_id is not None:
        return int(context_match_id) if context_match_id in options else None
    return int(options[0]) if options else None


def _build_player_contextual_average_position(
    bundle: DatasetBundle,
    *,
    player_id: int,
    visual_match_id: int | None,
) -> pd.Series | None:
    if visual_match_id is None:
        return None

    if bundle.average_positions.empty:
        return None
    average_subset = bundle.average_positions[
        (bundle.average_positions["player_id"] == player_id)
        & (bundle.average_positions["match_id"] == visual_match_id)
    ].copy()
    if average_subset.empty:
        return None
    return average_subset.iloc[0]


def _build_player_contextual_heatmap(
    bundle: DatasetBundle,
    *,
    player_id: int,
    visual_match_id: int | None,
) -> pd.DataFrame:
    if bundle.heatmap_points.empty or visual_match_id is None:
        return pd.DataFrame()
    heatmap_points = bundle.heatmap_points[
        (bundle.heatmap_points["player_id"] == player_id)
        & (bundle.heatmap_points["match_id"] == visual_match_id)
    ].copy()
    return heatmap_points.sort_values(["match_id"], kind="mergesort").reset_index(drop=True)


def _build_player_accumulated_heatmap(
    bundle: DatasetBundle,
    filters: FilterState,
    *,
    player_id: int,
) -> pd.DataFrame:
    if bundle.heatmap_points.empty:
        return pd.DataFrame()

    filtered_matches = apply_regular_season_filters(bundle.matches, filters)
    if filtered_matches.empty:
        return pd.DataFrame()

    match_ids = set(filtered_matches["match_id"].dropna().astype(int).tolist())
    if not match_ids:
        return pd.DataFrame()

    heatmap_points = bundle.heatmap_points[
        (bundle.heatmap_points["player_id"] == player_id)
        & (bundle.heatmap_points["match_id"].isin(match_ids))
    ].copy()
    return heatmap_points.sort_values(["match_id"], kind="mergesort").reset_index(drop=True)


def _build_player_accumulated_average_position(
    bundle: DatasetBundle,
    filters: FilterState,
    *,
    player_id: int,
) -> pd.Series | None:
    if bundle.average_positions.empty:
        return None

    filtered_matches = apply_regular_season_filters(bundle.matches, filters)
    if filtered_matches.empty:
        return None
    match_ids = set(filtered_matches["match_id"].dropna().astype(int).tolist())
    if not match_ids:
        return None

    subset = bundle.average_positions[
        (bundle.average_positions["player_id"] == player_id)
        & (bundle.average_positions["match_id"].isin(match_ids))
    ].copy()
    if subset.empty:
        return None

    subset["average_x"] = pd.to_numeric(subset["average_x"], errors="coerce")
    subset["average_y"] = pd.to_numeric(subset["average_y"], errors="coerce")
    subset["points_count_numeric"] = pd.to_numeric(subset.get("points_count"), errors="coerce").fillna(0.0)
    subset = subset.dropna(subset=["average_x", "average_y"]).copy()
    if subset.empty:
        return None

    weights = subset["points_count_numeric"]
    weighted = bool((weights > 0).any())
    if weighted:
        average_x = float((subset["average_x"] * weights).sum() / weights.sum())
        average_y = float((subset["average_y"] * weights).sum() / weights.sum())
    else:
        average_x = float(subset["average_x"].mean())
        average_y = float(subset["average_y"].mean())

    def _mode_or_last(series: pd.Series) -> object:
        valid = series.dropna()
        if valid.empty:
            return pd.NA
        modes = valid.mode(dropna=True)
        return modes.iloc[0] if not modes.empty else valid.iloc[-1]

    matches_count = int(subset["match_id"].dropna().nunique())
    points_total = int(weights[weights > 0].sum()) if weighted else 0
    return pd.Series(
        {
            "player_id": player_id,
            "match_id": pd.NA,
            "team_id": _mode_or_last(subset["team_id"]) if "team_id" in subset.columns else pd.NA,
            "team_name": _mode_or_last(subset["team_name"]) if "team_name" in subset.columns else pd.NA,
            "name": _mode_or_last(subset["name"]) if "name" in subset.columns else pd.NA,
            "shirt_number": _mode_or_last(subset["shirt_number"]) if "shirt_number" in subset.columns else pd.NA,
            "position": _mode_or_last(subset["position"]) if "position" in subset.columns else pd.NA,
            "average_x": average_x,
            "average_y": average_y,
            "points_count": points_total,
            "points_count_total": points_total,
            "matches_count": matches_count,
        }
    )


def _build_player_visual_coverage(visual_matches: pd.DataFrame) -> dict[str, object]:
    if visual_matches.empty:
        return {
            "average_match_count": 0,
            "heatmap_match_count": 0,
            "average_round_labels": [],
            "heatmap_round_labels": [],
        }

    average_matches = visual_matches[visual_matches["has_average_position"]].copy()
    heatmap_matches = visual_matches[visual_matches["has_heatmap"]].copy()
    return {
        "average_match_count": int(average_matches["match_id"].nunique()) if not average_matches.empty else 0,
        "heatmap_match_count": int(heatmap_matches["match_id"].nunique()) if not heatmap_matches.empty else 0,
        "average_round_labels": average_matches["round_label"].dropna().astype(str).drop_duplicates().tolist() if not average_matches.empty and "round_label" in average_matches.columns else [],
        "heatmap_round_labels": heatmap_matches["round_label"].dropna().astype(str).drop_duplicates().tolist() if not heatmap_matches.empty and "round_label" in heatmap_matches.columns else [],
    }


def _build_player_accumulated_visual_coverage(
    bundle: DatasetBundle,
    filters: FilterState,
    *,
    player_id: int,
) -> dict[str, object]:
    regular_matches = apply_regular_season_filters(bundle.matches, filters)
    if regular_matches.empty:
        return {
            "regular_average_match_count": 0,
            "regular_heatmap_match_count": 0,
            "regular_average_round_labels": [],
            "regular_heatmap_round_labels": [],
        }

    match_ids = set(regular_matches["match_id"].dropna().astype(int).tolist())
    average_match_ids = set()
    heatmap_match_ids = set()

    if not bundle.average_positions.empty:
        average_match_ids = set(
            bundle.average_positions[
                (bundle.average_positions["player_id"] == player_id)
                & (bundle.average_positions["match_id"].isin(match_ids))
            ]["match_id"].dropna().astype(int).tolist()
        )
    if not bundle.heatmap_points.empty:
        heatmap_match_ids = set(
            bundle.heatmap_points[
                (bundle.heatmap_points["player_id"] == player_id)
                & (bundle.heatmap_points["match_id"].isin(match_ids))
            ]["match_id"].dropna().astype(int).tolist()
        )

    average_matches = regular_matches[regular_matches["match_id"].isin(average_match_ids)].copy()
    heatmap_matches = regular_matches[regular_matches["match_id"].isin(heatmap_match_ids)].copy()
    return {
        "regular_average_match_count": int(average_matches["match_id"].nunique()) if not average_matches.empty else 0,
        "regular_heatmap_match_count": int(heatmap_matches["match_id"].nunique()) if not heatmap_matches.empty else 0,
        "regular_average_round_labels": average_matches["round_label"].dropna().astype(str).drop_duplicates().tolist() if not average_matches.empty and "round_label" in average_matches.columns else [],
        "regular_heatmap_round_labels": heatmap_matches["round_label"].dropna().astype(str).drop_duplicates().tolist() if not heatmap_matches.empty and "round_label" in heatmap_matches.columns else [],
    }


def _resolve_player_visual_defaults(
    *,
    contextual_average_position_row: pd.Series | None,
    contextual_heatmap_points: pd.DataFrame,
    accumulated_average_position_row: pd.Series | None,
    accumulated_heatmap_points: pd.DataFrame,
) -> tuple[str, str]:
    if contextual_average_position_row is not None:
        return PLAYER_AVERAGE_POSITION_MODE, PLAYER_CONTEXTUAL_SCOPE
    if not contextual_heatmap_points.empty:
        return PLAYER_HEATMAP_MODE, PLAYER_CONTEXTUAL_SCOPE
    if accumulated_average_position_row is not None:
        return PLAYER_AVERAGE_POSITION_MODE, PLAYER_ACCUMULATED_SCOPE
    if not accumulated_heatmap_points.empty:
        return PLAYER_HEATMAP_MODE, PLAYER_ACCUMULATED_SCOPE
    return PLAYER_AVERAGE_POSITION_MODE, PLAYER_CONTEXTUAL_SCOPE


def build_players_table(
    bundle: DatasetBundle,
    filters: FilterState,
    team_id: int | None = None,
    position: str | None = None,
    search: str | None = None,
) -> pd.DataFrame:
    player_stats = _filter_presentable_players(build_base_player_stats(bundle, filters))
    if player_stats.empty:
        return player_stats
    player_stats = player_stats[player_stats["minutesplayed"] >= filters.min_minutes]
    if team_id is not None:
        player_stats = player_stats[player_stats["team_id"] == team_id]
    if position:
        player_stats = player_stats[player_stats["position"] == position]
    if search:
        player_stats = player_stats[player_stats["name"].astype(str).str.contains(search, case=False, na=False)]
    return player_stats.sort_values(
        ["goals", "assists", "goal_actions_per90", "minutesplayed", "name"],
        ascending=[False, False, False, False, True],
    ).reset_index(drop=True)


def build_player_profile(
    bundle: DatasetBundle,
    filters: FilterState,
    player_id: int,
    *,
    context_match_id: int | None = None,
    visual_match_id: int | None = None,
) -> PlayerProfile | None:
    player_stats = _filter_presentable_players(build_base_player_stats(bundle, filters))
    if player_stats.empty:
        return None
    player_stats = player_stats[player_stats["minutesplayed"] >= filters.min_minutes].reset_index(drop=True)
    if player_stats.empty or player_id not in set(player_stats["player_id"].astype(int).tolist()):
        return None

    selected = player_stats[player_stats["player_id"] == player_id]
    if selected.empty:
        return None
    player_row = selected.iloc[0]
    if not _has_usable_text(player_row.get("name")):
        return None
    cohort = player_stats[player_stats["position"] == player_row["position"]].copy()
    if cohort.empty:
        cohort = player_stats.copy()

    if str(player_row["position"]) == "G":
        metrics = [
            ("Atajadas / 90", "saves_per90"),
            ("Minutos", "minutesplayed"),
            ("Partidos", "matches_played"),
        ]
    else:
        metrics = [
            ("Goles / 90", "goals_per90"),
            ("Asistencias / 90", "assists_per90"),
            ("Acciones de gol / 90", "goal_actions_per90"),
            ("Minutos", "minutesplayed"),
        ]

    percentiles = []
    for label, column in metrics:
        cohort_values = pd.to_numeric(cohort[column], errors="coerce").fillna(0)
        ranks = cohort_values.rank(pct=True, method="max")
        player_index = cohort.index[cohort["player_id"] == player_id]
        percentile = float((ranks.loc[player_index[0]] * 100).round(0)) if len(player_index) else 0
        value = float(pd.to_numeric(pd.Series([player_row[column]]), errors="coerce").fillna(0).iloc[0])
        percentiles.append({"Metric": label, "value": round(value, 2), "percentile": percentile})

    filtered_matches = apply_match_filters(bundle.matches, filters)
    player_recent = bundle.player_match[
        (bundle.player_match["player_id"] == player_id) & (bundle.player_match["match_id"].isin(filtered_matches["match_id"]))
    ].copy()
    player_recent = add_per90_metrics(player_recent)
    player_recent = player_recent.sort_values(["fecha_dt", "match_id"], ascending=[False, False]).head(8)
    if not player_recent.empty:
        player_recent["partido"] = player_recent["home"] + " " + player_recent["scoreline"] + " " + player_recent["away"]

    available_visual_matches = build_player_visual_matches(bundle, filters, player_id)
    resolved_visual_match_id = _resolve_visual_match_id(
        available_visual_matches,
        context_match_id=context_match_id,
        visual_match_id=visual_match_id,
    )
    contextual_payload_match_id = _resolve_contextual_payload_match_id(
        available_visual_matches,
        context_match_id=context_match_id,
        visual_match_id=visual_match_id,
    )
    contextual_average_position_row = _build_player_contextual_average_position(
        bundle,
        player_id=player_id,
        visual_match_id=contextual_payload_match_id,
    )
    contextual_heatmap_points = _build_player_contextual_heatmap(
        bundle,
        player_id=player_id,
        visual_match_id=contextual_payload_match_id,
    )
    accumulated_average_position_row = _build_player_accumulated_average_position(
        bundle,
        filters,
        player_id=player_id,
    )
    accumulated_heatmap_points = _build_player_accumulated_heatmap(
        bundle,
        filters,
        player_id=player_id,
    )
    visual_coverage = {
        **_build_player_visual_coverage(available_visual_matches),
        **_build_player_accumulated_visual_coverage(bundle, filters, player_id=player_id),
    }
    default_visual_mode, default_visual_scope = _resolve_player_visual_defaults(
        contextual_average_position_row=contextual_average_position_row,
        contextual_heatmap_points=contextual_heatmap_points,
        accumulated_average_position_row=accumulated_average_position_row,
        accumulated_heatmap_points=accumulated_heatmap_points,
    )

    summary = {
        "Equipo": _safe_text(player_row.get("team_name"), "Sin equipo"),
        "Posicion": _safe_text(player_row.get("position"), "-"),
        "Minutos": _safe_int(player_row.get("minutesplayed", 0)),
        "Partidos": _safe_int(player_row.get("matches_played", 0)),
        "Goles": _safe_int(player_row.get("goals", 0)),
        "Asistencias": _safe_int(player_row.get("assists", 0)),
    }

    return PlayerProfile(
        player_id=player_id,
        player_row=player_row,
        team_color=_resolve_team_color(bundle.teams, _safe_optional_int(player_row.get("team_id")), COLORS["accent"]),
        summary=summary,
        percentiles=pd.DataFrame(percentiles),
        recent_matches=player_recent,
        available_visual_matches=available_visual_matches,
        visual_coverage=visual_coverage,
        default_visual_match_id=resolved_visual_match_id,
        default_visual_mode=default_visual_mode,
        default_visual_scope=default_visual_scope,
        contextual_average_position_row=contextual_average_position_row,
        accumulated_average_position_row=accumulated_average_position_row,
        contextual_heatmap_points=contextual_heatmap_points,
        accumulated_heatmap_points=accumulated_heatmap_points,
    )


def build_match_catalog(
    bundle: DatasetBundle,
    filters: FilterState,
    team_id: int | None = None,
    venue_filter: str = "Todos",
    result_filter: str = "Todos",
) -> pd.DataFrame:
    matches = apply_match_filters(bundle.matches, filters).copy()
    if matches.empty:
        return matches
    if team_id is not None:
        matches = matches[(matches["home_id"] == team_id) | (matches["away_id"] == team_id)]
    if venue_filter == "Local" and team_id is not None:
        matches = matches[matches["home_id"] == team_id]
    if venue_filter == "Visita" and team_id is not None:
        matches = matches[matches["away_id"] == team_id]
    if result_filter == "Victorias locales":
        matches = matches[matches["home_score"] > matches["away_score"]]
    elif result_filter == "Empates":
        matches = matches[matches["home_score"] == matches["away_score"]]
    elif result_filter == "Victorias visitantes":
        matches = matches[matches["away_score"] > matches["home_score"]]

    matches = _build_match_label(matches)
    return matches.sort_values(["fecha_dt", "match_id"], ascending=[False, False]).reset_index(drop=True)


def build_match_stat_table(team_stats: pd.DataFrame, match_id: int) -> pd.DataFrame:
    lookup = _build_match_stat_lookup(team_stats, match_id)
    if lookup.empty:
        return pd.DataFrame()

    rows = []
    for label, key, is_percent in PREFERRED_MATCH_STATS:
        if key not in lookup.index:
            continue
        home_value, away_value = _get_match_stat_pair(lookup, key)
        if is_percent:
            home_display = _format_stat_value(home_value, is_percent=True)
            away_display = _format_stat_value(away_value, is_percent=True)
        else:
            home_display = _format_stat_value(home_value)
            away_display = _format_stat_value(away_value)
        rows.append({"Metrica": label, "Local": home_display, "Visita": away_display})
    return pd.DataFrame(rows)


def _select_team_average_positions(
    average_positions: pd.DataFrame,
    player_rows: pd.DataFrame,
    *,
    team_id: int,
    team_name: str,
    side: str,
) -> tuple[pd.DataFrame, str]:
    if average_positions.empty:
        return pd.DataFrame(), "sin datos"

    subset = average_positions[average_positions["team_id"] == team_id].copy()
    if subset.empty and "team_name" in average_positions.columns:
        subset = average_positions[average_positions["team_name"] == team_name].copy()
    if subset.empty:
        return pd.DataFrame(), "sin datos"

    starters = pd.DataFrame()
    if "is_starter" in subset.columns and subset["is_starter"].notna().any():
        starters = subset[subset["is_starter"] == True].copy()  # noqa: E712

    if len(starters) >= 8:
        chosen = starters
        strategy = "titulares"
    else:
        candidate_ids: list[int] = []
        if not player_rows.empty:
            candidate_ids = (
                player_rows[
                    (player_rows["side"] == side)
                    & (player_rows["team_id"] == team_id)
                    & (player_rows["player_id"].notna())
                ]
                .sort_values(["minutesplayed", "goals", "assists", "player_id"], ascending=[False, False, False, True], kind="mergesort")["player_id"]
                .astype(int)
                .tolist()
            )
        if candidate_ids:
            fallback = subset[subset["player_id"].isin(candidate_ids)].copy()
            if not fallback.empty:
                fallback["minutes_rank"] = pd.Categorical(
                    fallback["player_id"].astype(int),
                    categories=candidate_ids,
                    ordered=True,
                )
                chosen = (
                    fallback.sort_values(["minutes_rank", "points_count"], kind="mergesort")
                    .drop(columns="minutes_rank")
                    .head(11)
                )
                strategy = "minutos"
            else:
                chosen = subset.sort_values(["points_count", "shirt_number"], ascending=[False, True], kind="mergesort").head(11)
                strategy = "todos"
        else:
            chosen = subset.sort_values(["points_count", "shirt_number"], ascending=[False, True], kind="mergesort").head(11)
            strategy = "todos"

    chosen = chosen.copy()
    chosen["side"] = side
    chosen["team_name"] = chosen["team_name"].fillna(team_name)
    return chosen.reset_index(drop=True), strategy


def build_match_team_average_positions(
    bundle: DatasetBundle,
    match_row: pd.Series,
    player_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if bundle.average_positions.empty:
        return pd.DataFrame(), {"home_strategy": "sin datos", "away_strategy": "sin datos"}

    match_id = int(match_row["match_id"])
    subset = bundle.average_positions[bundle.average_positions["match_id"] == match_id].copy()
    if subset.empty:
        return pd.DataFrame(), {"home_strategy": "sin datos", "away_strategy": "sin datos"}

    home_positions, home_strategy = _select_team_average_positions(
        subset,
        player_rows,
        team_id=int(match_row["home_id"]),
        team_name=str(match_row["home"]),
        side="Local",
    )
    away_positions, away_strategy = _select_team_average_positions(
        subset,
        player_rows,
        team_id=int(match_row["away_id"]),
        team_name=str(match_row["away"]),
        side="Visita",
    )
    combined = pd.concat([home_positions, away_positions], ignore_index=True)
    metadata = {
        "home_strategy": home_strategy,
        "away_strategy": away_strategy,
        "home_count": len(home_positions),
        "away_count": len(away_positions),
    }
    return combined, metadata


def build_grouped_match_stats(team_stats: pd.DataFrame, match_id: int) -> OrderedDict[str, pd.DataFrame]:
    subset = _build_match_stat_subset(team_stats, match_id)
    if subset.empty:
        return OrderedDict()

    subset = subset.drop_duplicates(subset=["GROUP", "KEY"], keep="first").copy()
    subset["Grupo"] = subset["group_label"]
    subset["Metrica"] = subset.apply(_clean_stat_label, axis=1)
    subset["Local"] = subset.apply(
        lambda row: _format_stat_value(
            row["HOMEVALUE"] if pd.notna(row.get("HOMEVALUE")) else row.get("HOMETOTAL"),
            is_percent=_is_percent_stat(row),
        ),
        axis=1,
    )
    subset["Visita"] = subset.apply(
        lambda row: _format_stat_value(
            row["AWAYVALUE"] if pd.notna(row.get("AWAYVALUE")) else row.get("AWAYTOTAL"),
            is_percent=_is_percent_stat(row),
        ),
        axis=1,
    )
    groups = OrderedDict()
    group_labels = subset["Grupo"].dropna().astype(str).unique().tolist()
    ordered_groups = [label for label in MATCH_STAT_GROUP_ORDER if label in group_labels]
    ordered_groups.extend(sorted(label for label in group_labels if label not in MATCH_STAT_GROUP_ORDER))
    for group in ordered_groups:
        frame = subset[subset["Grupo"] == group][["Metrica", "Local", "Visita", "KEY"]].reset_index(drop=True)
        groups[group] = frame
    return groups


def build_match_player_rows(player_match: pd.DataFrame, match_row: pd.Series) -> pd.DataFrame:
    if player_match.empty:
        return pd.DataFrame()

    match_id = int(match_row["match_id"])
    subset = player_match[player_match["match_id"] == match_id].copy()
    if subset.empty:
        return pd.DataFrame()
    if "name" in subset.columns:
        subset = subset[subset["name"].map(_has_usable_text)].copy()
    if subset.empty:
        return pd.DataFrame()

    side_lookup = {
        int(match_row["home_id"]): ("Local", str(match_row["home"])),
        int(match_row["away_id"]): ("Visita", str(match_row["away"])),
    }
    subset["name"] = subset["name"].map(lambda value: _safe_text(value, "Jugador sin identificar"))
    subset["side"] = subset["team_id"].map(
        lambda value: side_lookup.get(int(value), ("Sin lado", "Sin equipo"))[0] if pd.notna(value) else "Sin lado"
    )
    subset["team_name"] = subset["team_id"].map(
        lambda value: side_lookup.get(int(value), ("Sin lado", "Sin equipo"))[1] if pd.notna(value) else "Sin equipo"
    )
    subset["is_navigable"] = subset["player_id"].notna() & subset["team_id"].notna()

    for column in ["minutesplayed", "goals", "assists", "saves", "fouls"]:
        if column in subset.columns:
            subset[column] = pd.to_numeric(subset[column], errors="coerce").fillna(0)
    subset["impact"] = subset["goals"].fillna(0) + subset["assists"].fillna(0)

    side_order = pd.Categorical(subset["side"], categories=["Local", "Visita", "Sin lado"], ordered=True)
    subset = subset.assign(_side_order=side_order)
    subset = subset.sort_values(
        ["_side_order", "impact", "minutesplayed", "goals", "assists", "name"],
        ascending=[True, False, False, False, False, True],
        kind="mergesort",
    )
    return subset.drop(columns="_side_order").reset_index(drop=True)


def _resolve_event_side(value: object) -> str:
    if pd.isna(value):
        return "Sin lado"
    if isinstance(value, bool):
        return "Local" if value else "Visita"
    text = str(value).strip().lower()
    if text in {"true", "1", "home", "local"}:
        return "Local"
    if text in {"false", "0", "away", "visita"}:
        return "Visita"
    return "Sin lado"


def build_match_shot_events(shot_events: pd.DataFrame, match_row: pd.Series) -> tuple[pd.DataFrame, dict[str, object]]:
    if shot_events.empty:
        return pd.DataFrame(), {}

    match_id = int(match_row["match_id"])
    subset = shot_events.loc[shot_events["match_id"] == match_id].copy()
    if subset.empty:
        return pd.DataFrame(), {}

    for column in ["x", "y", "z", "time", "added_time", "time_seconds"]:
        if column in subset.columns:
            subset[column] = pd.to_numeric(subset[column], errors="coerce")
    subset["shot_type_norm"] = subset.get("shot_type", pd.Series(index=subset.index, dtype="object")).astype("string").str.strip().str.lower()

    subset["side"] = subset.get("is_home", pd.Series(index=subset.index, dtype="object")).map(_resolve_event_side)
    home_id = _safe_optional_int(match_row.get("home_id"))
    away_id = _safe_optional_int(match_row.get("away_id"))
    if "team_id" in subset.columns:
        team_ids = pd.to_numeric(subset["team_id"], errors="coerce").astype("Int64")
        subset.loc[subset["side"] == "Sin lado", "side"] = team_ids.map(
            lambda value: "Local"
            if pd.notna(value) and home_id is not None and int(value) == home_id
            else "Visita"
            if pd.notna(value) and away_id is not None and int(value) == away_id
            else "Sin lado"
        )

    subset["display_x"] = subset.get("x")
    subset["display_y"] = subset.get("y")
    # Opta events are normalized in attacking direction (x: 0->100), so we mirror
    # away shots to compare both teams against the same attacking goal in one chart.
    away_mask = subset["side"] == "Visita"
    subset.loc[away_mask, "display_x"] = 100 - subset.loc[away_mask, "x"]
    subset.loc[away_mask, "display_y"] = 100 - subset.loc[away_mask, "y"]
    subset["team_name"] = subset.get("team_name", pd.Series(index=subset.index, dtype="object")).astype("string")
    subset.loc[subset["side"] == "Local", "team_name"] = subset.loc[subset["side"] == "Local", "team_name"].fillna(str(match_row.get("home", "Local")))
    subset.loc[subset["side"] == "Visita", "team_name"] = subset.loc[subset["side"] == "Visita", "team_name"].fillna(str(match_row.get("away", "Visita")))

    subset["is_on_target"] = subset["shot_type_norm"].isin({"goal", "save"})
    subset["minute_label"] = subset["time"].fillna(0).astype(int).astype(str)
    if "added_time" in subset.columns:
        added = subset["added_time"].fillna(0)
        subset.loc[added > 0, "minute_label"] = (
            subset.loc[added > 0, "time"].fillna(0).astype(int).astype(str) + "+" + added.loc[added > 0].astype(int).astype(str)
        )

    sort_columns = [column for column in ["time_seconds", "time", "shot_id"] if column in subset.columns]
    if sort_columns:
        subset = subset.sort_values(sort_columns, kind="mergesort")
    subset = subset.reset_index(drop=True)

    home_subset = subset[subset["side"] == "Local"]
    away_subset = subset[subset["side"] == "Visita"]
    metadata = {
        "home_shots": int(len(home_subset)),
        "away_shots": int(len(away_subset)),
        "home_goals": int((home_subset["shot_type_norm"] == "goal").sum()),
        "away_goals": int((away_subset["shot_type_norm"] == "goal").sum()),
        "home_on_target": int(home_subset["is_on_target"].sum()),
        "away_on_target": int(away_subset["is_on_target"].sum()),
        "orientation_note": "Opta base: la visita se refleja para comparar ambos ataques hacia la misma porteria.",
    }
    return subset, metadata


def build_match_momentum_series(match_momentum: pd.DataFrame, match_id: int) -> tuple[pd.DataFrame, dict[str, object]]:
    if match_momentum.empty:
        return pd.DataFrame(), {}
    subset = match_momentum.loc[match_momentum["match_id"] == match_id].copy()
    if subset.empty:
        return pd.DataFrame(), {}
    subset["minute"] = pd.to_numeric(subset.get("minute"), errors="coerce")
    subset["value"] = pd.to_numeric(subset.get("value"), errors="coerce")
    subset = subset.dropna(subset=["minute", "value"]).copy()
    if subset.empty:
        return pd.DataFrame(), {}

    subset["minute"] = subset["minute"].round(1)
    if "dominant_side" in subset.columns:
        subset["dominant_side"] = subset["dominant_side"].astype("string").str.strip().str.lower()
    else:
        subset["dominant_side"] = pd.Series("neutral", index=subset.index, dtype="string")

    grouped = (
        subset.groupby("minute", as_index=False)
        .agg(
            value=("value", "mean"),
            dominant_side=("dominant_side", lambda values: values.mode().iloc[0] if not values.mode().empty else "neutral"),
        )
        .sort_values("minute", kind="mergesort")
        .reset_index(drop=True)
    )
    grouped["rolling_value"] = grouped["value"].rolling(window=5, min_periods=1, center=True).mean()
    metadata = {
        "max_value": float(grouped["value"].max()),
        "min_value": float(grouped["value"].min()),
        "max_abs": float(grouped["value"].abs().max()),
        "points": int(len(grouped)),
    }
    return grouped, metadata


def build_match_goalkeeper_saves(player_rows: pd.DataFrame, match_row: pd.Series) -> pd.DataFrame:
    if player_rows.empty:
        return pd.DataFrame()

    work = player_rows.copy()
    work["position_norm"] = work.get("position", pd.Series(index=work.index, dtype="object")).astype("string").str.strip().str.upper()
    work["saves"] = pd.to_numeric(work.get("saves"), errors="coerce").fillna(0)
    work["minutesplayed"] = pd.to_numeric(work.get("minutesplayed"), errors="coerce").fillna(0)

    keepers = work[work["position_norm"].isin({"G", "GK", "GOALKEEPER", "PORTERO"})].copy()
    if keepers.empty:
        keepers = work[work["saves"] > 0].copy()
    if keepers.empty:
        return pd.DataFrame()

    side_team_lookup = {
        "Local": _safe_text(match_row.get("home"), "Local"),
        "Visita": _safe_text(match_row.get("away"), "Visita"),
    }
    keepers["team_name"] = keepers.get("team_name", pd.Series(index=keepers.index, dtype="object"))
    keepers["team_name"] = keepers["team_name"].fillna(keepers["side"].map(side_team_lookup)).fillna("Sin equipo")
    side_order = pd.Categorical(keepers["side"], categories=["Local", "Visita", "Sin lado"], ordered=True)
    keepers = (
        keepers.assign(_side_order=side_order)
        .sort_values(["_side_order", "saves", "minutesplayed", "name"], ascending=[True, False, False, True], kind="mergesort")
        .drop(columns="_side_order")
    )
    columns = [column for column in ["side", "team_name", "name", "position", "saves", "minutesplayed", "player_id", "team_id"] if column in keepers.columns]
    return keepers[columns].reset_index(drop=True)


def build_match_standout_players(player_rows: pd.DataFrame) -> pd.DataFrame:
    if player_rows.empty:
        return pd.DataFrame(columns=["side", "player_id", "team_id", "name", "position", "goals", "assists", "minutesplayed"])

    rows = []
    for side in ["Local", "Visita"]:
        subset = player_rows[player_rows["side"] == side].copy()
        if "is_navigable" in subset.columns:
            subset = subset[subset["is_navigable"]].copy()
        if subset.empty:
            continue
        standout = subset.sort_values(["impact", "minutesplayed", "goals", "assists"], ascending=[False, False, False, False], kind="mergesort").iloc[0]
        rows.append(
            {
                "side": side,
                "player_id": int(standout["player_id"]),
                "team_id": int(standout["team_id"]),
                "name": _safe_text(standout["name"], "Sin figura clara"),
                "position": standout.get("position"),
                "goals": _safe_int(standout.get("goals")),
                "assists": _safe_int(standout.get("assists")),
                "minutesplayed": _safe_int(standout.get("minutesplayed")),
            }
        )
    return pd.DataFrame(rows)


def build_match_insight_cards(match_row: pd.Series, team_stats: pd.DataFrame, standout_players: pd.DataFrame) -> list[dict[str, str]]:
    lookup = _build_match_stat_lookup(team_stats, int(match_row["match_id"]))
    possession_home, possession_away = _get_match_stat_pair(lookup, "ballPossession")
    passes_home, passes_away = _get_match_stat_pair(lookup, "passes")
    shots_home, shots_away = _get_match_stat_pair(lookup, "totalShotsOnGoal")
    chances_home, chances_away = _get_match_stat_pair(lookup, "bigChanceCreated")
    fouls_home, fouls_away = _get_match_stat_pair(lookup, "fouls")
    on_target_home, on_target_away = _get_match_stat_pair(lookup, "shotsOnGoal")

    if standout_players.empty or "side" not in standout_players.columns:
        local_star = pd.DataFrame()
        away_star = pd.DataFrame()
    else:
        local_star = standout_players[standout_players["side"] == "Local"].head(1)
        away_star = standout_players[standout_players["side"] == "Visita"].head(1)

    local_star_value = _safe_text(local_star.iloc[0]["name"], "Sin figura clara") if not local_star.empty else "Sin figura clara"
    away_star_value = _safe_text(away_star.iloc[0]["name"], "Sin figura clara") if not away_star.empty else "Sin figura clara"
    local_star_help = (
        f"G {_safe_int(local_star.iloc[0]['goals'])} | A {_safe_int(local_star.iloc[0]['assists'])} | Min {_safe_int(local_star.iloc[0]['minutesplayed'])}"
        if not local_star.empty
        else "No hay player_match suficiente."
    )
    away_star_help = (
        f"G {_safe_int(away_star.iloc[0]['goals'])} | A {_safe_int(away_star.iloc[0]['assists'])} | Min {_safe_int(away_star.iloc[0]['minutesplayed'])}"
        if not away_star.empty
        else "No hay player_match suficiente."
    )

    total_goals = _safe_int(match_row.get("home_score")) + _safe_int(match_row.get("away_score"))
    total_fouls = _safe_int(fouls_home) + _safe_int(fouls_away)
    total_on_target = _safe_int(on_target_home) + _safe_int(on_target_away)
    return [
        {
            "label": "Control del juego",
            "value": _format_pair(possession_home, possession_away, is_percent=True),
            "help": f"Posesion | Pases {_format_pair(passes_home, passes_away)}",
        },
        {
            "label": "Amenaza ofensiva",
            "value": _format_pair(shots_home, shots_away),
            "help": f"Tiros totales | Big chances {_format_pair(chances_home, chances_away)}",
        },
        {
            "label": "Figura local",
            "value": str(local_star_value),
            "help": local_star_help,
        },
        {
            "label": "Figura visita",
            "value": str(away_star_value),
            "help": away_star_help,
        },
        {
            "label": "Volumen del partido",
            "value": f"{total_goals} goles | {total_fouls} faltas",
            "help": f"Tiros al arco totales {total_on_target}",
        },
    ]


def build_team_context_matches(matches: pd.DataFrame, team_id: int, match_id: int, limit: int = 5) -> pd.DataFrame:
    team_rows = build_team_match_rows(matches)
    team_rows = team_rows[team_rows["team_id"] == team_id].sort_values(["fecha_dt", "match_id"]).reset_index(drop=True)
    if team_rows.empty:
        return pd.DataFrame()

    current_index = team_rows.index[team_rows["match_id"] == match_id]
    if len(current_index) == 0:
        return pd.DataFrame()

    current_index = int(current_index[0])
    candidates = []
    for idx in team_rows.index.tolist():
        if idx == current_index:
            continue
        candidates.append((abs(idx - current_index), idx))

    selected_indexes = [idx for _, idx in sorted(candidates, key=lambda item: (item[0], item[1]))[:limit]]
    if not selected_indexes:
        return pd.DataFrame()

    context = team_rows.loc[selected_indexes].copy()
    context["delta"] = context.index - current_index
    context["Relacion"] = context["delta"].map(
        lambda value: f"{abs(int(value))} antes" if value < 0 else f"{int(value)} despues"
    )
    context["Resultado"] = context["result"].map({"W": "Victoria", "D": "Empate", "L": "Derrota"})
    context["Marcador"] = context["goals_for"].astype(int).astype(str) + "-" + context["goals_against"].astype(int).astype(str)
    context["Partido"] = context["team_name"] + " " + context["Marcador"] + " " + context["opponent_name"]
    return context.sort_values(["delta"], kind="mergesort").reset_index(drop=True)


def build_catalog_neighbors(catalog: pd.DataFrame, match_id: int) -> dict[str, object]:
    if catalog.empty:
        return {
            "current_index": 0,
            "total": 0,
            "current_label": "",
            "previous_match_id": None,
            "previous_label": None,
            "next_match_id": None,
            "next_label": None,
        }

    match_ids = catalog["match_id"].astype(int).tolist()
    current_index = match_ids.index(match_id) if match_id in match_ids else 0
    current_row = catalog.iloc[current_index]
    previous_row = catalog.iloc[current_index - 1] if current_index > 0 else None
    next_row = catalog.iloc[current_index + 1] if current_index < len(catalog) - 1 else None
    def _catalog_label(row: pd.Series | None, fallback: str) -> str | None:
        if row is None:
            return None
        round_label = _safe_text(row.get("round_label"), "")
        partido = _safe_text(row.get("partido"), fallback)
        return f"{round_label} · {partido}" if round_label else partido
    return {
        "current_index": current_index,
        "total": len(catalog),
        "current_label": _catalog_label(current_row, "Partido focal") or "Partido focal",
        "previous_match_id": int(previous_row["match_id"]) if previous_row is not None else None,
        "previous_label": _catalog_label(previous_row, "Partido anterior"),
        "next_match_id": int(next_row["match_id"]) if next_row is not None else None,
        "next_label": _catalog_label(next_row, "Partido siguiente"),
    }


def build_match_summary(
    bundle: DatasetBundle,
    filters: FilterState,
    match_id: int,
    catalog: pd.DataFrame,
    origin_context: dict[str, object] | None = None,
) -> MatchSummary | None:
    matches = bundle.matches[bundle.matches["match_id"] == match_id]
    if matches.empty:
        return None
    match_row = matches.iloc[0]
    grouped_stats = build_grouped_match_stats(bundle.team_stats, int(match_row["match_id"]))
    player_rows = build_match_player_rows(bundle.player_match, match_row)
    standout_players = build_match_standout_players(player_rows)
    shot_events, shot_events_metadata = build_match_shot_events(bundle.shot_events, match_row)
    momentum_series, momentum_metadata = build_match_momentum_series(bundle.match_momentum, int(match_row["match_id"]))
    goalkeeper_saves = build_match_goalkeeper_saves(player_rows, match_row)
    team_average_positions, average_position_metadata = build_match_team_average_positions(bundle, match_row, player_rows)
    filtered_matches = apply_match_filters(bundle.matches, filters)
    home_team_id = _safe_optional_int(match_row.get("home_id"))
    away_team_id = _safe_optional_int(match_row.get("away_id"))
    home_team_color = _resolve_team_color(bundle.teams, home_team_id, COLORS["accent"])
    away_team_color = _resolve_team_color(bundle.teams, away_team_id, COLORS["accent_alt"])
    if home_team_color == away_team_color:
        away_team_color = COLORS["accent_alt"]
    return MatchSummary(
        match_id=int(match_row["match_id"]),
        match_row=match_row,
        home_team_color=home_team_color,
        away_team_color=away_team_color,
        curated_stats=build_match_stat_table(bundle.team_stats, int(match_row["match_id"])),
        grouped_stats=grouped_stats,
        player_rows=player_rows,
        standout_players=standout_players,
        insight_cards=build_match_insight_cards(match_row, bundle.team_stats, standout_players),
        home_context_matches=build_team_context_matches(filtered_matches, int(match_row["home_id"]), int(match_row["match_id"])),
        away_context_matches=build_team_context_matches(filtered_matches, int(match_row["away_id"]), int(match_row["match_id"])),
        catalog_neighbors=build_catalog_neighbors(catalog, int(match_row["match_id"])),
        origin_context=origin_context or {},
        team_average_positions=team_average_positions,
        average_position_metadata=average_position_metadata,
        shot_events=shot_events,
        shot_events_metadata=shot_events_metadata,
        momentum_series=momentum_series,
        momentum_metadata=momentum_metadata,
        goalkeeper_saves=goalkeeper_saves,
    )
