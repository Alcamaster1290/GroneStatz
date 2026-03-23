from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Iterable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from gronestats.dashboard.config import APP_TITLE, BASE_CSS, COLORS, SEASON_LABEL


HEX_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")


def inject_base_styles() -> None:
    st.markdown(BASE_CSS, unsafe_allow_html=True)


def safe_text(value: object, fallback: str = "Sin dato") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return fallback
    return text


def safe_float(value: object, default: float = 0.0) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(default).iloc[0]
    return float(numeric)


def safe_int(value: object, default: int = 0) -> int:
    return int(round(safe_float(value, default=default)))


def safe_optional_int(value: object) -> int | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return int(float(numeric))


def normalize_hex_color(value: object, fallback: str = COLORS["accent"]) -> str:
    text = safe_text(value, fallback).lower()
    if HEX_COLOR_PATTERN.match(text):
        return text
    return fallback


def rgba_from_hex(hex_color: str, alpha: float) -> str:
    color = normalize_hex_color(hex_color)
    alpha = max(0.0, min(alpha, 1.0))
    red = int(color[1:3], 16)
    green = int(color[3:5], 16)
    blue = int(color[5:7], 16)
    return f"rgba({red}, {green}, {blue}, {alpha:.3f})"


def mix_hex(color_a: str, color_b: str, ratio: float) -> str:
    first = normalize_hex_color(color_a)
    second = normalize_hex_color(color_b)
    ratio = max(0.0, min(ratio, 1.0))
    inv = 1.0 - ratio
    channels = []
    for index in (1, 3, 5):
        channel_a = int(first[index : index + 2], 16)
        channel_b = int(second[index : index + 2], 16)
        channels.append(round(channel_a * inv + channel_b * ratio))
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def build_team_palette(primary: object, fallback: str = COLORS["accent"]) -> dict[str, str]:
    base = normalize_hex_color(primary, fallback)
    return {
        "primary": base,
        "line": mix_hex(base, COLORS["text"], 0.18),
        "soft_bg": rgba_from_hex(base, 0.12),
        "soft_bg_strong": rgba_from_hex(base, 0.18),
        "border": rgba_from_hex(base, 0.32),
        "chip_bg": rgba_from_hex(base, 0.16),
        "chip_border": rgba_from_hex(base, 0.24),
        "glow": rgba_from_hex(base, 0.20),
        "muted": mix_hex(base, COLORS["muted"], 0.48),
    }


def render_app_header(page_title: str, subtitle: str, loaded_at: datetime, *, scope_summary: str | None = None) -> None:
    formatted_timestamp = loaded_at.strftime("%d/%m/%Y %H:%M:%S")
    scope_chip = f"<span class=\"gs-chip\">Filtros activos: {scope_summary}</span>" if scope_summary else ""
    html = f"""
    <section class="gs-shell">
      <header class="gs-header">
        <span class="gs-header__eyebrow">{APP_TITLE} | {SEASON_LABEL}</span>
        <h1 class="gs-header__title">{page_title}</h1>
        <p class="gs-header__subtitle">{subtitle}</p>
        <div class="gs-chip-row">
          {scope_chip}
          <span class="gs-chip">Cobertura verificada 2025</span>
          <span class="gs-chip">Parquets normalizados</span>
          <span class="gs-chip">Actualizado en carga: {formatted_timestamp}</span>
        </div>
      </header>
    </section>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_section_title(title: str, note: str | None = None) -> None:
    st.markdown(f"<h2 class='gs-section-title'>{title}</h2>", unsafe_allow_html=True)
    if note:
        st.markdown(f"<p class='gs-note'>{note}</p>", unsafe_allow_html=True)


def render_metric_cards(cards: list[dict[str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, card in zip(columns, cards):
        html = f"""
        <div class="gs-kpi-card">
          <span class="gs-kpi-card__label">{card["label"]}</span>
          <strong class="gs-kpi-card__value">{card["value"]}</strong>
          <span class="gs-kpi-card__help">{card["help"]}</span>
        </div>
        """
        column.markdown(html, unsafe_allow_html=True)


def render_action_button(
    label: str,
    key: str,
    *,
    variant: str = "secondary",
    help: str | None = None,
    disabled: bool = False,
    width: str = "stretch",
) -> bool:
    button_type = "primary" if variant in {"primary", "active"} else "secondary"
    return st.button(
        label,
        key=key,
        type=button_type,
        help=help,
        disabled=disabled,
        width=width,
    )


def render_selection_note(message: str) -> None:
    st.markdown(f"<div class='gs-selection-note'>{message}</div>", unsafe_allow_html=True)


def render_navigation_surface(
    *,
    title: str,
    note: str,
    key: str,
    button_label: str,
    eyebrow: str | None = None,
    metadata: list[str] | None = None,
    variant: str = "secondary",
    active: bool = False,
    compact: bool = False,
    disabled: bool = False,
    help: str | None = None,
    accent_color: str | None = None,
) -> bool:
    state_class = " gs-link-card--active" if active else ""
    palette = build_team_palette(accent_color or COLORS["accent"])
    card_style = (
        f"border-color:{palette['border']}; "
        f"background:linear-gradient(180deg, {palette['soft_bg_strong']}, rgba(255,255,255,0.018)), rgba(15, 24, 36, 0.9);"
        if accent_color
        else ""
    )
    meta_html = ""
    if metadata:
        meta_html = "<div class='gs-link-card__meta'>" + "".join(
            f"<span style='border-color:{palette['chip_border']}; background:{palette['chip_bg']};'>{item}</span>" for item in metadata
        ) + "</div>"
    eyebrow_html = (
        f"<span class='gs-link-card__eyebrow' style='color:{palette['primary']};'>{eyebrow}</span>"
        if eyebrow
        else ""
    )
    card_html = f"""
    <div class="gs-link-card{state_class}" style="{card_style}">
      {eyebrow_html}
      <div class="gs-link-card__title">{title}</div>
      <div class="gs-link-card__note">{note}</div>
      {meta_html}
    </div>
    """
    if compact:
        card_col, button_col = st.columns([4, 1.1], gap="small")
        with card_col:
            st.markdown(card_html, unsafe_allow_html=True)
        with button_col:
            return render_action_button(
                button_label,
                key=key,
                variant="active" if active else variant,
                help=help,
                disabled=disabled,
                width="stretch",
            )
    st.markdown(card_html, unsafe_allow_html=True)
    return render_action_button(
        button_label,
        key=key,
        variant="active" if active else variant,
        help=help,
        disabled=disabled,
        width="stretch",
    )


def render_panel_open() -> None:
    st.markdown("<div class='gs-panel'>", unsafe_allow_html=True)


def render_panel_close() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_empty_state(message: str) -> None:
    st.markdown(f"<div class='gs-empty'>{message}</div>", unsafe_allow_html=True)


def render_form_chips(results: Iterable[str]) -> str:
    chips = []
    for result in results:
        code = result if result in {"W", "D", "L"} else "NA"
        label = result if code != "NA" else "Sin datos"
        chips.append(f"<span class='gs-form-chip gs-form-chip--{code}'>{label}</span>")
    return "<div class='gs-form-row'>" + "".join(chips) + "</div>"


def render_identity_panel(
    title: str,
    subtitle: str,
    image_path: Path | None = None,
    metadata: list[str] | None = None,
    *,
    accent_color: str | None = None,
    accent_label: str | None = None,
) -> None:
    render_panel_open()
    left, right = st.columns([0.55, 2.45], gap="medium", vertical_alignment="center")
    palette = build_team_palette(accent_color or COLORS["accent"])
    with left:
        if image_path and image_path.exists():
            st.image(str(image_path), width="stretch")
        else:
            st.markdown(
                """
                <div class="gs-kpi-card" style="min-height:88px; place-items:center; text-align:center;">
                  <span class="gs-kpi-card__label">Sin imagen</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        meta_html = ""
        if metadata:
            meta_html = "<div class='gs-mini-meta'>" + "".join(
                f"<span style='color:{palette['muted']};'>{item}</span>" for item in metadata
            ) + "</div>"
        accent_html = ""
        if accent_label:
            accent_html = (
                f"<span class='gs-chip' style='width:max-content; margin-bottom:0.28rem; "
                f"border-color:{palette['chip_border']}; background:{palette['chip_bg']}; color:{palette['primary']};'>"
                f"{accent_label}</span>"
            )
        st.markdown(
            f"""
            {accent_html}
            <h3 style="margin:0; font-size:1.32rem; font-weight:800; line-height:1.08;">{title}</h3>
            <p style="margin:0.16rem 0 0; color:{COLORS["muted"]}; font-size:0.88rem; line-height:1.42;">{subtitle}</p>
            {meta_html}
            """,
            unsafe_allow_html=True,
        )
    render_panel_close()


def render_player_spotlight_card(
    *,
    kicker: str,
    title: str,
    stat_line: str,
    image_path: Path | None = None,
    note: str | None = None,
    button_label: str | None = None,
    button_key: str | None = None,
    button_variant: str = "secondary",
    button_disabled: bool = False,
    accent_color: str | None = None,
) -> bool:
    palette = build_team_palette(accent_color or COLORS["accent"])
    image_col, body_col = st.columns([0.5, 1.55], gap="small", vertical_alignment="center")
    with image_col:
        if image_path and image_path.exists():
            st.image(str(image_path), width="stretch")
        else:
            st.markdown(
                """
                <div class="gs-spotlight__image-fallback">
                  <span>Sin foto</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with body_col:
        st.markdown(
            f"""
            <div class="gs-spotlight gs-spotlight--media" style="border-color:{palette['border']}; background:linear-gradient(180deg, {palette['soft_bg_strong']}, rgba(255,255,255,0.015)), rgba(15, 24, 36, 0.88);">
              <span class="gs-spotlight__kicker" style="color:{palette['primary']};">{kicker}</span>
              <strong class="gs-spotlight__title">{title}</strong>
              <span class="gs-spotlight__meta">{stat_line}</span>
              {f'<span class="gs-spotlight__note">{note}</span>' if note else ''}
            </div>
            """,
            unsafe_allow_html=True,
        )
    if button_label and button_key:
        return render_action_button(
            button_label,
            key=button_key,
            variant=button_variant,
            disabled=button_disabled,
            width="stretch",
        )
    return False


def get_selected_row_index(event) -> int | None:
    if event is None or not hasattr(event, "selection"):
        return None
    rows = getattr(event.selection, "rows", [])
    if not rows:
        return None
    return int(rows[0])


def apply_chart_theme(figure: go.Figure) -> go.Figure:
    figure.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Plus Jakarta Sans, sans-serif", "color": COLORS["text"]},
        margin={"l": 18, "r": 18, "t": 18, "b": 18},
        legend={"orientation": "h", "y": 1.05, "x": 0},
        xaxis={"gridcolor": "rgba(154, 168, 186, 0.14)", "zeroline": False},
        yaxis={"gridcolor": "rgba(154, 168, 186, 0.08)", "zeroline": False},
    )
    return figure


def build_bar_figure(frame, x: str, y: str, color: str, horizontal: bool = False) -> go.Figure:
    if horizontal:
        figure = go.Figure(
            data=[
                go.Bar(
                    x=frame[x],
                    y=frame[y],
                    orientation="h",
                    marker_color=color,
                    hovertemplate="%{y}: %{x}<extra></extra>",
                )
            ]
        )
    else:
        figure = go.Figure(
            data=[
                go.Bar(
                    x=frame[x],
                    y=frame[y],
                    marker_color=color,
                    hovertemplate="%{x}: %{y}<extra></extra>",
                )
            ]
        )
    return apply_chart_theme(figure)


def build_line_figure(frame, x: str, y: str) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Scatter(
                x=frame[x],
                y=frame[y],
                mode="lines+markers",
                line={"color": COLORS["accent"], "width": 3},
                marker={"size": 7, "color": COLORS["accent_alt"]},
                hovertemplate="%{x}: %{y}<extra></extra>",
            )
        ]
    )
    return apply_chart_theme(figure)


def build_grouped_bar(
    frame,
    metric_col: str,
    left_col: str,
    right_col: str,
    *,
    left_color: str = COLORS["accent"],
    right_color: str = COLORS["accent_alt"],
) -> go.Figure:
    figure = go.Figure()
    figure.add_bar(
        y=frame[metric_col],
        x=frame[left_col],
        name="Equipo",
        orientation="h",
        marker_color=left_color,
    )
    figure.add_bar(
        y=frame[metric_col],
        x=frame[right_col],
        name="Liga",
        orientation="h",
        marker_color=right_color,
    )
    figure.update_layout(barmode="group")
    return apply_chart_theme(figure)


def build_percentile_figure(frame) -> go.Figure:
    figure = go.Figure(
        data=[
            go.Bar(
                y=frame["Metric"],
                x=frame["percentile"],
                orientation="h",
                marker_color=COLORS["accent"],
                text=frame["value"],
                textposition="outside",
                hovertemplate="%{y}: P% %{x}<extra></extra>",
            )
        ]
    )
    figure.update_xaxes(range=[0, 100], ticksuffix="%")
    return apply_chart_theme(figure)
