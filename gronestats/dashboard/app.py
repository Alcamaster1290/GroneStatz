from __future__ import annotations

import streamlit as st

from gronestats.data_layout import season_layout
from gronestats.dashboard.config import APP_SUBTITLE, APP_TITLE, DEFAULT_DASHBOARD_TOURNAMENTS, LEAGUE_NAME
from gronestats.dashboard.data import (
    build_team_options,
    describe_active_scope,
    describe_bundle_gaps,
    load_consolidated_season_overview,
    load_dashboard_data,
    load_season_catalog,
    resolve_default_season_year,
    resolve_season_dataset,
    season_catalog_signature,
    season_parquet_signature,
    tournament_display_label,
    tournament_sort_key,
)
from gronestats.dashboard.models import FilterState
from gronestats.dashboard.pages import build_team_lookup, clamp_round_range, derive_round_bounds, render_page
from gronestats.dashboard.state import PAGES, apply_navigation_action, init_dashboard_state, reset_dashboard_context
from gronestats.dashboard.views.shared import inject_base_styles, render_action_button, render_selection_note


st.set_page_config(page_title=f"{APP_TITLE} | Dashboard", page_icon=":soccer:", layout="wide")
inject_base_styles()

catalog_signature = season_catalog_signature()
season_catalog = load_season_catalog(catalog_signature)
if not season_catalog:
    sample_dir = season_layout(2026, league=LEAGUE_NAME).dashboard.current_dir
    st.error(f"No se encontraron temporadas publicadas en `{sample_dir.parent.parent.parent}/*/dashboard/current`.")
    st.stop()

season_options = [dataset.season_year for dataset in season_catalog]
season_lookup = {dataset.season_year: dataset for dataset in season_catalog}
init_dashboard_state([])
if st.session_state.get("selected_season_year") not in season_options:
    st.session_state["selected_season_year"] = resolve_default_season_year(season_catalog)

selected_season_year = int(st.session_state["selected_season_year"])
bundle = load_dashboard_data(selected_season_year, season_parquet_signature(selected_season_year))
if not bundle.has_schedule:
    st.error(f"No se pudieron cargar los parquets base de partidos desde {bundle.data_dir}.")
    st.stop()

consolidated_overview = load_consolidated_season_overview(catalog_signature)
team_options = build_team_options(bundle)
team_ids = team_options["team_id"].astype(int).tolist()
team_lookup = build_team_lookup(team_options)
coverage_notes = describe_bundle_gaps(bundle)
init_dashboard_state(team_ids)
if st.session_state.get("active_season_year") != bundle.season_year:
    reset_dashboard_context(team_ids, nav_page=st.session_state.get("nav_page", "Overview"))
    st.session_state["active_season_year"] = bundle.season_year


def _season_option_label(season_year: int) -> str:
    dataset = resolve_season_dataset(season_year, season_catalog)
    if dataset is None:
        return str(season_year)
    suffix = f"{dataset.warning_count} warnings" if dataset.warning_count else dataset.validation_status
    return f"{dataset.season_label} | {suffix}"


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
    selected_season_year = st.selectbox(
        "Temporada",
        options=season_options,
        key="selected_season_year",
        format_func=_season_option_label,
    )
    selected_dataset = season_lookup.get(int(selected_season_year))
    st.caption(f"{APP_SUBTITLE} | {bundle.season_label}")
    if selected_dataset is not None:
        st.caption(selected_dataset.coverage_label)
    if coverage_notes:
        st.caption("Cobertura parcial")
        for note in coverage_notes:
            st.caption(f"- {note}")
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
    round_min, round_max = derive_round_bounds(bundle.matches, selected_tournaments)
    st.session_state["round_range_filter"] = clamp_round_range(
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
    st.caption(f"Parquets: `{bundle.data_dir}`")
    st.caption(f"Release: `{bundle.manifest.get('release_id', '-')}`")
    st.caption(f"Cargado: {bundle.loaded_at.strftime('%d/%m/%Y %H:%M:%S')}")

filters = FilterState(round_range=round_range, min_minutes=min_minutes, tournaments=tuple(selected_tournaments))
scope_summary = describe_active_scope(bundle.matches, filters)
page_enabled = {
    "Temporadas": True,
    "Overview": bundle.has_schedule,
    "Equipos": bool(team_ids),
    "Jugadores": bundle.has_player_layer,
    "Partidos": bundle.has_schedule,
}
page_help = {
    "Equipos": "Se habilita cuando exista un catalogo de equipos o IDs reutilizables desde los fixtures.",
    "Jugadores": "Se habilita cuando exista `player_match` publicado para la temporada activa.",
}
if not page_enabled.get(st.session_state["nav_page"], True):
    st.session_state["nav_page"] = "Overview"

if coverage_notes:
    render_selection_note("Cobertura parcial activa: algunas capas analiticas todavia no estan publicadas para esta temporada.")

st.caption("Navega con botones, tablas y cards contextuales. El sidebar queda solo para filtros globales.")
nav_cols = st.columns(len(PAGES), gap="small")
for column, label in zip(nav_cols, PAGES):
    with column:
        if render_action_button(
            label,
            key=f"nav_button_{label}",
            width="stretch",
            variant="active" if st.session_state["nav_page"] == label else "secondary",
            disabled=not page_enabled.get(label, True),
            help=page_help.get(label),
        ):
            if st.session_state["nav_page"] != label:
                st.session_state["nav_page"] = label
                st.rerun()

page = st.session_state["nav_page"]
page_action = render_page(
    page,
    bundle,
    filters,
    team_ids,
    team_lookup,
    season_catalog,
    consolidated_overview,
    scope_summary=scope_summary,
)
apply_navigation_action(page_action)
