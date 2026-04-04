from __future__ import annotations

from typing import Any

import streamlit as st


PAGES = ["Temporadas", "Overview", "Equipos", "Jugadores", "Partidos"]


def init_dashboard_state(team_ids: list[int]) -> None:
    defaults: dict[str, Any] = {
        "selected_season_year": None,
        "active_season_year": None,
        "nav_page": "Overview",
        "tournament_filter": None,
        "round_range_filter": None,
        "focus_team_id": team_ids[0] if team_ids else None,
        "focus_player_id": None,
        "focus_match_id": None,
        "player_context_match_id": None,
        "player_visual_mode": None,
        "player_visual_scope": None,
        "player_visual_match_id": None,
        "player_visual_owner_id": None,
        "players_team_filter": None,
        "players_position_filter": "Todas",
        "players_search": "",
        "matches_team_filter": None,
        "matches_venue_filter": "Todos",
        "matches_result_filter": "Todos",
        "nav_origin_page": None,
        "nav_origin_label": None,
        "nav_origin_state": {},
        "match_catalog_ids": [],
        "focus_match_index": 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_dashboard_context(team_ids: list[int], *, nav_page: str | None = None) -> None:
    st.session_state["tournament_filter"] = None
    st.session_state["round_range_filter"] = None
    st.session_state["focus_team_id"] = team_ids[0] if team_ids else None
    st.session_state["focus_player_id"] = None
    st.session_state["focus_match_id"] = None
    st.session_state["player_context_match_id"] = None
    st.session_state["player_visual_mode"] = None
    st.session_state["player_visual_scope"] = None
    st.session_state["player_visual_match_id"] = None
    st.session_state["player_visual_owner_id"] = None
    st.session_state["players_team_filter"] = None
    st.session_state["players_position_filter"] = "Todas"
    st.session_state["players_search"] = ""
    st.session_state["matches_team_filter"] = None
    st.session_state["matches_venue_filter"] = "Todos"
    st.session_state["matches_result_filter"] = "Todos"
    st.session_state["nav_origin_page"] = None
    st.session_state["nav_origin_label"] = None
    st.session_state["nav_origin_state"] = {}
    st.session_state["match_catalog_ids"] = []
    st.session_state["focus_match_index"] = 0
    st.session_state["nav_page"] = nav_page if nav_page in PAGES else st.session_state.get("nav_page", "Overview")


def pick_valid_option(value: Any, options: list[Any], fallback: Any | None = None) -> Any | None:
    if value in options:
        return value
    if fallback in options:
        return fallback
    return options[0] if options else fallback


def build_action(action_type: str, **payload: Any) -> dict[str, Any]:
    action = {"type": action_type}
    action.update(payload)
    return action


def _default_origin_label(page: str | None) -> str:
    if page == "Temporadas":
        return "Resumen de temporadas"
    if page == "Overview":
        return "Overview"
    if page == "Equipos":
        return "Explorador de equipos"
    if page == "Jugadores":
        return "Ranking de jugadores"
    if page == "Partidos":
        return "Explorador de partidos"
    return "Dashboard"


def _snapshot_page_state(page: str | None) -> dict[str, Any]:
    if page == "Equipos":
        return {
            "focus_team_id": st.session_state.get("focus_team_id"),
        }
    if page == "Jugadores":
        return {
            "focus_player_id": st.session_state.get("focus_player_id"),
            "players_team_filter": st.session_state.get("players_team_filter"),
            "players_position_filter": st.session_state.get("players_position_filter"),
            "players_search": st.session_state.get("players_search", ""),
            "player_visual_mode": st.session_state.get("player_visual_mode"),
            "player_visual_scope": st.session_state.get("player_visual_scope"),
            "player_visual_match_id": st.session_state.get("player_visual_match_id"),
        }
    if page == "Partidos":
        return {
            "focus_match_id": st.session_state.get("focus_match_id"),
            "focus_match_index": st.session_state.get("focus_match_index", 0),
            "matches_team_filter": st.session_state.get("matches_team_filter"),
            "matches_venue_filter": st.session_state.get("matches_venue_filter", "Todos"),
            "matches_result_filter": st.session_state.get("matches_result_filter", "Todos"),
        }
    return {}


def _restore_page_state(page: str | None, payload: dict[str, Any]) -> None:
    if not payload:
        return
    for key, value in payload.items():
        st.session_state[key] = value


def get_origin_context() -> dict[str, Any]:
    page = st.session_state.get("nav_origin_page")
    label = st.session_state.get("nav_origin_label")
    payload = st.session_state.get("nav_origin_state") or {}
    return {
        "page": page,
        "label": label or _default_origin_label(page),
        "state": payload,
        "has_origin": bool(page),
    }


def apply_navigation_action(action: dict[str, Any] | None) -> None:
    if not action:
        return

    action_type = action["type"]
    current_page = st.session_state.get("nav_page", "Overview")
    if action_type == "team":
        st.session_state["nav_page"] = "Equipos"
        st.session_state["focus_team_id"] = int(action["team_id"])
    elif action_type == "player":
        st.session_state["nav_page"] = "Jugadores"
        st.session_state["focus_player_id"] = int(action["player_id"])
        st.session_state["player_context_match_id"] = action.get("match_id")
        st.session_state["player_visual_mode"] = None
        st.session_state["player_visual_scope"] = None
        st.session_state["player_visual_match_id"] = None
        st.session_state["player_visual_owner_id"] = None
        if action.get("team_id") is not None:
            st.session_state["players_team_filter"] = int(action["team_id"])
        if action.get("position"):
            st.session_state["players_position_filter"] = action["position"]
    elif action_type == "match":
        should_capture_origin = bool(action.get("update_origin", current_page != "Partidos"))
        if should_capture_origin:
            origin_page = action.get("origin_page") or current_page
            st.session_state["nav_origin_page"] = origin_page
            st.session_state["nav_origin_label"] = action.get("origin_label") or _default_origin_label(origin_page)
            st.session_state["nav_origin_state"] = action.get("origin_state") or _snapshot_page_state(origin_page)
        st.session_state["nav_page"] = "Partidos"
        st.session_state["focus_match_id"] = int(action["match_id"])
        if action.get("venue") is not None:
            st.session_state["matches_venue_filter"] = action["venue"]
        if action.get("result") is not None:
            st.session_state["matches_result_filter"] = action["result"]
        if action.get("team_id") is not None:
            st.session_state["matches_team_filter"] = int(action["team_id"])
    elif action_type == "players_filter":
        st.session_state["nav_page"] = "Jugadores"
        st.session_state["players_team_filter"] = action.get("team_id")
        st.session_state["players_position_filter"] = action.get("position", "Todas")
    elif action_type == "matches_filter":
        st.session_state["nav_page"] = "Partidos"
        st.session_state["matches_team_filter"] = action.get("team_id")
        st.session_state["matches_venue_filter"] = action.get("venue", "Todos")
        st.session_state["matches_result_filter"] = action.get("result", "Todos")
    elif action_type == "return_origin":
        origin_page = st.session_state.get("nav_origin_page") or "Overview"
        st.session_state["nav_page"] = origin_page
        _restore_page_state(origin_page, st.session_state.get("nav_origin_state") or {})
    elif action_type == "page":
        st.session_state["nav_page"] = action["page"]
    elif action_type == "season":
        st.session_state["selected_season_year"] = int(action["season_year"])
        st.session_state["nav_page"] = action.get("page", "Overview")
    else:
        return

    st.rerun()
