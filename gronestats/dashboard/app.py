from __future__ import annotations

import streamlit as st

from gronestats.dashboard.config import APP_SUBTITLE, APP_TITLE, DATA_DIR, DEFAULT_DASHBOARD_TOURNAMENTS, SEASON_LABEL
from gronestats.dashboard.data import describe_active_scope, load_dashboard_data, parquet_signature, tournament_display_label, tournament_sort_key
from gronestats.dashboard.models import FilterState
from gronestats.dashboard.pages import build_team_lookup, clamp_round_range, derive_round_bounds, render_page
from gronestats.dashboard.state import PAGES, apply_navigation_action, init_dashboard_state
from gronestats.dashboard.views.shared import inject_base_styles, render_action_button


st.set_page_config(page_title=f"{APP_TITLE} | {SEASON_LABEL}", page_icon=":soccer:", layout="wide")
inject_base_styles()

bundle = load_dashboard_data(parquet_signature())
if bundle.matches.empty or bundle.teams.empty or bundle.players.empty or bundle.player_match.empty:
    st.error(f"No se pudieron cargar los parquets requeridos desde {DATA_DIR}.")
    st.stop()

team_options = bundle.teams[["team_id", "team_name"]].dropna().sort_values("team_name")
team_ids = team_options["team_id"].astype(int).tolist()
team_lookup = build_team_lookup(team_options)
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
    st.caption(f"Parquets: `{DATA_DIR}`")
    st.caption(f"Cargado: {bundle.loaded_at.strftime('%d/%m/%Y %H:%M:%S')}")

filters = FilterState(round_range=round_range, min_minutes=min_minutes, tournaments=tuple(selected_tournaments))
scope_summary = describe_active_scope(bundle.matches, filters)

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
page_action = render_page(
    page,
    bundle,
    filters,
    team_ids,
    team_lookup,
    scope_summary=scope_summary,
)
apply_navigation_action(page_action)
