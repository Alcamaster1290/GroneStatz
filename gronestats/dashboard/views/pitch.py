from __future__ import annotations

from matplotlib import pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from mplsoccer import VerticalPitch
import pandas as pd

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
