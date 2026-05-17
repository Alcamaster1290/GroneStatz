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
    render_section_title,
    render_selection_note,
    safe_float,
    safe_int,
    safe_optional_int,
    safe_text,
)


def _render_standings_table(frame, *, key: str, label: str) -> dict[str, object] | None:
    st.markdown(f"**{label}**")
    standings_event = st.dataframe(
        frame[["Pos", "team_name", "PJ", "Pts", "G", "E", "P", "GF", "GC", "DG", "PPG"]],
        use_container_width=True,
        hide_index=True,
        column_config={"team_name": "Equipo"},
        key=key,
        on_select="rerun",
        selection_mode="single-row",
    )
    row_index = get_selected_row_index(standings_event)
    if row_index is None:
        return None
    selected_team_id = safe_optional_int(frame.iloc[row_index].get("team_id"))
    if selected_team_id is None:
        return None
    return build_action("team", team_id=selected_team_id)


def _render_match_results_table(frame, *, key: str) -> dict[str, object] | None:
    results_event = st.dataframe(
        frame[["round_label", "partido", "scoreline", "estadio", "ciudad"]],
        use_container_width=True,
        hide_index=True,
        key=key,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "round_label": "Tramo",
            "partido": "Partido",
            "scoreline": "Marcador",
            "estadio": "Estadio",
            "ciudad": "Ciudad",
        },
    )
    row_index = get_selected_row_index(results_event)
    if row_index is None:
        return None
    match_id = safe_optional_int(frame.iloc[row_index].get("match_id"))
    if match_id is None:
        return None
    return build_action("match", match_id=match_id, origin_label="Overview")


def render_overview(overview: LeagueOverview) -> dict[str, object] | None:
    action: dict[str, object] | None = None

    render_section_title("Acciones rapidas", "Abre los puntos mas relevantes del analisis sin salir del overview.")
    quick_cols = st.columns(3)
    leader_team = overview.standings.iloc[0] if not overview.standings.empty else None
    top_scorers = overview.leaders.get("Goles") if overview.leaders else None
    spotlight_matches = overview.grand_final_results if not overview.grand_final_results.empty else overview.top_matches
    top_match = spotlight_matches.iloc[0] if not spotlight_matches.empty else None

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
        elif overview.grand_final_only:
            render_empty_state("Grand Final no usa tabla acumulada.")
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

    if overview.grand_final_only:
        left, right = st.columns([1.35, 1], gap="large")
        with left:
            render_section_title("Resultados Grand Final", "Cada fila abre el analisis del partido.")
            if overview.grand_final_results.empty:
                render_empty_state("No hay resultados publicados para Grand Final.")
            else:
                render_selection_note("La tabla es navegable y conserva el contexto del overview.")
                if action is None:
                    action = _render_match_results_table(overview.grand_final_results, key="overview_grand_final_results")
                else:
                    _render_match_results_table(overview.grand_final_results, key="overview_grand_final_results")
        with right:
            render_section_title("Tabla de goleadores", "Selecciona una fila para abrir el perfil del jugador.")
            if top_scorers is None or top_scorers.empty:
                render_empty_state("No hay `player_match` publicado para construir la tabla de goleadores.")
            else:
                render_selection_note("La tabla de goleadores es navegable.")
                scorer_event = st.dataframe(
                    top_scorers[["Jugador", "Equipo", "Valor"]],
                    use_container_width=True,
                    hide_index=True,
                    key="overview_grand_final_scorers",
                    on_select="rerun",
                    selection_mode="single-row",
                )
                row_index = get_selected_row_index(scorer_event)
                if action is None and row_index is not None:
                    selected = top_scorers.iloc[row_index]
                    player_id = safe_optional_int(selected.get("player_id"))
                    team_id = safe_optional_int(selected.get("team_id"))
                    if player_id is not None:
                        action = build_action("player", player_id=player_id, team_id=team_id)
        return action

    render_section_title(
        "Tablas de posiciones",
        "Cuando el filtro combina Apertura y Clausura, el overview mantiene una tabla por torneo.",
    )
    if not overview.standings_tables:
        render_empty_state("No hay partidos con resultado para construir tablas de posiciones.")
    elif len(overview.standings_tables) == 1:
        render_selection_note("Tabla navegable: haz click en una fila para abrir el club y mantener el rango activo.")
        if action is None:
            action = _render_standings_table(
                overview.standings_tables[0][1],
                key="overview_standings_single",
                label=overview.standings_tables[0][0],
            )
        else:
            _render_standings_table(
                overview.standings_tables[0][1],
                key="overview_standings_single",
                label=overview.standings_tables[0][0],
            )
    else:
        render_selection_note("Cada tabla es navegable y conserva el rango activo del overview.")
        standings_cols = st.columns(len(overview.standings_tables), gap="large")
        for index, ((label, frame), column) in enumerate(zip(overview.standings_tables, standings_cols)):
            with column:
                next_action = _render_standings_table(frame, key=f"overview_standings_{index}", label=label)
                if action is None and next_action is not None:
                    action = next_action

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
                    use_container_width=True,
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

    if not overview.grand_final_results.empty:
        render_section_title("Resultados Grand Final", "Si el filtro incluye Grand Final, cada fila abre el partido correspondiente.")
        render_selection_note("Esta tabla aparece solo cuando el tramo activo incluye partidos de Grand Final.")
        next_action = _render_match_results_table(overview.grand_final_results, key="overview_grand_final_results_mixed")
        if action is None and next_action is not None:
            action = next_action

    bottom_left, bottom_right = st.columns([1.2, 1], gap="large")

    with bottom_left:
        render_section_title("Goles por ronda", "Detecta tramos de mayor produccion ofensiva.")
        if overview.goals_by_round.empty:
            render_empty_state("Sin goles por ronda en el filtro actual.")
        else:
            st.plotly_chart(
                build_line_figure(overview.goals_by_round, "round_label", "goals"),
                use_container_width=True,
            )

    with bottom_right:
        render_section_title("Goles local vs visita", "Balance de produccion segun condicion.")
        if overview.venue_goals.empty:
            render_empty_state("No hay goles disponibles.")
        else:
            st.plotly_chart(
                build_bar_figure(overview.venue_goals, "context", "goals", "#7ec4b8"),
                use_container_width=True,
            )

    match_col, form_col = st.columns([1.1, 1], gap="large")
    with match_col:
        render_section_title("Partidos destacados", "Selecciona un partido para saltar al detalle.")
        if overview.top_matches.empty:
            render_empty_state("No hay partidos destacados para mostrar.")
        else:
            render_selection_note("Haz click en una fila para abrir el detalle del partido sin perder el contexto del overview.")
            matches_event = st.dataframe(
                overview.top_matches[["round_label", "partido", "total_goals", "estadio", "ciudad"]],
                use_container_width=True,
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
