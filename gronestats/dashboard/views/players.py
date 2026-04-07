from __future__ import annotations

import streamlit as st

from gronestats.dashboard.data import find_player_image
from gronestats.dashboard.metrics import (
    PLAYER_ACCUMULATED_SCOPE,
    PLAYER_AVERAGE_POSITION_MODE,
    PLAYER_CONTEXTUAL_SCOPE,
    PLAYER_HEATMAP_MODE,
)
from gronestats.dashboard.models import PlayerProfile
from gronestats.dashboard.state import build_action
from gronestats.dashboard.views.pitch import build_player_average_position_figure, build_player_heatmap_figure
from gronestats.dashboard.views.shared import (
    build_percentile_figure,
    get_selected_row_index,
    render_empty_state,
    render_identity_panel,
    render_metric_cards,
    render_navigation_surface,
    render_panel_close,
    render_panel_open,
    render_section_title,
    render_selection_note,
    safe_optional_int,
    safe_text,
)


def _format_match_option(visual_matches, value: int) -> str:
    selected = visual_matches.loc[visual_matches["match_id"] == value, "partido"]
    if selected.empty:
        return f"Partido {value}"
    return safe_text(selected.iloc[0], f"Partido {value}")


def _format_rounds_label(rounds: list[str]) -> str:
    if not rounds:
        return "sin tramos disponibles"
    if len(rounds) == 1:
        return rounds[0]
    if len(rounds) <= 4:
        return ", ".join(rounds)
    return f"{rounds[0]} ... {rounds[-1]}"


def _describe_available_views(profile: PlayerProfile, selected_match_row) -> str:
    available = []
    if selected_match_row is not None and bool(selected_match_row.get("has_average_position")):
        available.append("posicion promedio contextual")
    if selected_match_row is not None and bool(selected_match_row.get("has_heatmap")):
        available.append("heatmap contextual")
    if profile.accumulated_average_position_row is not None:
        available.append("posicion promedio acumulada")
    if not profile.accumulated_heatmap_points.empty:
        available.append("heatmap acumulado")
    return ", ".join(available) if available else "ninguna vista disponible"


def render_players_table(table) -> int | None:
    if table.empty:
        render_empty_state("No hay jugadores que cumplan con los filtros activos.")
        return None

    render_selection_note("La fila seleccionada fija el perfil y habilita saltos a equipo o partido.")
    event = st.dataframe(
        table[
            [
                "name",
                "team_name",
                "position",
                "minutesplayed",
                "matches_played",
                "goals",
                "assists",
                "goals_per90",
                "assists_per90",
                "goal_actions_per90",
            ]
        ],
        use_container_width=True,
        hide_index=True,
        key="players_table",
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "name": "Jugador",
            "team_name": "Equipo",
            "position": "Pos",
            "minutesplayed": "Min",
            "matches_played": "PJ",
            "goals": "G",
            "assists": "A",
            "goals_per90": "G/90",
            "assists_per90": "A/90",
            "goal_actions_per90": "G+A/90",
        },
    )
    row_index = get_selected_row_index(event)
    if row_index is None:
        return None
    return safe_optional_int(table.iloc[row_index].get("player_id"))


def render_player_profile(profile: PlayerProfile | None) -> dict[str, object] | None:
    if profile is None:
        render_empty_state("Selecciona un jugador con minutos suficientes en el rango actual.")
        return None

    action: dict[str, object] | None = None
    team_id = safe_optional_int(profile.player_row.get("team_id"))

    top_left, top_right = st.columns([0.98, 1.22], gap="medium")
    with top_left:
        render_identity_panel(
            title=safe_text(profile.player_row.get("name"), f"Jugador {profile.player_id}"),
            subtitle="Perfil individual y comparacion relativa dentro de su cohorte posicional.",
            image_path=find_player_image(int(profile.player_id)),
            metadata=[f"{key}: {value}" for key, value in profile.summary.items() if key in {"Equipo", "Posicion", "Partidos"}],
            accent_color=profile.team_color,
            accent_label="Color del club actual",
        )

        action_cols = st.columns(2, gap="small")
        with action_cols[0]:
            if action is None and team_id is not None and render_navigation_surface(
                title="Equipo del jugador",
                note="Vuelve al club sin perder el rango global.",
                key=f"player_go_team_{profile.player_id}",
                button_label="Abrir equipo",
                eyebrow="Relacion directa",
                metadata=[str(profile.summary.get("Equipo", "Sin equipo")), str(profile.summary.get("Posicion", "-"))],
                variant="primary",
                accent_color=profile.team_color,
            ):
                action = build_action("team", team_id=int(team_id))
        with action_cols[1]:
            if action is None and team_id is not None and render_navigation_surface(
                title="Partidos del equipo",
                note="Abre el contexto competitivo del club.",
                key=f"player_go_matches_{profile.player_id}",
                button_label="Ver partidos",
                eyebrow="Contexto",
                metadata=[str(profile.summary.get("Equipo", "Sin equipo")), "Partidos"],
                variant="secondary",
                accent_color=profile.team_color,
            ):
                action = build_action("matches_filter", team_id=int(team_id), venue="Todos", result="Todos")

        extra_metric_label = "Atajadas / 90" if safe_text(profile.summary.get("Posicion"), "-") == "G" else "G+A / 90"
        extra_metric_value = (
            profile.percentiles.loc[profile.percentiles["Metric"] == "Atajadas / 90", "value"].iloc[0]
            if extra_metric_label == "Atajadas / 90" and "Atajadas / 90" in profile.percentiles["Metric"].values
            else profile.percentiles.loc[profile.percentiles["Metric"] == "Acciones de gol / 90", "value"].iloc[0]
            if extra_metric_label == "G+A / 90" and "Acciones de gol / 90" in profile.percentiles["Metric"].values
            else 0.0
        )
        cards = [
            {"label": "Minutos", "value": str(profile.summary["Minutos"]), "help": "Carga de juego."},
            {"label": "Partidos", "value": str(profile.summary["Partidos"]), "help": "Apariciones."},
            {"label": "Goles", "value": str(profile.summary["Goles"]), "help": "Produccion."},
            {"label": "Asistencias", "value": str(profile.summary["Asistencias"]), "help": "Creacion."},
            {"label": extra_metric_label, "value": str(extra_metric_value), "help": "Senal oficial del rendimiento individual."},
        ]
        render_metric_cards(cards)

    with top_right:
        render_section_title(
            "Mapa del jugador",
            "Cruza capa visual y alcance entre partido contextual y acumulado del tramo regular.",
        )
        render_panel_open()
        if profile.available_visual_matches.empty:
            render_empty_state("No hay mapas posicionales disponibles para este jugador en el rango filtrado.")
        else:
            visual_matches = profile.available_visual_matches.copy()
            match_options = visual_matches["match_id"].dropna().astype(int).tolist()
            mode_options = [PLAYER_AVERAGE_POSITION_MODE, PLAYER_HEATMAP_MODE]
            scope_options = [PLAYER_CONTEXTUAL_SCOPE, PLAYER_ACCUMULATED_SCOPE]

            if st.session_state.get("player_visual_owner_id") != profile.player_id:
                st.session_state["player_visual_owner_id"] = profile.player_id
                st.session_state["player_visual_mode"] = profile.default_visual_mode
                st.session_state["player_visual_scope"] = profile.default_visual_scope
                st.session_state["player_visual_match_id"] = profile.default_visual_match_id

            if st.session_state.get("player_visual_mode") not in mode_options:
                st.session_state["player_visual_mode"] = profile.default_visual_mode
            if st.session_state.get("player_visual_scope") not in scope_options:
                st.session_state["player_visual_scope"] = profile.default_visual_scope
            if st.session_state.get("player_visual_match_id") not in match_options:
                st.session_state["player_visual_match_id"] = profile.default_visual_match_id

            controls = st.columns([1.0, 1.0, 1.3], gap="medium")
            with controls[0]:
                selected_mode = st.radio(
                    "Capa",
                    options=mode_options,
                    key="player_visual_mode",
                    horizontal=True,
                )
            with controls[1]:
                selected_scope = st.radio(
                    "Alcance",
                    options=scope_options,
                    key="player_visual_scope",
                    horizontal=True,
                )
            with controls[2]:
                if selected_scope == PLAYER_CONTEXTUAL_SCOPE:
                    selected_match_id = st.selectbox(
                        "Partido contextual",
                        options=match_options,
                        key="player_visual_match_id",
                        format_func=lambda value: _format_match_option(visual_matches, value),
                    )
                else:
                    selected_match_id = st.session_state.get("player_visual_match_id") or profile.default_visual_match_id

            coverage = profile.visual_coverage or {}
            if selected_scope == PLAYER_CONTEXTUAL_SCOPE:
                average_match_count = int(coverage.get("average_match_count", 0))
                heatmap_match_count = int(coverage.get("heatmap_match_count", 0))
                average_rounds = coverage.get("average_round_labels", [])
                heatmap_rounds = coverage.get("heatmap_round_labels", [])
            else:
                average_match_count = int(coverage.get("regular_average_match_count", 0))
                heatmap_match_count = int(coverage.get("regular_heatmap_match_count", 0))
                average_rounds = coverage.get("regular_average_round_labels", [])
                heatmap_rounds = coverage.get("regular_heatmap_round_labels", [])
                render_selection_note(
                    f"Cobertura del tramo regular | Posicion promedio: {average_match_count} partidos ({_format_rounds_label(average_rounds)}) | "
                    f"Heatmap: {heatmap_match_count} partidos ({_format_rounds_label(heatmap_rounds)})"
                )

            selected_match = visual_matches[visual_matches["match_id"] == selected_match_id].head(1)
            selected_match_row = selected_match.iloc[0] if not selected_match.empty else None
            if selected_scope == PLAYER_CONTEXTUAL_SCOPE and selected_match_row is not None:
                capabilities = []
                if bool(selected_match_row.get("has_average_position")):
                    capabilities.append("posicion promedio")
                if bool(selected_match_row.get("has_heatmap")):
                    capabilities.append("heatmap")
                render_selection_note(
                    f"Activo: {safe_text(selected_match_row.get('partido'), f'Partido {selected_match_id}')}. "
                    f"Capas disponibles en este partido: {', '.join(capabilities) if capabilities else 'ninguna'}."
                )

            if selected_scope == PLAYER_CONTEXTUAL_SCOPE and selected_mode == PLAYER_AVERAGE_POSITION_MODE:
                if profile.contextual_average_position_row is None:
                    render_empty_state(
                        "No hay posicion promedio disponible para este jugador en el partido contextual seleccionado. "
                        f"Disponible: {_describe_available_views(profile, selected_match_row)}."
                    )
                else:
                    st.pyplot(
                        build_player_average_position_figure(
                            profile.contextual_average_position_row,
                            team_color=profile.team_color,
                            title_suffix="posicion promedio contextual",
                            footer_note=(
                                f"Puntos registrados: {safe_text(profile.contextual_average_position_row.get('points_count'), '0')} | "
                                f"{safe_text(selected_match_row.get('partido') if selected_match_row is not None else None, 'Partido contextual')}"
                            ),
                        ),
                        use_container_width=True,
                    )
            elif selected_scope == PLAYER_CONTEXTUAL_SCOPE and selected_mode == PLAYER_HEATMAP_MODE:
                if profile.contextual_heatmap_points.empty:
                    render_empty_state(
                        "No hay heatmap disponible para este jugador en el partido contextual seleccionado. "
                        f"Disponible: {_describe_available_views(profile, selected_match_row)}."
                    )
                else:
                    st.pyplot(
                        build_player_heatmap_figure(
                            profile.contextual_heatmap_points,
                            average_position_row=profile.contextual_average_position_row,
                            title_suffix="heatmap contextual",
                            footer_note=(
                                f"Puntos de calor: {len(profile.contextual_heatmap_points)} | "
                                f"{safe_text(selected_match_row.get('partido') if selected_match_row is not None else None, 'Partido contextual')}"
                            ),
                            team_color=profile.team_color,
                        ),
                        use_container_width=True,
                    )
            elif selected_scope == PLAYER_ACCUMULATED_SCOPE and selected_mode == PLAYER_AVERAGE_POSITION_MODE:
                if profile.accumulated_average_position_row is None:
                    render_empty_state(
                        "No hay posicion promedio acumulada disponible para este jugador dentro del tramo regular activo. "
                        f"Disponible: {_describe_available_views(profile, selected_match_row)}."
                    )
                else:
                    st.pyplot(
                        build_player_average_position_figure(
                            profile.accumulated_average_position_row,
                            team_color=profile.team_color,
                            title_suffix="posicion promedio acumulada",
                            footer_note=(
                                f"Partidos: {safe_text(profile.accumulated_average_position_row.get('matches_count'), '0')} | "
                                f"Puntos registrados: {safe_text(profile.accumulated_average_position_row.get('points_count_total', profile.accumulated_average_position_row.get('points_count')), '0')}"
                            ),
                        ),
                        use_container_width=True,
                    )
            else:
                if profile.accumulated_heatmap_points.empty:
                    render_empty_state(
                        "No hay heatmap acumulado disponible para este jugador dentro del tramo regular activo. "
                        f"Disponible: {_describe_available_views(profile, selected_match_row)}."
                    )
                else:
                    st.pyplot(
                        build_player_heatmap_figure(
                            profile.accumulated_heatmap_points,
                            average_position_row=profile.accumulated_average_position_row,
                            title_suffix="heatmap acumulado del jugador",
                            footer_note=(
                                f"Puntos de calor: {len(profile.accumulated_heatmap_points)} | "
                                f"Partidos: {heatmap_match_count} | {_format_rounds_label(heatmap_rounds)}"
                            ),
                            team_color=profile.team_color,
                        ),
                        use_container_width=True,
                    )
        render_panel_close()

    left, right = st.columns([1.02, 1.18], gap="medium")
    with left:
        render_section_title("Percentiles por posicion", "Ubica al jugador frente a pares de su posicion.")
        if profile.percentiles.empty:
            render_empty_state("No hay percentiles suficientes para este jugador.")
        else:
            st.plotly_chart(build_percentile_figure(profile.percentiles), use_container_width=True)
            st.dataframe(
                profile.percentiles,
                use_container_width=True,
                hide_index=True,
                column_config={"Metric": "Metrica", "value": "Valor", "percentile": "Percentil"},
            )

    with right:
        render_section_title("Ultimos partidos", "Selecciona una fila para abrir el partido.")
        if profile.recent_matches.empty:
            render_empty_state("No hay apariciones recientes para este jugador.")
        else:
            render_selection_note("Cada fila abre el match y conserva el origen del perfil.")
            recent_event = st.dataframe(
                profile.recent_matches[["round_label", "partido", "minutesplayed", "goals", "assists", "goal_actions_per90"]],
                use_container_width=True,
                hide_index=True,
                key=f"player_recent_{profile.player_id}",
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "round_label": "Tramo",
                    "partido": "Partido",
                    "minutesplayed": "Min",
                    "goals": "G",
                    "assists": "A",
                    "goal_actions_per90": "G+A/90",
                },
            )
            row_index = get_selected_row_index(recent_event)
            if action is None and row_index is not None:
                selected = profile.recent_matches.iloc[row_index]
                match_id = safe_optional_int(selected.get("match_id"))
                action = (
                    build_action(
                        "match",
                        match_id=match_id,
                        team_id=team_id,
                        venue="Todos",
                        result="Todos",
                        origin_label=safe_text(profile.player_row.get("name"), "Jugador"),
                    )
                    if match_id is not None
                    else None
                )

    return action
