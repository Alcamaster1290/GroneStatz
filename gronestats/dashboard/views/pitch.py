from __future__ import annotations

from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D
from mplsoccer import VerticalPitch
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from gronestats.dashboard.config import COLORS
from gronestats.dashboard.views.shared import build_team_palette, safe_int, safe_text


PLAYER_HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "gs_player_heatmap",
    ["#102030", "#2b4a5d", COLORS["accent"], "#efe1a8"],
    N=12,
)


def _base_pitch(figsize: tuple[float, float]) -> tuple[VerticalPitch, plt.Figure, plt.Axes]:
    pitch = VerticalPitch(
        pitch_type="opta",
        pitch_color=COLORS["surface"],
        line_color="#dbe4ef",
        linewidth=1.05,
    )
    fig, ax = pitch.draw(figsize=figsize)
    fig.patch.set_facecolor(COLORS["surface"])
    ax.set_facecolor(COLORS["surface"])
    return pitch, fig, ax


def _annotate_marker(
    pitch: VerticalPitch,
    ax: plt.Axes,
    *,
    x: float,
    y: float,
    label: str,
    facecolor: str,
    edgecolor: str = "#f6f4ef",
    size: int = 340,
) -> None:
    pitch.scatter(
        x,
        y,
        ax=ax,
        s=size,
        color=facecolor,
        edgecolors=edgecolor,
        linewidth=1.4,
        zorder=3,
        alpha=0.95,
    )
    pitch.annotate(
        label,
        xy=(x, y),
        ax=ax,
        c="#081019",
        ha="center",
        va="center",
        size=9,
        weight="bold",
        zorder=4,
    )


def build_player_average_position_figure(
    position_row: pd.Series,
    *,
    team_color: str | None = None,
    title_suffix: str = "posicion promedio",
    footer_note: str | None = None,
):
    pitch, fig, ax = _base_pitch((5.8, 8.2))
    palette = build_team_palette(team_color or COLORS["accent"])
    x = float(position_row["average_x"])
    y = float(position_row["average_y"])
    label = str(safe_int(position_row.get("shirt_number"))) if pd.notna(position_row.get("shirt_number")) else safe_text(position_row.get("position"), "?")
    _annotate_marker(pitch, ax, x=x, y=y, label=label, facecolor=palette["primary"])
    ax.set_title(
        f"{safe_text(position_row.get('name'), 'Jugador')} | {title_suffix}",
        color=COLORS["text"],
        fontsize=13,
        pad=14,
    )
    ax.text(
        0.03,
        0.02,
        footer_note or f"Puntos registrados: {safe_int(position_row.get('points_count'))}",
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=9,
    )
    return fig


def build_player_heatmap_figure(
    heatmap_points: pd.DataFrame,
    average_position_row: pd.Series | None = None,
    *,
    title_suffix: str = "heatmap del jugador",
    footer_note: str | None = None,
    team_color: str | None = None,
):
    pitch, fig, ax = _base_pitch((5.8, 8.2))
    palette = build_team_palette(team_color or COLORS["accent"])
    pitch.hexbin(
        heatmap_points["x"],
        heatmap_points["y"],
        ax=ax,
        gridsize=(12, 9),
        edgecolors="none",
        cmap=PLAYER_HEATMAP_CMAP,
        alpha=0.9,
        mincnt=1,
    )
    if average_position_row is not None:
        label = (
            str(safe_int(average_position_row.get("shirt_number")))
            if pd.notna(average_position_row.get("shirt_number"))
            else safe_text(average_position_row.get("position"), "?")
        )
        _annotate_marker(
            pitch,
            ax,
            x=float(average_position_row["average_x"]),
            y=float(average_position_row["average_y"]),
            label=label,
            facecolor="#f3e9be",
            edgecolor=palette["primary"],
            size=220,
        )
    focus_name = safe_text(
        average_position_row.get("name") if average_position_row is not None else heatmap_points["name"].iloc[0],
        "Jugador",
    )
    ax.set_title(
        f"{focus_name} | {title_suffix}",
        color=COLORS["text"],
        fontsize=13,
        pad=14,
    )
    ax.text(
        0.03,
        0.02,
        footer_note or f"Puntos de calor: {len(heatmap_points)}",
        transform=ax.transAxes,
        color=COLORS["muted"],
        fontsize=9,
    )
    return fig


def build_match_average_positions_figure(
    team_average_positions: pd.DataFrame,
    *,
    home_team: str,
    away_team: str,
    metadata: dict[str, object] | None = None,
    home_color: str | None = None,
    away_color: str | None = None,
):
    pitch, fig, ax = _base_pitch((6.8, 10.4))
    home_palette = build_team_palette(home_color or COLORS["accent"])
    away_palette = build_team_palette(away_color or COLORS["accent_alt"])

    for side, color, team_label in [
        ("Local", home_palette["primary"], home_team),
        ("Visita", away_palette["primary"], away_team),
    ]:
        subset = team_average_positions[team_average_positions["side"] == side].copy()
        if subset.empty:
            continue
        if side == "Visita":
            subset["display_x"] = 100 - subset["average_x"]
            subset["display_y"] = 100 - subset["average_y"]
        else:
            subset["display_x"] = subset["average_x"]
            subset["display_y"] = subset["average_y"]
        for _, row in subset.iterrows():
            marker_label = (
                str(safe_int(row.get("shirt_number")))
                if pd.notna(row.get("shirt_number"))
                else safe_text(row.get("position"), "?")
            )
            _annotate_marker(
                pitch,
                ax,
                x=float(row["display_x"]),
                y=float(row["display_y"]),
                label=marker_label,
                facecolor=color,
                edgecolor="#f4f4f0",
                size=300,
            )
        ax.text(
            0.03 if side == "Local" else 0.97,
            0.98,
            team_label,
            transform=ax.transAxes,
            ha="left" if side == "Local" else "right",
            va="top",
            color=color,
            fontsize=11,
            fontweight="bold",
        )

    if metadata:
        ax.text(
            0.03,
            0.02,
            f"Local: {safe_text(metadata.get('home_strategy'), 'sin datos')} | Visita: {safe_text(metadata.get('away_strategy'), 'sin datos')}",
            transform=ax.transAxes,
            color=COLORS["muted"],
            fontsize=9,
        )
    ax.set_title("Posiciones promedio de ambos equipos", color=COLORS["text"], fontsize=14, pad=14)
    return fig


def _shot_marker(outcome: str) -> str:
    marker_map = {
        "goal": "*",
        "save": "o",
        "block": "X",
        "post": "P",
        "miss": "^",
    }
    return marker_map.get(outcome, "o")


def _shot_size(outcome: str) -> int:
    if outcome == "goal":
        return 290
    if outcome in {"save", "post"}:
        return 145
    if outcome == "block":
        return 135
    return 120


def _legacy_shot_color(outcome: str) -> str:
    color_map = {
        "block": "coral",
        "miss": "darkred",
        "goal": "darkgreen",
        "save": "darkgoldenrod",
        "post": "darkgoldenrod",
    }
    return color_map.get(outcome, "gray")


def _legacy_shot_symbol(outcome: str) -> str:
    symbol_map = {
        "goal": "star",
        "save": "circle",
        "post": "diamond",
        "block": "x",
        "miss": "triangle-up",
    }
    return symbol_map.get(outcome, "circle")


def build_match_shotmap_figure(
    shot_events: pd.DataFrame,
    *,
    home_team: str,
    away_team: str,
    metadata: dict[str, object] | None = None,
    home_color: str | None = None,
    away_color: str | None = None,
):
    pitch, fig, ax = _base_pitch((6.9, 10.4))
    home_palette = build_team_palette(home_color or COLORS["accent"])
    away_palette = build_team_palette(away_color or COLORS["accent_alt"])

    plotted = False
    side_series = shot_events.get("side", pd.Series(index=shot_events.index, dtype="object"))
    for side, team_label, side_color in [
        ("Local", home_team, home_palette["primary"]),
        ("Visita", away_team, away_palette["primary"]),
    ]:
        subset = shot_events[side_series == side].copy()
        if subset.empty:
            continue
        if "has_pitch_coordinates" in subset.columns:
            subset = subset[subset["has_pitch_coordinates"] == True].copy()  # noqa: E712
        subset = subset.dropna(subset=["display_x", "display_y"])
        if subset.empty:
            continue
        plotted = True
        shot_type_series = subset.get("shot_type_norm", pd.Series(index=subset.index, dtype="object"))
        for outcome in ["goal", "save", "block", "post", "miss"]:
            event_subset = subset[shot_type_series == outcome]
            if event_subset.empty:
                continue
            pitch.scatter(
                event_subset["display_x"],
                event_subset["display_y"],
                ax=ax,
                marker=_shot_marker(outcome),
                s=_shot_size(outcome),
                color=side_color,
                edgecolors="#f6f4ef",
                linewidth=1.1,
                alpha=0.92 if outcome == "goal" else 0.78,
                zorder=3 if outcome == "goal" else 2,
            )

    ax.text(0.03, 0.98, home_team, transform=ax.transAxes, ha="left", va="top", color=home_palette["primary"], fontsize=11, fontweight="bold")
    ax.text(0.97, 0.98, away_team, transform=ax.transAxes, ha="right", va="top", color=away_palette["primary"], fontsize=11, fontweight="bold")
    ax.set_title("Mapa de tiros comparativo", color=COLORS["text"], fontsize=14, pad=14)

    if plotted:
        handles = [
            Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=home_palette["primary"], markeredgecolor="#f6f4ef", label="Local"),
            Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=away_palette["primary"], markeredgecolor="#f6f4ef", label="Visita"),
            Line2D([0], [0], marker="*", linestyle="none", color="#f6f4ef", label="Gol"),
            Line2D([0], [0], marker="o", linestyle="none", color="#f6f4ef", label="Atajada"),
            Line2D([0], [0], marker="X", linestyle="none", color="#f6f4ef", label="Bloqueado"),
            Line2D([0], [0], marker="^", linestyle="none", color="#f6f4ef", label="Desviado"),
        ]
        legend = ax.legend(
            handles=handles,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.03),
            ncol=3,
            fontsize=8,
            frameon=True,
            facecolor=COLORS["surface_alt"],
            edgecolor=COLORS["border"],
        )
        legend.get_frame().set_alpha(0.95)
    else:
        ax.text(
            0.5,
            0.5,
            "No hay eventos de tiro con coordenadas",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color=COLORS["muted"],
            fontsize=10,
        )

    if metadata:
        footer = (
            f"{home_team}: {safe_int(metadata.get('home_shots'))} tiros | "
            f"{safe_int(metadata.get('home_on_target'))} al arco | "
            f"{safe_int(metadata.get('home_goals'))} goles\n"
            f"{away_team}: {safe_int(metadata.get('away_shots'))} tiros | "
            f"{safe_int(metadata.get('away_on_target'))} al arco | "
            f"{safe_int(metadata.get('away_goals'))} goles"
        )
        ax.text(0.03, 0.02, footer, transform=ax.transAxes, color=COLORS["muted"], fontsize=8.6, va="bottom")
    return fig


def _add_goal_mouth_shapes(fig: go.Figure, *, xref: str, yref: str) -> None:
    palo_exterior = 45.4
    palo_interior = 45.6
    travesano_inferior = 0
    travesano_superior = 35.5
    palo_opuesto_exterior = 54.6
    palo_opuesto_interior = 54.4

    for shape in [
        dict(type="line", x0=palo_exterior, y0=travesano_inferior, x1=palo_exterior, y1=travesano_superior, line=dict(color="black", width=4)),
        dict(type="line", x0=palo_opuesto_exterior, y0=travesano_inferior, x1=palo_opuesto_exterior, y1=travesano_superior, line=dict(color="black", width=4)),
        dict(type="line", x0=palo_exterior, y0=travesano_superior, x1=palo_opuesto_exterior, y1=travesano_superior, line=dict(color="black", width=8)),
        dict(type="line", x0=palo_interior, y0=travesano_inferior, x1=palo_interior, y1=travesano_superior, line=dict(color="black", width=4)),
        dict(type="line", x0=palo_opuesto_interior, y0=travesano_inferior, x1=palo_opuesto_interior, y1=travesano_superior, line=dict(color="black", width=4)),
        dict(type="line", x0=palo_interior, y0=travesano_superior, x1=palo_opuesto_interior, y1=travesano_superior, line=dict(color="black", width=4)),
        dict(type="rect", x0=palo_exterior, y0=travesano_inferior, x1=palo_interior, y1=travesano_superior, fillcolor="white", line=dict(width=0)),
        dict(type="rect", x0=palo_opuesto_interior, y0=travesano_inferior, x1=palo_opuesto_exterior, y1=travesano_superior, fillcolor="white", line=dict(width=0)),
        dict(type="line", x0=palo_exterior, y0=travesano_superior, x1=palo_opuesto_exterior, y1=travesano_superior, line=dict(color="white", width=10)),
    ]:
        fig.add_shape(xref=xref, yref=yref, **shape)


def build_match_goalmouth_figure(
    shot_events: pd.DataFrame,
    *,
    home_team: str,
    away_team: str,
    metadata: dict[str, object] | None = None,
) -> go.Figure:
    figure = make_subplots(
        rows=1,
        cols=2,
        subplot_titles=(home_team, away_team),
        horizontal_spacing=0.08,
    )
    figure.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=64, b=20),
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor=COLORS["surface_alt"],
            bordercolor=COLORS["border"],
            borderwidth=1,
            font=dict(color=COLORS["text"], size=11),
        ),
        title=dict(text="Definiciones sobre el arco", font=dict(color=COLORS["text"], size=15)),
    )

    plotted = False
    outcome_order = ["goal", "save", "post", "block", "miss"]
    side_series = shot_events.get("side", pd.Series(index=shot_events.index, dtype="object"))
    for col_index, side in enumerate(["Local", "Visita"], start=1):
        subset = shot_events[side_series == side].copy()
        if "has_goal_mouth_coordinates" in subset.columns:
            subset = subset[subset["has_goal_mouth_coordinates"] == True].copy()  # noqa: E712
        subset = subset.dropna(subset=["goal_mouth_y", "goal_mouth_z"])
        if not subset.empty:
            plotted = True

        for outcome in outcome_order:
            event_subset = subset[subset.get("shot_type_norm", pd.Series(index=subset.index, dtype="object")) == outcome]
            if event_subset.empty:
                continue
            customdata = pd.DataFrame(
                {
                    "name": event_subset.get("name", pd.Series(index=event_subset.index, dtype="object")).fillna("Sin nombre"),
                    "team_name": event_subset.get("team_name", pd.Series(index=event_subset.index, dtype="object")).fillna(
                        home_team if side == "Local" else away_team
                    ),
                    "shot_type": event_subset.get("shot_type", pd.Series(index=event_subset.index, dtype="object")).fillna(outcome),
                    "minute_label": event_subset.get("minute_label", pd.Series(index=event_subset.index, dtype="object")).fillna("-"),
                    "situation": event_subset.get("situation", pd.Series(index=event_subset.index, dtype="object")).fillna("Sin situacion"),
                    "body_part": event_subset.get("body_part", pd.Series(index=event_subset.index, dtype="object")).fillna("Sin perfil"),
                    "goal_mouth_location": event_subset.get(
                        "goal_mouth_location",
                        pd.Series(index=event_subset.index, dtype="object"),
                    ).fillna("Sin zona"),
                }
            )
            figure.add_trace(
                go.Scatter(
                    x=event_subset["goal_mouth_y"],
                    y=event_subset["goal_mouth_z"],
                    mode="markers",
                    name=outcome.capitalize(),
                    legendgroup=outcome,
                    showlegend=col_index == 1,
                    customdata=customdata,
                    marker=dict(
                        size=12,
                        color=_legacy_shot_color(outcome),
                        symbol=_legacy_shot_symbol(outcome),
                        line=dict(width=1.8, color="black"),
                        opacity=0.9,
                    ),
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Jugador: %{customdata[0]}<br>"
                        "Tiro: %{customdata[2]}<br>"
                        "Minuto: %{customdata[3]}<br>"
                        "Situacion: %{customdata[4]}<br>"
                        "Perfil: %{customdata[5]}<br>"
                        "Zona de arco: %{customdata[6]}<extra></extra>"
                    ),
                ),
                row=1,
                col=col_index,
            )

        axis_suffix = "" if col_index == 1 else str(col_index)
        figure.update_xaxes(
            range=[60, 40],
            showgrid=False,
            visible=False,
            row=1,
            col=col_index,
        )
        figure.update_yaxes(
            range=[0, 85],
            showgrid=False,
            visible=False,
            row=1,
            col=col_index,
        )
        _add_goal_mouth_shapes(figure, xref=f"x{axis_suffix}", yref=f"y{axis_suffix}")

        if subset.empty:
            figure.add_annotation(
                x=50,
                y=42,
                xref=f"x{axis_suffix}",
                yref=f"y{axis_suffix}",
                text="Sin tiros con<br>coordenadas de arco",
                showarrow=False,
                font=dict(color=COLORS["muted"], size=12),
                align="center",
            )

    if metadata:
        figure.add_annotation(
            x=0.5,
            y=-0.14,
            xref="paper",
            yref="paper",
            text=(
                f"{home_team}: {safe_int(metadata.get('home_shots'))} tiros | "
                f"{safe_int(metadata.get('home_on_target'))} al arco | "
                f"{safe_int(metadata.get('home_goals'))} goles &nbsp;&nbsp;|&nbsp;&nbsp; "
                f"{away_team}: {safe_int(metadata.get('away_shots'))} tiros | "
                f"{safe_int(metadata.get('away_on_target'))} al arco | "
                f"{safe_int(metadata.get('away_goals'))} goles"
            ),
            showarrow=False,
            font=dict(color=COLORS["muted"], size=11),
        )

    if not plotted:
        figure.add_annotation(
            x=0.5,
            y=0.5,
            xref="paper",
            yref="paper",
            text="No hay coordenadas de arco para este partido",
            showarrow=False,
            font=dict(color=COLORS["muted"], size=12),
        )
    return figure


def build_match_momentum_figure(
    momentum_series: pd.DataFrame,
    *,
    home_team: str,
    away_team: str,
    home_color: str | None = None,
    away_color: str | None = None,
):
    home_palette = build_team_palette(home_color or COLORS["accent"])
    away_palette = build_team_palette(away_color or COLORS["accent_alt"])
    fig, ax = plt.subplots(figsize=(7.6, 3.8))
    fig.patch.set_facecolor(COLORS["surface"])
    ax.set_facecolor(COLORS["surface"])

    if momentum_series.empty:
        ax.text(0.5, 0.5, "No hay serie de momentum para este partido", ha="center", va="center", color=COLORS["muted"], transform=ax.transAxes, fontsize=10)
        ax.set_axis_off()
        return fig

    series = momentum_series.copy()
    series["minute"] = pd.to_numeric(series.get("minute"), errors="coerce")
    series["value"] = pd.to_numeric(series.get("value"), errors="coerce")
    series = series.dropna(subset=["minute", "value"]).sort_values("minute", kind="mergesort")
    if series.empty:
        ax.text(0.5, 0.5, "No hay serie de momentum valida para este partido", ha="center", va="center", color=COLORS["muted"], transform=ax.transAxes, fontsize=10)
        ax.set_axis_off()
        return fig

    minutes = series["minute"]
    values = series["value"]
    smoothed = series["rolling_value"] if "rolling_value" in series.columns else values.rolling(window=5, min_periods=1, center=True).mean()

    ax.axhline(0, color=COLORS["border"], linewidth=1.1, alpha=0.8)
    ax.fill_between(minutes, 0, values.clip(lower=0), color=home_palette["primary"], alpha=0.35, step="mid", label=home_team)
    ax.fill_between(minutes, 0, values.clip(upper=0), color=away_palette["primary"], alpha=0.35, step="mid", label=away_team)
    ax.plot(minutes, values, color="#dfe6f0", linewidth=0.95, alpha=0.65)
    ax.plot(minutes, smoothed, color=COLORS["accent"], linewidth=2.1, alpha=0.95, label="Tendencia")

    max_minute = max(float(minutes.max()), 90.0)
    ax.set_xlim(0, max_minute + 1)
    max_abs = max(float(values.abs().max()), 10.0)
    ax.set_ylim(-max_abs * 1.16, max_abs * 1.16)

    for milestone in [45, 90]:
        if milestone <= max_minute + 1:
            ax.axvline(milestone, color=COLORS["border"], linewidth=0.8, linestyle="--", alpha=0.55)

    ax.set_title("Momentum del partido", color=COLORS["text"], fontsize=13, pad=10)
    ax.set_xlabel("Minuto", color=COLORS["muted"], fontsize=9)
    ax.set_ylabel("Impulso", color=COLORS["muted"], fontsize=9)
    ax.tick_params(colors=COLORS["muted"], labelsize=8.5)
    ax.grid(axis="y", color=COLORS["border"], alpha=0.26, linewidth=0.7)
    ax.legend(loc="upper right", fontsize=8, frameon=False, labelcolor=COLORS["text"])
    return fig


def build_goalkeeper_saves_figure(
    goalkeeper_saves: pd.DataFrame,
    *,
    home_team: str,
    away_team: str,
    home_color: str | None = None,
    away_color: str | None = None,
):
    home_palette = build_team_palette(home_color or COLORS["accent"])
    away_palette = build_team_palette(away_color or COLORS["accent_alt"])
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    fig.patch.set_facecolor(COLORS["surface"])
    ax.set_facecolor(COLORS["surface"])

    if goalkeeper_saves.empty:
        ax.text(0.5, 0.5, "No hay atajadas de arquero registradas en este partido", ha="center", va="center", color=COLORS["muted"], transform=ax.transAxes, fontsize=10)
        ax.set_axis_off()
        return fig

    frame = goalkeeper_saves.copy()
    frame["saves"] = pd.to_numeric(frame.get("saves"), errors="coerce").fillna(0)
    frame["minutesplayed"] = pd.to_numeric(frame.get("minutesplayed"), errors="coerce").fillna(0)
    frame["label"] = frame.apply(
        lambda row: f"{safe_text(row.get('name'), 'Arquero')} ({safe_text(row.get('team_name'), 'Sin equipo')})",
        axis=1,
    )
    frame = frame.sort_values(["side", "saves", "minutesplayed"], ascending=[True, False, False], kind="mergesort").reset_index(drop=True)
    colors = frame["side"].map({"Local": home_palette["primary"], "Visita": away_palette["primary"]}).fillna(COLORS["muted"]).tolist()

    bars = ax.barh(frame["label"], frame["saves"], color=colors, edgecolor="#f6f4ef", linewidth=0.9, alpha=0.88)
    ax.invert_yaxis()
    for bar, value in zip(bars, frame["saves"].tolist()):
        ax.text(
            float(bar.get_width()) + 0.08,
            bar.get_y() + bar.get_height() / 2,
            str(int(value)),
            va="center",
            ha="left",
            color=COLORS["text"],
            fontsize=9,
            fontweight="bold",
        )

    max_saves = max(frame["saves"].max(), 1)
    ax.set_xlim(0, max_saves + 1.3)
    ax.set_xlabel("Atajadas", color=COLORS["muted"], fontsize=9)
    ax.set_title(f"Atajadas de arquero | {home_team} vs {away_team}", color=COLORS["text"], fontsize=13, pad=10)
    ax.tick_params(axis="x", colors=COLORS["muted"], labelsize=8.5)
    ax.tick_params(axis="y", colors=COLORS["text"], labelsize=8.7)
    ax.grid(axis="x", color=COLORS["border"], alpha=0.25, linewidth=0.7)
    return fig
