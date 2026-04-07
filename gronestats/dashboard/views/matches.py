from __future__ import annotations

import streamlit as st

from gronestats.dashboard.data import find_player_image
from gronestats.dashboard.models import MatchSummary
from gronestats.dashboard.state import build_action
from gronestats.dashboard.views.pitch import (
    build_goalkeeper_saves_figure,
    build_match_average_positions_figure,
    build_match_momentum_figure,
    build_match_shotmap_figure,
)
from gronestats.dashboard.views.shared import (
    build_team_palette,
    get_selected_row_index,
    render_action_button,
    render_empty_state,
    render_form_chips,
    render_metric_cards,
    render_navigation_surface,
    render_player_spotlight_card,
    render_selection_note,
    render_section_title,
    safe_float,
    safe_int,
    safe_optional_int,
    safe_text,
)


def render_match_catalog(frame, selected_match_id: int | None = None) -> int | None:
    if frame.empty:
        render_empty_state("No hay partidos que coincidan con los filtros activos.")
        return None
    total = len(frame)
    st.markdown(
        f"""
        <div class="gs-catalog-shell">
          <div class="gs-catalog-header">
            <span class="gs-toolbar__kicker">Catalogo filtrado</span>
            <span class="gs-catalog-header__count">{total} partidos</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected = safe_optional_int(selected_match_id) if selected_match_id in frame["match_id"].tolist() else None
    with st.container(height=400):
        for _, row in frame.iterrows():
            match_id = safe_optional_int(row.get("match_id"))
            if match_id is None:
                continue
            is_active = selected == match_id
            title = f"{safe_text(row.get('home'), 'Local')} vs {safe_text(row.get('away'), 'Visita')}"
            note = f"{safe_text(row.get('scoreline'), '-')} • {safe_text(row.get('fecha'), 'Fecha sin dato')}"
            metadata = [safe_text(row.get("estadio"), "Estadio sin dato"), safe_text(row.get("ciudad"), "Ciudad sin dato")]
            metadata.append("Activo" if is_active else f"Arbitro {safe_text(row.get('arbitro'), 'Sin arbitro')}")
            clicked = render_navigation_surface(
                title=title,
                note=note,
                key=f"match_catalog_item_{match_id}",
                button_label="Activo" if is_active else "Ver",
                eyebrow=safe_text(row.get("round_label"), f"R{safe_int(row.get('round_number'))}"),
                metadata=metadata,
                variant="active" if is_active else "secondary",
                active=is_active,
                compact=True,
                disabled=is_active,
            )
            if clicked:
                return match_id
    return None


def _render_origin_toolbar(summary: MatchSummary) -> dict[str, object] | None:
    action: dict[str, object] | None = None
    origin = summary.origin_context or {}
    neighbors = summary.catalog_neighbors or {}
    chips = []
    round_chip = safe_text(summary.match_row.get("round_label"), f"R{safe_int(summary.match_row.get('round_number'))}")
    if origin.get("has_origin"):
        chips.append(f"<span class='gs-chip'>Desde {safe_text(origin.get('label'), 'Dashboard')}</span>")
    chips.append(f"<span class='gs-chip'>Partido {safe_int(neighbors.get('current_index', 0)) + 1} de {safe_int(neighbors.get('total', 0))}</span>")
    chips.append(f"<span class='gs-chip'>{round_chip}</span>")
    chips.append(f"<span class='gs-chip'>{safe_text(summary.match_row.get('tournament_label'), 'Sin torneo')}</span>")
    toolbar_html = f"""
    <section class="gs-toolbar">
      <span class="gs-toolbar__kicker">Ruta analitica</span>
      <p class="gs-toolbar__title">{safe_text(neighbors.get('current_label'), 'Partido focal')}</p>
      <p class="gs-toolbar__note">Sigue el catalogo activo, vuelve al origen o salta al siguiente partido.</p>
      <div class="gs-chip-row">{''.join(chips)}</div>
    </section>
    """
    st.markdown(toolbar_html, unsafe_allow_html=True)

    toolbar_cols = st.columns([1.05, 0.8, 0.8], gap="small")
    with toolbar_cols[0]:
        if action is None and origin.get("has_origin") and render_action_button(
            "Volver",
            key=f"match_back_origin_{summary.match_id}",
            variant="primary",
            width="stretch",
        ):
            action = build_action("return_origin")
    with toolbar_cols[1]:
        if action is None and render_action_button(
            "Anterior",
            key=f"match_prev_{summary.match_id}",
            variant="secondary",
            width="stretch",
            help=neighbors.get("previous_label"),
            disabled=neighbors.get("previous_match_id") is None,
        ):
            previous_match_id = safe_optional_int(neighbors.get("previous_match_id"))
            if previous_match_id is not None:
                action = build_action("match", match_id=previous_match_id, update_origin=False)
    with toolbar_cols[2]:
        if action is None and render_action_button(
            "Siguiente",
            key=f"match_next_{summary.match_id}",
            variant="secondary",
            width="stretch",
            help=neighbors.get("next_label"),
            disabled=neighbors.get("next_match_id") is None,
        ):
            next_match_id = safe_optional_int(neighbors.get("next_match_id"))
            if next_match_id is not None:
                action = build_action("match", match_id=next_match_id, update_origin=False)

    return action


def _render_match_header(summary: MatchSummary) -> dict[str, object] | None:
    row = summary.match_row
    action: dict[str, object] | None = None
    home_palette = build_team_palette(summary.home_team_color)
    away_palette = build_team_palette(summary.away_team_color)
    header_html = f"""
    <section class="gs-match-hero" style="
      background:
        radial-gradient(circle at left top, {home_palette['soft_bg_strong']}, transparent 34%),
        radial-gradient(circle at right top, {away_palette['soft_bg_strong']}, transparent 34%),
        linear-gradient(135deg, rgba(255,255,255,0.03), rgba(255,255,255,0.012)),
        rgba(15, 24, 36, 0.92);
      border-color: color-mix(in srgb, {home_palette['primary']} 42%, {away_palette['primary']});
    ">
      <div class="gs-match-hero__grid">
        <div class="gs-match-hero__team">
          <span class="gs-match-hero__eyebrow" style="color:{home_palette['primary']};">Local</span>
          <h2 class="gs-match-hero__name" style="color:{home_palette['primary']};">{safe_text(row.get('home'), 'Local')}</h2>
          <span class="gs-match-hero__context">{safe_text(row.get('round_label'), f"R{safe_int(row.get('round_number'))}")}</span>
        </div>
        <div class="gs-match-hero__score">
          <span class="gs-match-hero__caption">{safe_text(row.get('tournament_label'), 'Resultado final')}</span>
          <div class="gs-match-hero__scoreline">{safe_text(row.get('scoreline'), '-')}</div>
        </div>
        <div class="gs-match-hero__team gs-match-hero__team--away">
          <span class="gs-match-hero__eyebrow" style="color:{away_palette['primary']};">Visita</span>
          <h2 class="gs-match-hero__name" style="color:{away_palette['primary']};">{safe_text(row.get('away'), 'Visita')}</h2>
          <span class="gs-match-hero__context">{safe_text(row.get('fecha'), 'Fecha sin dato')}</span>
        </div>
      </div>
      <div class="gs-match-hero__meta">
        <span style="border-color:{home_palette['chip_border']}; background:{home_palette['chip_bg']};">Estadio: {safe_text(row.get('estadio'), 'Sin dato')}</span>
        <span style="border-color:{away_palette['chip_border']}; background:{away_palette['chip_bg']};">Ciudad: {safe_text(row.get('ciudad'), 'Sin dato')}</span>
        <span>Arbitro: {safe_text(row.get('arbitro'), 'Sin dato')}</span>
      </div>
    </section>
    """
    st.markdown(header_html, unsafe_allow_html=True)

    home_team_id = safe_optional_int(row.get("home_id"))
    away_team_id = safe_optional_int(row.get("away_id"))
    action_cols = st.columns(2, gap="small")
    with action_cols[0]:
        if action is None and home_team_id is not None and render_action_button(
            f"Abrir local",
            key=f"match_home_{summary.match_id}",
            variant="primary",
            width="stretch",
        ):
            action = build_action("team", team_id=home_team_id)
    with action_cols[1]:
        if action is None and away_team_id is not None and render_action_button(
            f"Abrir visita",
            key=f"match_away_{summary.match_id}",
            variant="secondary",
            width="stretch",
        ):
            action = build_action("team", team_id=away_team_id)
    return action


def _pick_side_star(summary: MatchSummary, side: str):
    if summary.standout_players.empty:
        return None
    subset = summary.standout_players[summary.standout_players["side"] == side]
    if subset.empty:
        return None
    return subset.iloc[0]


def _render_context_table(frame, key_prefix: str) -> int | None:
    if frame.empty:
        render_empty_state("No hay partidos cercanos en el rango activo.")
        return None
    event = st.dataframe(
        frame[["Relacion", "round_label", "Partido", "venue", "Resultado"]],
        use_container_width=True,
        hide_index=True,
        key=key_prefix,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Relacion": "Relacion",
            "round_label": "Tramo",
            "Partido": "Partido",
            "venue": "Condicion",
            "Resultado": "Resultado",
        },
    )
    row_index = get_selected_row_index(event)
    if row_index is None:
        return None
    return safe_optional_int(frame.iloc[row_index].get("match_id"))


def render_match_detail(summary: MatchSummary | None) -> dict[str, object] | None:
    if summary is None:
        render_empty_state("Selecciona un partido para inspeccionar detalle.")
        return None

    action: dict[str, object] | None = None
    row = summary.match_row
    home_star = _pick_side_star(summary, "Local")
    away_star = _pick_side_star(summary, "Visita")

    action = _render_origin_toolbar(summary)
    header_action = _render_match_header(summary)
    if action is None:
        action = header_action

    render_section_title(
        "Insight strip",
        "Lectura rapida de control, amenaza y protagonistas del partido.",
    )
    render_metric_cards(summary.insight_cards)

    tabs = st.tabs(["Lectura rapida", "Estadisticas", "Eventos Opta", "Jugadores", "Contexto"])

    with tabs[0]:
        left, right = st.columns([1.32, 0.9], gap="medium")
        with left:
            render_section_title(
                "Comparacion curada",
                "Variables clave para entender dominio, amenaza y ritmo.",
            )
            if summary.curated_stats.empty:
                render_empty_state("No hay comparacion confiable para este partido. Se mantiene metadata y score.")
            else:
                render_selection_note("Tabla comparativa: lectura rapida de las ventajas del partido por metrica clave.")
                st.dataframe(summary.curated_stats, use_container_width=True, hide_index=True)

        with right:
            render_section_title("Protagonistas", "Figuras mas influyentes del partido.")
            if home_star is None and away_star is None:
                render_empty_state("No hay figuras claras por falta de registros individuales.")
            else:
                if home_star is not None:
                    render_player_spotlight_card(
                        kicker="Local",
                        title=safe_text(home_star.get("name"), "Sin figura clara"),
                        stat_line=(
                            f"G {safe_int(home_star.get('goals'))} | "
                            f"A {safe_int(home_star.get('assists'))} | "
                            f"Min {safe_int(home_star.get('minutesplayed'))}"
                        ),
                        image_path=find_player_image(safe_optional_int(home_star.get("player_id"))),
                        note="Lectura rapida del jugador mas influyente del local.",
                        accent_color=summary.home_team_color,
                    )
                if away_star is not None:
                    render_player_spotlight_card(
                        kicker="Visita",
                        title=safe_text(away_star.get("name"), "Sin figura clara"),
                        stat_line=(
                            f"G {safe_int(away_star.get('goals'))} | "
                            f"A {safe_int(away_star.get('assists'))} | "
                            f"Min {safe_int(away_star.get('minutesplayed'))}"
                        ),
                        image_path=find_player_image(safe_optional_int(away_star.get("player_id"))),
                        note="Lectura rapida del jugador mas influyente de la visita.",
                        accent_color=summary.away_team_color,
                    )

        render_section_title(
            "Posiciones promedio de ambos equipos",
            "Estructura promedio del partido con la visita reflejada.",
        )
        if summary.team_average_positions.empty:
            render_empty_state("No hay posiciones promedio disponibles para este match_id.")
        else:
            metadata = summary.average_position_metadata or {}
            render_selection_note(
                f"Local: {safe_text(metadata.get('home_strategy'), 'sin datos')} ({safe_int(metadata.get('home_count'))}) | "
                f"Visita: {safe_text(metadata.get('away_strategy'), 'sin datos')} ({safe_int(metadata.get('away_count'))})"
            )
            st.pyplot(
                build_match_average_positions_figure(
                    summary.team_average_positions,
                    home_team=safe_text(row.get("home"), "Local"),
                    away_team=safe_text(row.get("away"), "Visita"),
                    metadata=metadata,
                    home_color=summary.home_team_color,
                    away_color=summary.away_team_color,
                ),
                use_container_width=True,
            )

    with tabs[1]:
        render_section_title(
            "Metricas completas por grupo",
            "Agrupadas por bloque estadistico para una lectura mas rapida.",
        )
        if not summary.grouped_stats:
            render_empty_state("Este match_id no trae metricas ampliadas en team_stats.parquet.")
        else:
            render_selection_note("Abre solo el grupo estadistico que quieras revisar.")
            for group, frame in summary.grouped_stats.items():
                with st.expander(f"{group} ({len(frame)})", expanded=group in {"Match overview", "Shots"}):
                    st.dataframe(frame[["Metrica", "Local", "Visita"]], use_container_width=True, hide_index=True)

    with tabs[2]:
        render_section_title(
            "Shotmap comparativo",
            "Eventos de tiro Opta por tipo de finalizacion. La visita se refleja para comparar patron de ataque en el mismo arco de referencia.",
        )
        if summary.shot_events.empty:
            render_empty_state("No hay `shot_events` publicados para este match_id.")
        else:
            render_selection_note(
                safe_text(
                    summary.shot_events_metadata.get("orientation_note"),
                    "Coordenadas Opta normalizadas; visual comparativa con espejo de visita.",
                )
            )
            st.pyplot(
                build_match_shotmap_figure(
                    summary.shot_events,
                    home_team=safe_text(row.get("home"), "Local"),
                    away_team=safe_text(row.get("away"), "Visita"),
                    metadata=summary.shot_events_metadata,
                    home_color=summary.home_team_color,
                    away_color=summary.away_team_color,
                ),
                use_container_width=True,
            )

        momentum_cols = st.columns([1.15, 0.85], gap="medium")
        with momentum_cols[0]:
            render_section_title(
                "Momentum por minuto",
                "Curva de impulso del partido: valores positivos favorecen al local y negativos a la visita.",
            )
            if summary.momentum_series.empty:
                render_empty_state("No hay `match_momentum` publicado para este partido.")
            else:
                st.pyplot(
                    build_match_momentum_figure(
                        summary.momentum_series,
                        home_team=safe_text(row.get("home"), "Local"),
                        away_team=safe_text(row.get("away"), "Visita"),
                        home_color=summary.home_team_color,
                        away_color=summary.away_team_color,
                    ),
                    use_container_width=True,
                )

        with momentum_cols[1]:
            render_section_title(
                "Atajadas de arquero",
                "Lectura rapida del trabajo de los arqueros en el partido.",
            )
            if summary.goalkeeper_saves.empty:
                render_empty_state("Sin registros de atajadas de arquero en player_match para este match_id.")
            else:
                st.pyplot(
                    build_goalkeeper_saves_figure(
                        summary.goalkeeper_saves,
                        home_team=safe_text(row.get("home"), "Local"),
                        away_team=safe_text(row.get("away"), "Visita"),
                        home_color=summary.home_team_color,
                        away_color=summary.away_team_color,
                    ),
                    use_container_width=True,
                )
                st.dataframe(
                    summary.goalkeeper_saves[["side", "name", "team_name", "saves", "minutesplayed"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "side": "Lado",
                        "name": "Arquero",
                        "team_name": "Equipo",
                        "saves": "Atajadas",
                        "minutesplayed": "Min",
                    },
                )

    with tabs[3]:
        render_section_title(
            "Jugadores del partido",
            "Planillas por lado ordenadas por impacto, minutos y produccion.",
        )
        if home_star is not None or away_star is not None:
            figure_cols = st.columns(2, gap="medium")
            with figure_cols[0]:
                if home_star is not None:
                    home_star_player_id = safe_optional_int(home_star.get("player_id"))
                    home_star_team_id = safe_optional_int(home_star.get("team_id"))
                    clicked = render_player_spotlight_card(
                        kicker="Figura local",
                        title=safe_text(home_star.get("name"), "Sin figura clara"),
                        stat_line=(
                            f"G {safe_int(home_star.get('goals'))} | "
                            f"A {safe_int(home_star.get('assists'))} | "
                            f"Min {safe_int(home_star.get('minutesplayed'))}"
                        ),
                        image_path=find_player_image(home_star_player_id),
                        note=safe_text(home_star.get("position"), "Sin posicion"),
                        button_label="Abrir figura local",
                        button_key=f"match_open_home_star_{summary.match_id}",
                        button_variant="primary",
                        button_disabled=home_star_player_id is None or home_star_team_id is None,
                        accent_color=summary.home_team_color,
                    )
                    if action is None and home_star_player_id is not None and home_star_team_id is not None and clicked:
                        action = build_action(
                            "player",
                            player_id=home_star_player_id,
                            team_id=home_star_team_id,
                            position=home_star.get("position"),
                            match_id=summary.match_id,
                        )
            with figure_cols[1]:
                if away_star is not None:
                    away_star_player_id = safe_optional_int(away_star.get("player_id"))
                    away_star_team_id = safe_optional_int(away_star.get("team_id"))
                    clicked = render_player_spotlight_card(
                        kicker="Figura visita",
                        title=safe_text(away_star.get("name"), "Sin figura clara"),
                        stat_line=(
                            f"G {safe_int(away_star.get('goals'))} | "
                            f"A {safe_int(away_star.get('assists'))} | "
                            f"Min {safe_int(away_star.get('minutesplayed'))}"
                        ),
                        image_path=find_player_image(away_star_player_id),
                        note=safe_text(away_star.get("position"), "Sin posicion"),
                        button_label="Abrir figura visita",
                        button_key=f"match_open_away_star_{summary.match_id}",
                        button_variant="secondary",
                        button_disabled=away_star_player_id is None or away_star_team_id is None,
                        accent_color=summary.away_team_color,
                    )
                    if action is None and away_star_player_id is not None and away_star_team_id is not None and clicked:
                        action = build_action(
                            "player",
                            player_id=away_star_player_id,
                            team_id=away_star_team_id,
                            position=away_star.get("position"),
                            match_id=summary.match_id,
                        )

        if summary.player_rows.empty:
            render_empty_state("No hay registros individuales para este partido en player_match.parquet.")
        else:
            local_players = summary.player_rows[summary.player_rows["side"] == "Local"].copy()
            away_players = summary.player_rows[summary.player_rows["side"] == "Visita"].copy()

            side_cols = st.columns(2, gap="medium")
            with side_cols[0]:
                st.markdown(f"**{safe_text(row.get('home'), 'Local')}**")
                if local_players.empty:
                    render_empty_state("No hay planilla individual del local.")
                else:
                    render_selection_note("Selecciona una fila para abrir el perfil local.")
                    local_event = st.dataframe(
                        local_players[["name", "position", "minutesplayed", "goals", "assists", "saves", "fouls"]],
                        use_container_width=True,
                        hide_index=True,
                        key=f"match_local_players_{summary.match_id}",
                        on_select="rerun",
                        selection_mode="single-row",
                        column_config={
                            "name": "Jugador",
                            "position": "Pos",
                            "minutesplayed": "Min",
                            "goals": "G",
                            "assists": "A",
                            "saves": "At",
                            "fouls": "F",
                        },
                    )
                    row_index = get_selected_row_index(local_event)
                    if action is None and row_index is not None:
                        selected = local_players.iloc[row_index]
                        player_id = safe_optional_int(selected.get("player_id"))
                        team_id = safe_optional_int(selected.get("team_id"))
                        if player_id is not None and team_id is not None:
                            action = build_action(
                                "player",
                                player_id=player_id,
                                team_id=team_id,
                                position=selected.get("position"),
                                match_id=summary.match_id,
                            )
                        else:
                            st.caption("Este registro no tiene identidad completa; se muestra solo como dato del partido.")

            with side_cols[1]:
                st.markdown(f"**{safe_text(row.get('away'), 'Visita')}**")
                if away_players.empty:
                    render_empty_state("No hay planilla individual de la visita.")
                else:
                    render_selection_note("Selecciona una fila para abrir el perfil visitante.")
                    away_event = st.dataframe(
                        away_players[["name", "position", "minutesplayed", "goals", "assists", "saves", "fouls"]],
                        use_container_width=True,
                        hide_index=True,
                        key=f"match_away_players_{summary.match_id}",
                        on_select="rerun",
                        selection_mode="single-row",
                        column_config={
                            "name": "Jugador",
                            "position": "Pos",
                            "minutesplayed": "Min",
                            "goals": "G",
                            "assists": "A",
                            "saves": "At",
                            "fouls": "F",
                        },
                    )
                    row_index = get_selected_row_index(away_event)
                    if action is None and row_index is not None:
                        selected = away_players.iloc[row_index]
                        player_id = safe_optional_int(selected.get("player_id"))
                        team_id = safe_optional_int(selected.get("team_id"))
                        if player_id is not None and team_id is not None:
                            action = build_action(
                                "player",
                                player_id=player_id,
                                team_id=team_id,
                                position=selected.get("position"),
                                match_id=summary.match_id,
                            )
                        else:
                            st.caption("Este registro no tiene identidad completa; se muestra solo como dato del partido.")

    with tabs[4]:
        render_section_title(
            "Contexto alrededor del partido",
            "Que traian ambos equipos antes y despues del encuentro.",
        )
        render_selection_note("Cada tabla contextual abre otro partido dentro del mismo hilo.")
        context_cols = st.columns(2, gap="medium")
        home_team_id = safe_optional_int(row.get("home_id"))
        away_team_id = safe_optional_int(row.get("away_id"))
        with context_cols[0]:
            st.markdown(f"**Tramo de {safe_text(row.get('home'), 'Local')}**")
            if not summary.home_context_matches.empty:
                st.markdown(render_form_chips(summary.home_context_matches["result"].tolist()), unsafe_allow_html=True)
                st.caption(f"{safe_int(summary.home_context_matches['points'].sum())} pts en los partidos contextuales visibles.")
            selected_match = _render_context_table(summary.home_context_matches, f"home_context_{summary.match_id}")
            if action is None and selected_match is not None and home_team_id is not None:
                action = build_action(
                    "match",
                    match_id=selected_match,
                    team_id=home_team_id,
                    venue="Todos",
                    result="Todos",
                    update_origin=False,
                )

        with context_cols[1]:
            st.markdown(f"**Tramo de {safe_text(row.get('away'), 'Visita')}**")
            if not summary.away_context_matches.empty:
                st.markdown(render_form_chips(summary.away_context_matches["result"].tolist()), unsafe_allow_html=True)
                st.caption(f"{safe_int(summary.away_context_matches['points'].sum())} pts en los partidos contextuales visibles.")
            selected_match = _render_context_table(summary.away_context_matches, f"away_context_{summary.match_id}")
            if action is None and selected_match is not None and away_team_id is not None:
                action = build_action(
                    "match",
                    match_id=selected_match,
                    team_id=away_team_id,
                    venue="Todos",
                    result="Todos",
                    update_origin=False,
                )

    render_section_title("Relaciones y saltos", "Atajos directos hacia equipos y protagonistas.")
    relation_cols = st.columns(4, gap="small")
    home_team_id = safe_optional_int(row.get("home_id"))
    away_team_id = safe_optional_int(row.get("away_id"))
    with relation_cols[0]:
        if action is None and home_team_id is not None and render_navigation_surface(
            title=safe_text(row.get("home"), "Local"),
            note="Salta al analisis colectivo del local.",
            key=f"match_relation_home_{summary.match_id}",
            button_label="Abrir local",
            eyebrow="Equipo",
            metadata=[f"ID {home_team_id}", "Relacion directa"],
            variant="primary",
            accent_color=summary.home_team_color,
        ):
            action = build_action("team", team_id=home_team_id)
    with relation_cols[1]:
        if action is None and away_team_id is not None and render_navigation_surface(
            title=safe_text(row.get("away"), "Visita"),
            note="Salta al analisis colectivo del visitante.",
            key=f"match_relation_away_{summary.match_id}",
            button_label="Abrir visita",
            eyebrow="Equipo",
            metadata=[f"ID {away_team_id}", "Relacion directa"],
            variant="secondary",
            accent_color=summary.away_team_color,
        ):
            action = build_action("team", team_id=away_team_id)
    with relation_cols[2]:
        home_star_player_id = safe_optional_int(home_star.get("player_id")) if home_star is not None else None
        home_star_team_id = safe_optional_int(home_star.get("team_id")) if home_star is not None else None
        if action is None and home_star is not None and home_star_player_id is not None and home_star_team_id is not None and render_navigation_surface(
            title=safe_text(home_star.get("name"), "Sin figura clara"),
            note="Figura local del encuentro segun la planilla individual.",
            key=f"match_relation_home_star_{summary.match_id}",
            button_label="Abrir figura local",
            eyebrow="Jugador",
            metadata=[f"G {safe_int(home_star.get('goals'))} | A {safe_int(home_star.get('assists'))}", f"Min {safe_int(home_star.get('minutesplayed'))}"],
            variant="secondary",
            accent_color=summary.home_team_color,
        ):
            action = build_action(
                "player",
                player_id=home_star_player_id,
                team_id=home_star_team_id,
                position=home_star.get("position"),
                match_id=summary.match_id,
            )
    with relation_cols[3]:
        away_star_player_id = safe_optional_int(away_star.get("player_id")) if away_star is not None else None
        away_star_team_id = safe_optional_int(away_star.get("team_id")) if away_star is not None else None
        if action is None and away_star is not None and away_star_player_id is not None and away_star_team_id is not None and render_navigation_surface(
            title=safe_text(away_star.get("name"), "Sin figura clara"),
            note="Figura visitante del encuentro segun la planilla individual.",
            key=f"match_relation_away_star_{summary.match_id}",
            button_label="Abrir figura visita",
            eyebrow="Jugador",
            metadata=[f"G {safe_int(away_star.get('goals'))} | A {safe_int(away_star.get('assists'))}", f"Min {safe_int(away_star.get('minutesplayed'))}"],
            variant="secondary",
            accent_color=summary.away_team_color,
        ):
            action = build_action(
                "player",
                player_id=away_star_player_id,
                team_id=away_star_team_id,
                position=away_star.get("position"),
                match_id=summary.match_id,
            )

    return action
