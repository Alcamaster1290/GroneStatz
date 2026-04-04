from __future__ import annotations

import pandas as pd
import streamlit as st

from gronestats.dashboard.config import ROUND_RANGE_FALLBACK
from gronestats.dashboard.metrics import (
    build_league_overview,
    build_match_catalog,
    build_match_summary,
    build_player_profile,
    build_players_table,
    build_team_profile,
)
from gronestats.dashboard.models import ConsolidatedSeasonOverview, DatasetBundle, FilterState, SeasonDataset
from gronestats.dashboard.state import get_origin_context, pick_valid_option
from gronestats.dashboard.views.matches import render_match_catalog, render_match_detail
from gronestats.dashboard.views.overview import render_overview
from gronestats.dashboard.views.players import render_player_profile, render_players_table
from gronestats.dashboard.views.seasons import render_seasons_overview
from gronestats.dashboard.views.shared import (
    render_app_header,
    render_empty_state,
    render_section_title,
    render_selection_note,
    safe_text,
)
from gronestats.dashboard.views.teams import render_team_view


def build_team_lookup(frame: pd.DataFrame) -> dict[int, str]:
    if frame.empty:
        return {}
    return {
        int(row["team_id"]): safe_text(row["team_name"], f"Equipo {int(row['team_id'])}")
        for _, row in frame.iterrows()
        if not pd.isna(row["team_id"])
    }


def team_option_label(team_lookup: dict[int, str], value: int | None) -> str:
    if value is None:
        return "Todos los equipos"
    return team_lookup.get(int(value), f"Equipo {value}")


def player_option_label(frame: pd.DataFrame, value: int) -> str:
    selected = frame.loc[frame["player_id"] == value, ["name", "team_name"]]
    if selected.empty:
        return f"Jugador {value} | Sin equipo"
    row = selected.iloc[0]
    return f"{safe_text(row.get('name'), f'Jugador {value}')} | {safe_text(row.get('team_name'), 'Sin equipo')}"


def clamp_round_range(current: object, min_round: int, max_round: int) -> tuple[int, int]:
    if not isinstance(current, (tuple, list)) or len(current) != 2:
        return (min_round, max_round)
    start = max(min_round, min(int(current[0]), max_round))
    end = max(min_round, min(int(current[1]), max_round))
    if start > end:
        return (min_round, max_round)
    return (start, end)


def derive_round_bounds(matches: pd.DataFrame, selected_tournaments: list[str]) -> tuple[int, int]:
    tournament_scope = (
        matches[matches["tournament"].isin(selected_tournaments)].copy()
        if selected_tournaments and "tournament" in matches.columns
        else matches.copy()
    )
    if tournament_scope.empty or "round_number" not in tournament_scope.columns:
        return ROUND_RANGE_FALLBACK
    return (int(tournament_scope["round_number"].min()), int(tournament_scope["round_number"].max()))


def render_seasons_page(
    bundle: DatasetBundle,
    season_catalog: tuple[SeasonDataset, ...],
    consolidated_overview: ConsolidatedSeasonOverview,
) -> dict[str, object] | None:
    render_app_header(
        page_title="Resumen consolidado por temporada",
        subtitle="Compara cobertura, volumen y publicacion entre temporadas sin salir del dashboard. Desde aqui puedes saltar directo al overview anual activo.",
        loaded_at=bundle.loaded_at,
        season_label=bundle.season_label,
        coverage_label=bundle.coverage_label,
    )
    return render_seasons_overview(
        consolidated_overview,
        season_catalog=season_catalog,
        active_season_year=bundle.season_year,
    )


def render_overview_page(bundle: DatasetBundle, filters: FilterState, *, scope_summary: str) -> dict[str, object] | None:
    render_app_header(
        page_title=f"Panorama general de {bundle.season_label}",
        subtitle="El overview funciona como centro de mando de los filtros activos: tabla, lideres, partidos destacados y forma reciente con saltos directos a cada capa del analisis.",
        loaded_at=bundle.loaded_at,
        season_label=bundle.season_label,
        coverage_label=bundle.coverage_label,
        scope_summary=scope_summary,
    )
    return render_overview(build_league_overview(bundle, filters))


def render_teams_page(
    bundle: DatasetBundle,
    filters: FilterState,
    team_ids: list[int],
    team_lookup: dict[int, str],
    *,
    scope_summary: str,
) -> dict[str, object] | None:
    render_app_header(
        page_title="Explorador de equipos",
        subtitle="Sigue el hilo desde la tabla a cada club, y desde cada club baja a partidos y jugadores sin perder los filtros activos.",
        loaded_at=bundle.loaded_at,
        season_label=bundle.season_label,
        coverage_label=bundle.coverage_label,
        scope_summary=scope_summary,
    )
    if not team_ids:
        render_empty_state("No hay equipos disponibles con la release activa. Se requieren fixtures con IDs de equipo reutilizables.")
        return None

    st.session_state["focus_team_id"] = pick_valid_option(st.session_state.get("focus_team_id"), team_ids, team_ids[0])
    team_id = st.selectbox(
        "Equipo",
        options=team_ids,
        key="focus_team_id",
        format_func=lambda value: team_option_label(team_lookup, value),
    )
    return render_team_view(
        build_team_profile(bundle, filters, int(team_id)),
        player_layer_available=bundle.has_player_layer,
    )


def render_players_page(
    bundle: DatasetBundle,
    filters: FilterState,
    team_ids: list[int],
    team_lookup: dict[int, str],
    *,
    scope_summary: str,
) -> dict[str, object] | None:
    render_app_header(
        page_title="Ranking y perfiles de jugadores",
        subtitle="Cruza volumen, produccion por 90, heatmap acumulado y forma reciente. Desde aqui puedes volver al club o saltar al partido asociado.",
        loaded_at=bundle.loaded_at,
        season_label=bundle.season_label,
        coverage_label=bundle.coverage_label,
        scope_summary=scope_summary,
    )
    if not bundle.has_player_layer:
        render_empty_state(
            "Esta temporada aun no publica `player_match`. El ranking y los perfiles se habilitan cuando entren estadisticas individuales."
        )
        return None

    player_team_options = [None] + team_ids
    st.session_state["players_team_filter"] = pick_valid_option(st.session_state.get("players_team_filter"), player_team_options, None)
    col_a, col_b, col_c = st.columns([1.15, 0.85, 1.15], gap="medium")
    with col_a:
        selected_team = st.selectbox(
            "Equipo",
            options=player_team_options,
            key="players_team_filter",
            format_func=lambda value: team_option_label(team_lookup, value),
        )
    with col_b:
        selected_position = st.selectbox("Posicion", options=["Todas", "G", "D", "M", "F"], key="players_position_filter")
    with col_c:
        player_search = st.text_input("Buscar jugador", placeholder="Nombre o apellido", key="players_search")

    render_section_title("Tabla de jugadores", "Selecciona una fila para fijar el perfil.")
    table = build_players_table(
        bundle,
        filters,
        team_id=selected_team,
        position=None if selected_position == "Todas" else selected_position,
        search=player_search or None,
    )
    selected_from_table = render_players_table(table)
    if selected_from_table is not None:
        st.session_state["focus_player_id"] = int(selected_from_table)

    if table.empty:
        render_empty_state("Amplia filtros o reduce el minimo de minutos para ver perfiles.")
        return None

    player_ids = table["player_id"].astype(int).tolist()
    st.session_state["focus_player_id"] = pick_valid_option(
        st.session_state.get("focus_player_id"),
        player_ids,
        player_ids[0],
    )
    player_id = st.selectbox(
        "Perfil individual",
        options=player_ids,
        key="focus_player_id",
        format_func=lambda value: player_option_label(table, value),
    )
    return render_player_profile(
        build_player_profile(
            bundle,
            filters,
            int(player_id),
            context_match_id=st.session_state.get("player_context_match_id"),
            visual_match_id=st.session_state.get("player_visual_match_id"),
        )
    )


def render_matches_page(
    bundle: DatasetBundle,
    filters: FilterState,
    team_ids: list[int],
    team_lookup: dict[int, str],
    *,
    scope_summary: str,
) -> dict[str, object] | None:
    render_app_header(
        page_title="Explorador de partidos",
        subtitle="La vista de partidos prioriza el detalle focal. El catalogo queda oculto bajo demanda para que el analisis gane ancho sin perder navegacion contextual.",
        loaded_at=bundle.loaded_at,
        season_label=bundle.season_label,
        coverage_label=bundle.coverage_label,
        scope_summary=scope_summary,
    )
    match_team_options = [None] + team_ids
    st.session_state["matches_team_filter"] = pick_valid_option(st.session_state.get("matches_team_filter"), match_team_options, None)
    col_a, col_b, col_c = st.columns([1.2, 0.78, 0.9], gap="medium")
    with col_a:
        selected_team = st.selectbox(
            "Equipo",
            options=match_team_options,
            key="matches_team_filter",
            format_func=lambda value: team_option_label(team_lookup, value),
        )
    with col_b:
        venue_filter = st.selectbox("Condicion", ["Todos", "Local", "Visita"], key="matches_venue_filter")
    with col_c:
        result_filter = st.selectbox("Resultado", ["Todos", "Victorias locales", "Empates", "Victorias visitantes"], key="matches_result_filter")

    catalog = build_match_catalog(bundle, filters, team_id=selected_team, venue_filter=venue_filter, result_filter=result_filter)
    if catalog.empty:
        st.session_state["match_catalog_ids"] = []
        render_empty_state("No hay partidos disponibles con esa combinacion de filtros.")
        return None

    match_ids = catalog["match_id"].astype(int).tolist()
    st.session_state["match_catalog_ids"] = match_ids
    st.session_state["focus_match_id"] = pick_valid_option(
        st.session_state.get("focus_match_id"),
        match_ids,
        match_ids[0],
    )
    active_match_row = catalog[catalog["match_id"] == st.session_state["focus_match_id"]].head(1)
    active_match_label = safe_text(active_match_row.iloc[0].get("partido"), "Partido activo") if not active_match_row.empty else "Partido activo"

    toolbar_cols = st.columns([1.45, 0.82], gap="medium")
    selected_from_catalog = None
    with toolbar_cols[0]:
        st.markdown(
            f"""
            <div class="gs-match-switcher">
              <p class="gs-match-switcher__title">{active_match_label}</p>
              <p class="gs-match-switcher__note">Detalle activo dentro del catalogo filtrado. El listado queda bajo demanda para liberar ancho.</p>
              <div class="gs-match-switcher__meta">
                <span>{len(match_ids)} partidos filtrados</span>
                <span>{scope_summary}</span>
                <span>Contexto activo</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with toolbar_cols[1]:
        with st.popover("Catalogo de partidos", use_container_width=True):
            render_section_title("Catalogo filtrado", "Selector rapido de partidos.")
            render_selection_note("El activo queda marcado y el detalle conserva todo el ancho.")
            selected_from_catalog = render_match_catalog(catalog, st.session_state["focus_match_id"])
    if selected_from_catalog is not None:
        st.session_state["focus_match_id"] = pick_valid_option(selected_from_catalog, match_ids, match_ids[0])

    st.session_state["focus_match_index"] = match_ids.index(int(st.session_state["focus_match_id"]))
    return render_match_detail(
        build_match_summary(
            bundle,
            filters,
            int(st.session_state["focus_match_id"]),
            catalog,
            origin_context=get_origin_context(),
        )
    )


def render_page(
    page: str,
    bundle: DatasetBundle,
    filters: FilterState,
    team_ids: list[int],
    team_lookup: dict[int, str],
    season_catalog: tuple[SeasonDataset, ...],
    consolidated_overview: ConsolidatedSeasonOverview,
    *,
    scope_summary: str,
) -> dict[str, object] | None:
    if page == "Temporadas":
        return render_seasons_page(bundle, season_catalog, consolidated_overview)
    if page == "Overview":
        return render_overview_page(bundle, filters, scope_summary=scope_summary)
    if page == "Equipos":
        return render_teams_page(bundle, filters, team_ids, team_lookup, scope_summary=scope_summary)
    if page == "Jugadores":
        return render_players_page(bundle, filters, team_ids, team_lookup, scope_summary=scope_summary)
    if page == "Partidos":
        return render_matches_page(bundle, filters, team_ids, team_lookup, scope_summary=scope_summary)
    return None
