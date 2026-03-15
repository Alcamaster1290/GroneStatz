from __future__ import annotations

import pandas as pd
import streamlit as st

from gronestats.dashboard.config import APP_SUBTITLE, APP_TITLE, DATA_DIR, DEFAULT_DASHBOARD_TOURNAMENTS, ROUND_RANGE_FALLBACK, SEASON_LABEL
from gronestats.dashboard.data import load_dashboard_data, parquet_signature, tournament_display_label, tournament_sort_key
from gronestats.dashboard.metrics import (
    build_league_overview,
    build_match_catalog,
    build_match_summary,
    build_player_profile,
    build_players_table,
    build_team_profile,
)
from gronestats.dashboard.models import FilterState
from gronestats.dashboard.state import PAGES, apply_navigation_action, get_origin_context, init_dashboard_state, pick_valid_option
from gronestats.dashboard.views.matches import render_match_catalog, render_match_detail
from gronestats.dashboard.views.overview import render_overview
from gronestats.dashboard.views.players import render_player_profile, render_players_table
from gronestats.dashboard.views.shared import (
    inject_base_styles,
    render_action_button,
    render_app_header,
    render_empty_state,
    render_section_title,
    render_selection_note,
)
from gronestats.dashboard.views.teams import render_team_view


def _safe_text(value: object, fallback: str) -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    return text or fallback


def _build_team_lookup(frame) -> dict[int, str]:
    if frame.empty:
        return {}
    return {
        int(row["team_id"]): _safe_text(row["team_name"], f"Equipo {int(row['team_id'])}")
        for _, row in frame.iterrows()
        if not pd.isna(row["team_id"])
    }


def _team_option_label(team_lookup: dict[int, str], value: int | None) -> str:
    if value is None:
        return "Todos los equipos"
    return team_lookup.get(int(value), f"Equipo {value}")


def _player_option_label(frame, value: int) -> str:
    selected = frame.loc[frame["player_id"] == value, ["name", "team_name"]]
    if selected.empty:
        return f"Jugador {value} | Sin equipo"
    row = selected.iloc[0]
    name = _safe_text(row.get("name"), f"Jugador {value}")
    team = _safe_text(row.get("team_name"), "Sin equipo")
    return f"{name} | {team}"


def _clamp_round_range(current: object, min_round: int, max_round: int) -> tuple[int, int]:
    if not isinstance(current, (tuple, list)) or len(current) != 2:
        return (min_round, max_round)
    start = max(min_round, min(int(current[0]), max_round))
    end = max(min_round, min(int(current[1]), max_round))
    if start > end:
        start, end = min_round, max_round
    return (start, end)


st.set_page_config(page_title=f"{APP_TITLE} | {SEASON_LABEL}", page_icon=":soccer:", layout="wide")
inject_base_styles()

bundle = load_dashboard_data(parquet_signature())
if bundle.matches.empty or bundle.teams.empty or bundle.players.empty or bundle.player_match.empty:
    st.error(f"No se pudieron cargar los parquets requeridos desde {DATA_DIR}.")
    st.stop()

team_options = bundle.teams[["team_id", "team_name"]].dropna().sort_values("team_name")
team_ids = team_options["team_id"].astype(int).tolist()
team_lookup = _build_team_lookup(team_options)
init_dashboard_state(team_ids)

tournament_values = []
if "tournament" in bundle.matches.columns:
    tournament_values = sorted(bundle.matches["tournament"].dropna().astype(str).unique().tolist(), key=tournament_sort_key)
default_tournaments = [value for value in DEFAULT_DASHBOARD_TOURNAMENTS if value in tournament_values] or tournament_values
selected_tournament_state = st.session_state.get("tournament_filter")
if not isinstance(selected_tournament_state, list):
    st.session_state["tournament_filter"] = default_tournaments
else:
    valid_selected = [value for value in selected_tournament_state if value in tournament_values]
    st.session_state["tournament_filter"] = valid_selected or default_tournaments

with st.sidebar:
    st.markdown(f"## {APP_TITLE}")
    st.caption(f"{APP_SUBTITLE} | {SEASON_LABEL}")
    st.caption("Filtra por torneo y rango de rondas. El dashboard abre combinado en Apertura + Clausura y deja Grand Final como capa opcional.")
    st.divider()
    selected_tournaments = st.multiselect(
        "Torneos",
        options=tournament_values,
        default=st.session_state["tournament_filter"],
        key="tournament_filter",
        format_func=tournament_display_label,
    )
    if not selected_tournaments:
        selected_tournaments = default_tournaments
        st.session_state["tournament_filter"] = default_tournaments
    tournament_scope = (
        bundle.matches[bundle.matches["tournament"].isin(selected_tournaments)].copy()
        if selected_tournaments and "tournament" in bundle.matches.columns
        else bundle.matches.copy()
    )
    round_min = int(tournament_scope["round_number"].min()) if not tournament_scope.empty else ROUND_RANGE_FALLBACK[0]
    round_max = int(tournament_scope["round_number"].max()) if not tournament_scope.empty else ROUND_RANGE_FALLBACK[1]
    st.session_state["round_range_filter"] = _clamp_round_range(
        st.session_state.get("round_range_filter"),
        round_min,
        round_max,
    )
    round_range = st.slider(
        "Rango de rondas",
        min_value=round_min,
        max_value=round_max,
        value=st.session_state["round_range_filter"],
        key="round_range_filter",
    )
    min_minutes = st.slider(
        "Minimo de minutos para rankings",
        min_value=0,
        max_value=1500,
        step=45,
        value=180,
    )
    st.divider()
    st.caption(f"Parquets: `{DATA_DIR}`")
    st.caption(f"Cargado: {bundle.loaded_at.strftime('%d/%m/%Y %H:%M:%S')}")

filters = FilterState(round_range=round_range, min_minutes=min_minutes, tournaments=tuple(selected_tournaments))

st.caption("Navega con botones, tablas y cards contextuales. El sidebar queda solo para filtros globales.")
nav_cols = st.columns(len(PAGES), gap="small")
for column, label in zip(nav_cols, PAGES):
    with column:
        if render_action_button(
            label,
            key=f"nav_button_{label}",
            width="stretch",
            variant="active" if st.session_state["nav_page"] == label else "secondary",
        ):
            if st.session_state["nav_page"] != label:
                st.session_state["nav_page"] = label
                st.rerun()

page = st.session_state["nav_page"]

if page == "Overview":
    render_app_header(
        page_title="Panorama general de Liga 1 2025",
        subtitle="El overview funciona como centro de mando de los torneos y rondas activas: tabla, lideres, partidos destacados y forma reciente con saltos directos a cada capa del analisis.",
        loaded_at=bundle.loaded_at,
    )
    overview_action = render_overview(build_league_overview(bundle, filters))
    apply_navigation_action(overview_action)

elif page == "Equipos":
    render_app_header(
        page_title="Explorador de equipos",
        subtitle="Sigue el hilo desde la tabla a cada club, y desde cada club baja a partidos y jugadores sin perder el rango global de torneos y rondas activos.",
        loaded_at=bundle.loaded_at,
    )
    st.session_state["focus_team_id"] = pick_valid_option(st.session_state["focus_team_id"], team_ids, team_ids[0] if team_ids else None)
    team_id = st.selectbox(
        "Equipo",
        options=team_ids,
        key="focus_team_id",
        format_func=lambda value: _team_option_label(team_lookup, value),
    )
    team_action = render_team_view(build_team_profile(bundle, filters, int(team_id)))
    apply_navigation_action(team_action)

elif page == "Jugadores":
    render_app_header(
        page_title="Ranking y perfiles de jugadores",
        subtitle="Cruza volumen, produccion por 90, heatmap acumulado y forma reciente. Desde aqui puedes volver al club o saltar al partido asociado.",
        loaded_at=bundle.loaded_at,
    )
    player_team_options = [None] + team_ids
    st.session_state["players_team_filter"] = pick_valid_option(st.session_state["players_team_filter"], player_team_options, None)
    col_a, col_b, col_c = st.columns([1.15, 0.85, 1.15], gap="medium")
    with col_a:
        selected_team = st.selectbox(
            "Equipo",
            options=player_team_options,
            key="players_team_filter",
            format_func=lambda value: _team_option_label(team_lookup, value),
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
    else:
        player_ids = table["player_id"].astype(int).tolist()
        st.session_state["focus_player_id"] = pick_valid_option(
            st.session_state["focus_player_id"],
            player_ids,
            player_ids[0],
        )
        player_id = st.selectbox(
            "Perfil individual",
            options=player_ids,
            key="focus_player_id",
            format_func=lambda value: _player_option_label(table, value),
        )
        player_action = render_player_profile(
            build_player_profile(
                bundle,
                filters,
                int(player_id),
                context_match_id=st.session_state.get("player_context_match_id"),
                visual_match_id=st.session_state.get("player_visual_match_id"),
            )
        )
        apply_navigation_action(player_action)

elif page == "Partidos":
    render_app_header(
        page_title="Explorador de partidos",
        subtitle="La vista de partidos prioriza el detalle focal. El catalogo queda oculto bajo demanda para que el analisis gane ancho sin perder navegacion contextual.",
        loaded_at=bundle.loaded_at,
    )
    match_team_options = [None] + team_ids
    st.session_state["matches_team_filter"] = pick_valid_option(st.session_state["matches_team_filter"], match_team_options, None)
    col_a, col_b, col_c = st.columns([1.2, 0.78, 0.9], gap="medium")
    with col_a:
        selected_team = st.selectbox(
            "Equipo",
            options=match_team_options,
            key="matches_team_filter",
            format_func=lambda value: _team_option_label(team_lookup, value),
        )
    with col_b:
        venue_filter = st.selectbox("Condicion", ["Todos", "Local", "Visita"], key="matches_venue_filter")
    with col_c:
        result_filter = st.selectbox("Resultado", ["Todos", "Victorias locales", "Empates", "Victorias visitantes"], key="matches_result_filter")

    catalog = build_match_catalog(bundle, filters, team_id=selected_team, venue_filter=venue_filter, result_filter=result_filter)
    if catalog.empty:
        st.session_state["match_catalog_ids"] = []
        render_empty_state("No hay partidos disponibles con esa combinacion de filtros.")
    else:
        match_ids = catalog["match_id"].astype(int).tolist()
        st.session_state["match_catalog_ids"] = match_ids
        st.session_state["focus_match_id"] = pick_valid_option(
            st.session_state["focus_match_id"],
            match_ids,
            match_ids[0],
        )
        active_match_row = catalog[catalog["match_id"] == st.session_state["focus_match_id"]].head(1)
        active_match_label = (
            _safe_text(active_match_row.iloc[0].get("partido"), "Partido activo")
            if not active_match_row.empty
            else "Partido activo"
        )
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
                    <span>Regular hasta ronda {REGULAR_SEASON_MAX_ROUND}</span>
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
            st.session_state["focus_match_id"] = int(selected_from_catalog)

        selected_match = int(st.session_state["focus_match_id"])
        st.session_state["focus_match_index"] = match_ids.index(selected_match)
        match_action = render_match_detail(
            build_match_summary(
                bundle,
                filters,
                selected_match,
                catalog,
                origin_context=get_origin_context(),
            )
        )
        apply_navigation_action(match_action)
