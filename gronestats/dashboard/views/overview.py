from __future__ import annotations

import streamlit as st

from gronestats.dashboard.models import LeagueOverview
from gronestats.dashboard.state import build_action
from gronestats.dashboard.views.shared import (
    build_bar_figure,
    build_line_figure,
    get_selected_row_index,
    render_empty_state,
    render_form_chips,
    render_navigation_surface,
    render_metric_cards,
    render_section_title,
    render_selection_note,
    safe_float,
    safe_int,
    safe_optional_int,
    safe_text,
)


def render_overview(overview: LeagueOverview) -> dict[str, object] | None:
    action: dict[str, object] | None = None

    cards = [
        {"label": "Partidos", "value": f"{overview.total_matches}", "help": "Fixtures con marcador procesado en el rango actual."},
        {"label": "Equipos", "value": f"{overview.total_teams}", "help": "Clubes con presencia en la muestra activa."},
        {"label": "Jugadores", "value": f"{overview.total_players}", "help": "Futbolistas con minutos registrados."},
        {"label": "Goles", "value": f"{overview.total_goals}", "help": "Suma de goles locales y visitantes."},
        {"label": "Promedio", "value": f"{overview.goals_per_match:.2f}", "help": "Goles por partido dentro del rango seleccionado."},
    ]
    render_metric_cards(cards)

    render_section_title("Acciones rapidas", "Abre los puntos mas relevantes del analisis sin salir del overview.")
    quick_cols = st.columns(3)
    leader_team = overview.standings.iloc[0] if not overview.standings.empty else None
    top_scorers = overview.leaders.get("Goles") if overview.leaders else None
    top_match = overview.top_matches.iloc[0] if not overview.top_matches.empty else None

    with quick_cols[0]:
        if leader_team is not None:
            leader_team_id = safe_optional_int(leader_team.get("team_id"))
            if action is None and render_navigation_surface(
                title=safe_text(leader_team.get("team_name"), "Equipo sin nombre"),
                note="Mejor rendimiento acumulado en el rango actual.",
                key="overview_go_leader_team",
                button_label="Abrir equipo lider",
                eyebrow="Equipo lider",
                metadata=[f"{safe_int(leader_team.get('Pts'))} pts", f"PPG {safe_float(leader_team.get('PPG')):.2f}"],
                variant="primary",
            ) and leader_team_id is not None:
                action = build_action("team", team_id=leader_team_id)
        else:
            render_empty_state("Sin equipo lider disponible.")
    with quick_cols[1]:
        if top_scorers is not None and not top_scorers.empty:
            scorer_row = top_scorers.iloc[0]
            scorer_player_id = safe_optional_int(scorer_row.get("player_id"))
            scorer_team_id = safe_optional_int(scorer_row.get("team_id"))
            if action is None and render_navigation_surface(
                title=safe_text(scorer_row.get("Jugador"), "Jugador sin identificar"),
                note="Maximo anotador del rango filtrado.",
                key="overview_go_top_scorer",
                button_label="Abrir goleador",
                eyebrow="Goles",
                metadata=[safe_text(scorer_row.get("Equipo"), "Sin equipo"), f"{safe_int(scorer_row.get('Valor'))} goles"],
                variant="secondary",
            ) and scorer_player_id is not None:
                action = build_action("player", player_id=scorer_player_id, team_id=scorer_team_id)
        else:
            render_empty_state(
                "Sin `player_match` publicado en el rango activo."
                if overview.total_players == 0
                else "Sin lider de goles disponible."
            )
    with quick_cols[2]:
        if top_match is not None:
            top_match_id = safe_optional_int(top_match.get("match_id"))
            if action is None and render_navigation_surface(
                title=safe_text(top_match.get("partido"), "Partido destacado"),
                note="Encuentro con mayor volumen goleador en la muestra activa.",
                key="overview_go_top_match",
                button_label="Abrir partido",
                eyebrow=safe_text(top_match.get("round_label"), f"R{safe_int(top_match.get('round_number'))}"),
                metadata=[f"{safe_int(top_match.get('total_goals'))} goles", safe_text(top_match.get("estadio"), "Estadio sin dato")],
                variant="secondary",
            ) and top_match_id is not None:
                action = build_action("match", match_id=top_match_id, origin_label="Overview")
        else:
            render_empty_state("Sin partidos destacados disponibles.")

    left, right = st.columns([1.75, 1.05], gap="large")

    with left:
        render_section_title("Tabla de posiciones", "Selecciona una fila para abrir el analisis del club.")
        if overview.standings.empty:
            render_empty_state("No hay partidos con resultado para construir la tabla.")
        else:
            render_selection_note("Tabla navegable: haz click en una fila para abrir el club y mantener el rango activo.")
            standings_event = st.dataframe(
                overview.standings[["Pos", "team_name", "PJ", "Pts", "G", "E", "P", "GF", "GC", "DG", "PPG"]],
                width="stretch",
                hide_index=True,
                column_config={"team_name": "Equipo"},
                key="overview_standings",
                on_select="rerun",
                selection_mode="single-row",
            )
            row_index = get_selected_row_index(standings_event)
            if action is None and row_index is not None:
                selected_team_id = safe_optional_int(overview.standings.iloc[row_index].get("team_id"))
                if selected_team_id is not None:
                    action = build_action("team", team_id=selected_team_id)

    with right:
        render_section_title("Lideres", "Selecciona una fila para abrir el perfil del jugador.")
        if not overview.leaders:
            render_empty_state(
                "No hay `player_match` publicado para construir liderazgos."
                if overview.total_players == 0
                else "No hay datos suficientes para construir liderazgos."
            )
        else:
            render_selection_note("Cada tabla de lideres es navegable: la fila seleccionada abre el perfil del jugador.")
            tabs = st.tabs(list(overview.leaders.keys()))
            for tab, (label, frame) in zip(tabs, overview.leaders.items()):
                with tab:
                    leader_event = st.dataframe(
                        frame[["Jugador", "Equipo", "Valor"]],
                        width="stretch",
                        hide_index=True,
                        key=f"overview_leader_{label}",
                        on_select="rerun",
                        selection_mode="single-row",
                    )
                    row_index = get_selected_row_index(leader_event)
                    if action is None and row_index is not None:
                        selected = frame.iloc[row_index]
                        player_id = safe_optional_int(selected.get("player_id"))
                        team_id = safe_optional_int(selected.get("team_id"))
                        if player_id is not None:
                            action = build_action("player", player_id=player_id, team_id=team_id)

    bottom_left, bottom_right = st.columns([1.2, 1], gap="large")

    with bottom_left:
        render_section_title("Goles por ronda", "Detecta tramos de mayor produccion ofensiva.")
        if overview.goals_by_round.empty:
            render_empty_state("Sin goles por ronda en el filtro actual.")
        else:
            st.plotly_chart(build_line_figure(overview.goals_by_round, "round_label", "goals"), width="stretch")

    with bottom_right:
        render_section_title("Goles local vs visita", "Balance de produccion segun condicion.")
        if overview.venue_goals.empty:
            render_empty_state("No hay goles disponibles.")
        else:
            st.plotly_chart(build_bar_figure(overview.venue_goals, "context", "goals", "#7ec4b8"), width="stretch")

    match_col, form_col = st.columns([1.1, 1], gap="large")
    with match_col:
        render_section_title("Partidos destacados", "Selecciona un partido para saltar al detalle.")
        if overview.top_matches.empty:
            render_empty_state("No hay partidos destacados para mostrar.")
        else:
            render_selection_note("Haz click en una fila para abrir el detalle del partido sin perder el contexto del overview.")
            matches_event = st.dataframe(
                overview.top_matches[["round_label", "partido", "total_goals", "estadio", "ciudad"]],
                width="stretch",
                hide_index=True,
                key="overview_top_matches",
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "round_label": "Tramo",
                    "partido": "Partido",
                    "total_goals": "Goles",
                    "estadio": "Estadio",
                    "ciudad": "Ciudad",
                },
            )
            row_index = get_selected_row_index(matches_event)
            if action is None and row_index is not None:
                match_id = safe_optional_int(overview.top_matches.iloc[row_index].get("match_id"))
                if match_id is not None:
                    action = build_action("match", match_id=match_id, origin_label="Overview")

    with form_col:
        render_section_title("Forma reciente de equipos top", "Abre un club para bajar al siguiente nivel de analisis.")
        if overview.form_table.empty:
            render_empty_state("No se pudo construir la forma reciente.")
        else:
            for _, row in overview.form_table.iterrows():
                st.markdown(render_form_chips(row["Form"]), unsafe_allow_html=True)
                team_id = safe_optional_int(row.get("team_id"))
                if action is None and render_navigation_surface(
                    title=safe_text(row.get("team_name"), "Equipo sin nombre"),
                    note=f"{safe_int(row.get('Pts'))} pts en la racha visible con GF {safe_int(row.get('GF'))} y GC {safe_int(row.get('GC'))}.",
                    key=f"overview_form_team_{row['team_id']}",
                    button_label="Abrir este equipo",
                    eyebrow="Forma reciente",
                    metadata=[f"PPG {safe_float(row.get('PPG')):.2f}" if "PPG" in row else "Forma reciente", "Navegacion contextual"],
                    variant="secondary",
                ) and team_id is not None:
                    action = build_action("team", team_id=team_id)

    return action
