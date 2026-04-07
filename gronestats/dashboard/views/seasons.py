from __future__ import annotations

import pandas as pd
import streamlit as st

from gronestats.dashboard.models import ConsolidatedSeasonOverview, SeasonDataset
from gronestats.dashboard.state import build_action
from gronestats.dashboard.views.shared import (
    build_bar_figure,
    get_selected_row_index,
    render_empty_state,
    render_metric_cards,
    render_navigation_surface,
    render_section_title,
    render_selection_note,
    safe_float,
    safe_int,
    safe_text,
)


def _validated_label(value: object) -> str:
    if value is None or pd.isna(value):
        return "Sin fecha"
    text = str(value).replace("T", " ")
    return text[:16]


def render_seasons_overview(
    overview: ConsolidatedSeasonOverview,
    *,
    season_catalog: tuple[SeasonDataset, ...],
    active_season_year: int,
) -> dict[str, object] | None:
    action: dict[str, object] | None = None
    published_years = sorted(dataset.season_year for dataset in season_catalog)
    if published_years:
        coverage_span = (
            str(published_years[0])
            if len(published_years) == 1
            else f"{published_years[0]}-{published_years[-1]}"
        )
    else:
        coverage_span = "temporadas publicadas"
    cards = [
        {"label": "Temporadas", "value": f"{overview.total_seasons}", "help": "Releases disponibles para navegar desde el dashboard."},
        {"label": "Partidos", "value": f"{overview.total_matches}", "help": "Suma de partidos publicados entre todas las temporadas."},
        {"label": "Jugadores unicos", "value": f"{overview.total_players}", "help": f"Pool unico detectado al consolidar {coverage_span}."},
        {"label": "Goles", "value": f"{overview.total_goals}", "help": "Produccion ofensiva total de todas las temporadas publicadas."},
        {"label": "Promedio global", "value": f"{overview.goals_per_match:.2f}", "help": "Goles por partido sobre el consolidado completo."},
    ]
    render_metric_cards(cards)

    if overview.seasons_table.empty:
        render_empty_state("No hay temporadas publicadas para consolidar.")
        return None

    season_lookup = {dataset.season_year: dataset for dataset in season_catalog}
    seasons_table = overview.seasons_table.copy()

    top_row = seasons_table.sort_values(["goals_per_match", "season_year"], ascending=[False, False]).iloc[0]
    clean_row = seasons_table.sort_values(["warning_count", "season_year"], ascending=[True, False]).iloc[0]
    render_section_title("Lecturas rapidas", "Salta a la temporada mas productiva o a la release mas estable.")
    quick_cols = st.columns(2, gap="medium")
    with quick_cols[0]:
        top_year = safe_int(top_row.get("season_year"))
        if action is None and render_navigation_surface(
            title=safe_text(top_row.get("season_label"), f"Temporada {top_year}"),
            note=(
                f"Mayor promedio de gol publicado: {safe_float(top_row.get('goals_per_match')):.2f} por partido. "
                f"Top scorer: {safe_text(top_row.get('top_scorer'), 'Sin datos')} ({safe_int(top_row.get('top_scorer_goals'))})."
            ),
            key=f"season_best_attack_{top_year}",
            button_label="Abrir temporada",
            eyebrow="Mayor promedio de gol",
            metadata=[f"{safe_int(top_row.get('matches'))} partidos", safe_text(top_row.get("coverage_label"), "Sin validacion")],
            variant="primary" if top_year != active_season_year else "active",
            active=top_year == active_season_year,
            disabled=top_year == active_season_year,
        ):
            action = build_action("season", season_year=top_year, page="Overview")
    with quick_cols[1]:
        clean_year = safe_int(clean_row.get("season_year"))
        clean_dataset = season_lookup.get(clean_year)
        validation_note = clean_dataset.coverage_label if clean_dataset is not None else safe_text(clean_row.get("coverage_label"), "Sin validacion")
        if action is None and render_navigation_surface(
            title=safe_text(clean_row.get("season_label"), f"Temporada {clean_year}"),
            note=(
                f"Menor friccion operacional: {safe_int(clean_row.get('warning_count'))} warnings. "
                f"Release {safe_text(clean_row.get('release_id'), '-')}"
            ),
            key=f"season_clean_release_{clean_year}",
            button_label="Abrir temporada",
            eyebrow="Release mas estable",
            metadata=[validation_note, _validated_label(clean_row.get("validated_at"))],
            variant="secondary" if clean_year != active_season_year else "active",
            active=clean_year == active_season_year,
            disabled=clean_year == active_season_year,
        ):
            action = build_action("season", season_year=clean_year, page="Overview")

    top_cols = st.columns([1.35, 0.95], gap="large")
    with top_cols[0]:
        render_section_title("Comparativo por temporada", "Selecciona una fila para activar la temporada y abrir su overview.")
        render_selection_note("La seleccion cambia el dataset activo de todo el dashboard.")
        selection = st.dataframe(
            seasons_table[
                [
                    "season_label",
                    "matches",
                    "teams",
                    "players",
                    "goals",
                    "goals_per_match",
                    "coverage_label",
                    "warning_count",
                    "top_scorer",
                    "top_scorer_goals",
                ]
            ],
            use_container_width=True,
            hide_index=True,
            key="season_summary_table",
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "season_label": "Temporada",
                "matches": "Partidos",
                "teams": "Equipos",
                "players": "Jugadores",
                "goals": "Goles",
                "goals_per_match": "Goles/partido",
                "coverage_label": "Cobertura",
                "warning_count": "Warnings",
                "top_scorer": "Goleador",
                "top_scorer_goals": "Goles del goleador",
            },
        )
        row_index = get_selected_row_index(selection)
        if action is None and row_index is not None:
            season_year = safe_int(seasons_table.iloc[row_index].get("season_year"))
            action = build_action("season", season_year=season_year, page="Overview")

    with top_cols[1]:
        render_section_title("Temporadas publicadas", "Accesos directos hacia el overview de cada release.")
        for _, row in seasons_table.iterrows():
            season_year = safe_int(row.get("season_year"))
            is_active = season_year == active_season_year
            dataset = season_lookup.get(season_year)
            coverage_label = dataset.coverage_label if dataset is not None else safe_text(row.get("coverage_label"), "Sin validacion")
            if action is None and render_navigation_surface(
                title=safe_text(row.get("season_label"), f"Temporada {season_year}"),
                note=(
                    f"{safe_int(row.get('matches'))} partidos | {safe_int(row.get('goals'))} goles | "
                    f"Goleador: {safe_text(row.get('top_scorer'), 'Sin datos')} ({safe_int(row.get('top_scorer_goals'))})"
                ),
                key=f"season_nav_{season_year}",
                button_label="Activa" if is_active else "Abrir overview",
                eyebrow="Temporada activa" if is_active else "Release publicada",
                metadata=[coverage_label, f"Warnings {safe_int(row.get('warning_count'))}", _validated_label(row.get("validated_at"))],
                variant="active" if is_active else "secondary",
                active=is_active,
                disabled=is_active,
            ):
                action = build_action("season", season_year=season_year, page="Overview")

    bottom_cols = st.columns(2, gap="large")
    chart_frame = seasons_table.sort_values("season_year").copy()
    chart_frame["season"] = chart_frame["season_year"].astype(int).astype(str)
    with bottom_cols[0]:
        render_section_title("Partidos publicados", "Lectura del volumen publicado por temporada.")
        st.plotly_chart(
            build_bar_figure(chart_frame, "season", "matches", "#c6b170"),
            use_container_width=True,
        )
    with bottom_cols[1]:
        render_section_title("Promedio de gol", "Compara densidad ofensiva entre temporadas.")
        st.plotly_chart(
            build_bar_figure(chart_frame, "season", "goals_per_match", "#7ec4b8"),
            use_container_width=True,
        )

    return action
