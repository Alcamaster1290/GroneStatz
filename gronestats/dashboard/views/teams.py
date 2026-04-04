from __future__ import annotations

import streamlit as st

from gronestats.dashboard.data import find_team_image
from gronestats.dashboard.models import TeamProfile
from gronestats.dashboard.state import build_action
from gronestats.dashboard.views.shared import (
    build_bar_figure,
    build_grouped_bar,
    get_selected_row_index,
    render_empty_state,
    render_form_chips,
    render_identity_panel,
    render_metric_cards,
    render_navigation_surface,
    render_section_title,
    render_selection_note,
    safe_optional_int,
    safe_text,
)


def render_team_view(profile: TeamProfile | None, *, player_layer_available: bool = True) -> dict[str, object] | None:
    if profile is None:
        render_empty_state("Selecciona un club con partidos dentro del rango filtrado.")
        return None

    action: dict[str, object] | None = None
    metadata = []
    if "department" in profile.team_row:
        metadata.append(f"Departamento: {safe_text(profile.team_row.get('department'), '-')}")
    if "province" in profile.team_row:
        metadata.append(f"Provincia: {safe_text(profile.team_row.get('province'), '-')}")
    if "stadium_name_city" in profile.team_row:
        metadata.append(f"Estadio: {safe_text(profile.team_row.get('stadium_name_city'), '-')}")
    altitude_value = safe_optional_int(profile.team_row.get("is_altitude_team")) if "is_altitude_team" in profile.team_row else None
    if altitude_value == 1:
        metadata.append("Contexto de altura")

    render_identity_panel(
        title=profile.team_name,
        subtitle="Lectura rapida del rendimiento, splits y protagonismo individual del club.",
        image_path=find_team_image(profile.team_id),
        metadata=metadata,
        accent_color=profile.team_color,
        accent_label="Color primario del equipo",
    )

    action_cols = st.columns(2)
    with action_cols[0]:
        if action is None and render_navigation_surface(
            title="Plantilla y perfiles",
            note=(
                "Filtra la exploracion de jugadores al club actual para bajar a rendimiento individual."
                if player_layer_available
                else "La capa de jugadores aun no esta publicada para esta temporada."
            ),
            key=f"team_go_players_{profile.team_id}",
            button_label="Ver plantilla del equipo" if player_layer_available else "Jugadores pendientes",
            eyebrow="Siguiente capa",
            metadata=[profile.team_name, "Jugadores" if player_layer_available else "Sin player_match"],
            variant="primary",
            accent_color=profile.team_color,
            disabled=not player_layer_available,
            help=None if player_layer_available else "Se habilita cuando exista `player_match` publicado para esta temporada.",
        ):
            action = build_action("players_filter", team_id=int(profile.team_id), position="Todas")
    with action_cols[1]:
        if action is None and render_navigation_surface(
            title="Partidos del equipo",
            note="Abre el catalogo de encuentros del club sin resetear el rango global ni el contexto.",
            key=f"team_go_matches_{profile.team_id}",
            button_label="Ver partidos del equipo",
            eyebrow="Exploracion",
            metadata=[profile.team_name, "Partidos"],
            variant="secondary",
            accent_color=profile.team_color,
        ):
            action = build_action("matches_filter", team_id=int(profile.team_id), venue="Todos", result="Todos")

    cards = [
        {"label": "Puntos", "value": str(profile.summary["Pts"]), "help": f"PPG {profile.summary['PPG']}"},
        {"label": "PJ", "value": str(profile.summary["PJ"]), "help": f"G {profile.summary['G']} | E {profile.summary['E']} | P {profile.summary['P']}"},
        {"label": "GF", "value": str(profile.summary["GF"]), "help": "Goles a favor en el rango actual."},
        {"label": "GC", "value": str(profile.summary["GC"]), "help": "Goles en contra en el rango actual."},
        {"label": "DG", "value": str(profile.summary["DG"]), "help": "Diferencia de gol acumulada."},
    ]
    render_metric_cards(cards)

    left, right = st.columns([1.1, 1.25], gap="large")
    with left:
        render_section_title("Forma reciente", "Selecciona una fila para abrir el partido.")
        if profile.recent_matches.empty:
            render_empty_state("No hay partidos recientes para mostrar.")
        else:
            st.markdown(render_form_chips(profile.recent_matches["result"].tolist()), unsafe_allow_html=True)
            render_selection_note("Tabla navegable: una fila abre el partido y conserva el foco en este equipo.")
            recent_event = st.dataframe(
                profile.recent_matches[["round_label", "opponent_name", "venue", "marcador", "resultado"]],
                width="stretch",
                hide_index=True,
                key=f"team_recent_{profile.team_id}",
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "round_label": "Tramo",
                    "opponent_name": "Rival",
                    "venue": "Condicion",
                    "marcador": "Marcador",
                    "resultado": "Resultado",
                },
            )
            row_index = get_selected_row_index(recent_event)
            if action is None and row_index is not None:
                match_id = safe_optional_int(profile.recent_matches.iloc[row_index].get("match_id"))
                if match_id is not None:
                    action = build_action(
                        "match",
                        match_id=match_id,
                        team_id=int(profile.team_id),
                        venue="Todos",
                        result="Todos",
                        origin_label=profile.team_name,
                    )

    with right:
        render_section_title("Split local / visita", "Como cambia el rendimiento segun condicion.")
        if profile.splits.empty:
            render_empty_state("Sin datos para comparar local y visita.")
        else:
            st.plotly_chart(build_bar_figure(profile.splits, "venue", "points", profile.team_color), width="stretch")
            st.dataframe(profile.splits, width="stretch", hide_index=True, column_config={"venue": "Condicion"})

    bottom_left, bottom_right = st.columns([1.15, 1.2], gap="large")
    with bottom_left:
        render_section_title("Top contribuyentes", "Selecciona un jugador para abrir su perfil.")
        if profile.top_players.empty:
            render_empty_state(
                "Todavia no hay `player_match` publicado para este equipo."
                if not player_layer_available
                else "No hay jugadores con minutos registrados para este equipo."
            )
        else:
            render_selection_note("Selecciona una fila para saltar al perfil del jugador dentro del contexto del equipo.")
            players_event = st.dataframe(
                profile.top_players[["name", "position", "minutesplayed", "goals", "assists", "goal_actions_per90"]],
                width="stretch",
                hide_index=True,
                key=f"team_top_players_{profile.team_id}",
                on_select="rerun",
                selection_mode="single-row",
                column_config={
                    "name": "Jugador",
                    "position": "Pos",
                    "minutesplayed": "Min",
                    "goals": "G",
                    "assists": "A",
                    "goal_actions_per90": "G+A/90",
                },
            )
            row_index = get_selected_row_index(players_event)
            if action is None and row_index is not None:
                selected = profile.top_players.iloc[row_index]
                player_id = safe_optional_int(selected.get("player_id"))
                if player_id is not None:
                    action = build_action("player", player_id=player_id, team_id=int(profile.team_id))

    with bottom_right:
        render_section_title("Comparacion vs promedio liga", "Lectura rapida para detectar ventaja o desventaja estructural.")
        if profile.comparison.empty:
            render_empty_state("No hay comparacion disponible.")
        else:
            st.plotly_chart(
                build_grouped_bar(
                    profile.comparison,
                    "Metric",
                    "Equipo",
                    "Liga",
                    left_color=profile.team_color,
                ),
                width="stretch",
            )
            st.dataframe(profile.comparison, width="stretch", hide_index=True)

    return action
