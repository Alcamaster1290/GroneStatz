
# Directorio de parquets (Windows):
#   gronestats\data\Liga 1 Peru\2025\parquets
#
# Requisitos:
#   pip install streamlit pandas pyarrow

from __future__ import annotations

from pathlib import Path
import importlib.util
import sys
import pandas as pd
import streamlit as st

try:
    from gronestats.processing.st_create_parquets import (
        calculate_price,
        _round_float_columns,
        _scale_prices_to_budget,
        _stretch_goalkeeper_prices,
    )
except ModuleNotFoundError:
    BASE_DIR = Path(__file__).resolve().parents[2]
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    try:
        from gronestats.processing.st_create_parquets import (
            calculate_price,
            _round_float_columns,
            _scale_prices_to_budget,
            _stretch_goalkeeper_prices,
        )
    except ModuleNotFoundError:
        module_path = Path(__file__).resolve().parent / "st_create_parquets.py"
        spec = importlib.util.spec_from_file_location("st_create_parquets", module_path)
        if spec is None or spec.loader is None:
            raise
        module = importlib.util.module_from_spec(spec)
        sys.modules["st_create_parquets"] = module
        spec.loader.exec_module(module)
        calculate_price = module.calculate_price
        _round_float_columns = module._round_float_columns
        _scale_prices_to_budget = module._scale_prices_to_budget
        _stretch_goalkeeper_prices = module._stretch_goalkeeper_prices

# -------------------------
# Config
# -------------------------
st.set_page_config(page_title="Parquets Updater - Fantasy", layout="wide")

BASE_DIR = Path(__file__).resolve().parents[2]  # .../GroneStatz
PARQUETS_DIR = BASE_DIR / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets" / "normalized"

FILES = {
    "players_fantasy": PARQUETS_DIR / "players_fantasy.parquet",
    "players": PARQUETS_DIR / "players.parquet",
    "teams": PARQUETS_DIR / "teams.parquet",
    "player_totals": PARQUETS_DIR / "player_totals.parquet",
    "player_match": PARQUETS_DIR / "player_match.parquet",
    "player_transfer": PARQUETS_DIR / "player_transfer.parquet",
}

POS_ORDER = ["G", "D", "M", "F"]


# -------------------------
# Helpers
# -------------------------
@st.cache_data(show_spinner=False)
def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def normalize_team_id(x):
    if pd.isna(x) or x == "":
        return pd.NA
    try:
        return int(x)
    except Exception:
        return pd.NA

def normalize_pos(x):
    if pd.isna(x) or x == "":
        return pd.NA
    x = str(x).strip().upper()
    return x if x in POS_ORDER else pd.NA

def safe_cols(df: pd.DataFrame, wanted: list[str]) -> list[str]:
    return [c for c in wanted if c in df.columns]

def coalesce_columns(df: pd.DataFrame, target: str, candidates: list[str]) -> pd.DataFrame:
    existing = [c for c in candidates if c in df.columns]
    if not existing:
        return df
    work = df.copy()
    if target not in work.columns:
        work[target] = pd.NA
    for c in existing:
        if c == target:
            continue
        work[target] = work[target].combine_first(work[c])
    drop_cols = [c for c in existing if c != target]
    return work.drop(columns=drop_cols, errors="ignore")

def normalize_player_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "name", ["name", "NAME"])
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work = coalesce_columns(work, "goals", ["goals", "GOALS", "goal"])
    work = coalesce_columns(work, "assists", ["assists", "ASSISTS", "assist", "GOALASSIST", "goalassist", "goal_assist"])
    work = coalesce_columns(work, "saves", ["saves", "SAVES", "save"])
    work = coalesce_columns(work, "fouls", ["fouls", "FOULS", "foul"])
    work = coalesce_columns(work, "minutesplayed", ["minutesplayed", "MINUTESPLAYED", "minutes_played", "minutes"])
    work = coalesce_columns(work, "matches_played", ["matches_played", "MATCHES_PLAYED", "matchesplayed"])
    work = coalesce_columns(work, "penaltywon", ["penaltywon", "PENALTYWON", "penalty_won"])
    work = coalesce_columns(work, "penaltysave", ["penaltysave", "PENALTYSAVE", "penalty_save"])
    work = coalesce_columns(work, "penaltyconceded", ["penaltyconceded", "PENALTYCONCEDED", "penalty_conceded"])
    work = coalesce_columns(work, "rating", ["rating", "RATING"])
    for col in ["player_id", "match_id", "team_id"]:
        if col in work.columns:
            work[col] = pd.to_numeric(work[col], errors="coerce").astype("Int64")
    if "position" in work.columns:
        work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    return work


def normalize_teams(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    if "team_id" in work.columns:
        work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    if "short_name" not in work.columns and "shortName" in work.columns:
        work["short_name"] = work["shortName"]
    if "full_name" not in work.columns and "fullName" in work.columns:
        work["full_name"] = work["fullName"]
    work["team_name"] = work.get("short_name", pd.Series(index=work.index, dtype="object")).combine_first(
        work.get("full_name", pd.Series(index=work.index, dtype="object"))
    )
    return work


def build_view(players_fantasy: pd.DataFrame, players: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    view = normalize_player_columns(players_fantasy)
    players = normalize_player_columns(players)
    teams = normalize_teams(teams)
    for col in ["name", "position", "team_id"]:
        if col not in view.columns:
            view[col] = pd.NA
    if not players.empty and "player_id" in players.columns:
        cols = [c for c in ["player_id", "name", "position", "team_id"] if c in players.columns]
        view = view.merge(players[cols], on="player_id", how="left", suffixes=("", "_players"))
        for col in ["name", "position", "team_id"]:
            alt = f"{col}_players"
            if alt in view.columns:
                view[col] = view[alt].combine_first(view[col])
        view = view.drop(columns=[c for c in view.columns if c.endswith("_players")], errors="ignore")
    view["position_effective"] = view.get("position", pd.NA).astype(str).str.upper().replace({"NAN": pd.NA})
    view["team_id_effective"] = pd.to_numeric(view.get("team_id"), errors="coerce").astype("Int64")
    if not teams.empty and "team_id" in teams.columns:
        team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
        view = view.merge(
            team_lookup,
            left_on="team_id_effective",
            right_on="team_id",
            how="left",
            suffixes=("", "_team"),
        )
        view["team_name_effective"] = view["team_name"]
    else:
        view["team_name_effective"] = pd.NA
    return view


def _safe_per_match(series: pd.Series, matches: pd.Series) -> pd.Series:
    safe_matches = matches.where(matches > 0)
    return series.div(safe_matches).fillna(0)


def recalc_players_fantasy(players_fantasy: pd.DataFrame, players: pd.DataFrame) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy)
    players = normalize_player_columns(players)
    for col in ["name", "position", "team_id"]:
        if col not in fantasy.columns:
            fantasy[col] = pd.NA
    if not players.empty and "player_id" in players.columns:
        cols = [c for c in ["player_id", "name", "position", "team_id"] if c in players.columns]
        fantasy = fantasy.merge(players[cols], on="player_id", how="left", suffixes=("", "_players"))
        for col in ["name", "position", "team_id"]:
            alt = f"{col}_players"
            if alt in fantasy.columns:
                fantasy[col] = fantasy[alt].combine_first(fantasy[col])
        fantasy = fantasy.drop(columns=[c for c in fantasy.columns if c.endswith("_players")], errors="ignore")
    for col in [
        "minutesplayed",
        "matches_played",
        "goals",
        "assists",
        "saves",
        "fouls",
        "penaltywon",
        "penaltysave",
        "penaltyconceded",
    ]:
        if col not in fantasy.columns:
            fantasy[col] = 0
        fantasy[col] = pd.to_numeric(fantasy[col], errors="coerce").fillna(0)
    for src, target in [
        ("goals", "goals_pm"),
        ("assists", "assists_pm"),
        ("saves", "saves_pm"),
        ("fouls", "fouls_pm"),
        ("penaltywon", "penaltywon_pm"),
        ("penaltysave", "penaltysave_pm"),
        ("penaltyconceded", "penaltyconceded_pm"),
    ]:
        fantasy[target] = _safe_per_match(fantasy[src], fantasy["matches_played"])
    fantasy["price_raw"] = fantasy.apply(calculate_price, axis=1)
    scaled_prices = _scale_prices_to_budget(fantasy["price_raw"])
    scaled_prices = _stretch_goalkeeper_prices(scaled_prices, fantasy.get("position"))
    fantasy["price"] = scaled_prices.round(1)
    fantasy = fantasy.drop(columns=["price_raw"], errors="ignore")
    fantasy = _round_float_columns(fantasy, decimals=2)
    fantasy["price"] = fantasy["price"].round(1)
    return fantasy


def update_players_row(
    players_df: pd.DataFrame,
    player_id: int,
    position: str | None,
    team_id: int | None,
    name: str | None,
) -> pd.DataFrame:
    work = normalize_player_columns(players_df)
    for col in ["player_id", "name", "position", "team_id"]:
        if col not in work.columns:
            work[col] = pd.NA
    mask = work["player_id"] == player_id
    if mask.any():
        if position is not None and position is not pd.NA:
            work.loc[mask, "position"] = position
        if team_id is not None and team_id is not pd.NA:
            work.loc[mask, "team_id"] = team_id
        if name:
            work.loc[mask, "name"] = work.loc[mask, "name"].fillna(name)
    else:
        new_row = {
            "player_id": player_id,
            "name": name,
            "position": position,
            "team_id": team_id,
        }
        work = pd.concat([work, pd.DataFrame([new_row])], ignore_index=True)
    work["player_id"] = pd.to_numeric(work["player_id"], errors="coerce").astype("Int64")
    if "team_id" in work.columns:
        work["team_id"] = pd.to_numeric(work["team_id"], errors="coerce").astype("Int64")
    if "position" in work.columns:
        work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    return work


def save_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def remove_player_rows(
    players_fantasy_df: pd.DataFrame,
    player_id: int,
) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy_df)
    return fantasy[fantasy["player_id"] != player_id].copy()


# -------------------------
# Load
# -------------------------
missing_req = [k for k in ["players_fantasy", "teams"] if not FILES[k].exists()]
if missing_req:
    st.error(
        "Faltan archivos requeridos:\n- "
        + "\n- ".join(str(FILES[k]) for k in missing_req)
        + f"\n\nVerifica la ruta: {PARQUETS_DIR}"
    )
    st.stop()

players_fantasy = normalize_player_columns(read_parquet(FILES["players_fantasy"]))
players = normalize_player_columns(read_parquet(FILES["players"]))
teams = normalize_teams(read_parquet(FILES["teams"]))
totals = normalize_player_columns(read_parquet(FILES["player_totals"]))
pmatch = normalize_player_columns(read_parquet(FILES["player_match"]))
ptr = normalize_player_columns(read_parquet(FILES["player_transfer"]))
view = build_view(players_fantasy, players, teams)

# -------------------------
# UI
# -------------------------
st.title("Fantasy - Actualizador de jugadores")
st.caption("Usa filas de player_match para actualizar posicion y team_id.")

c0, c1, c2 = st.columns([2, 2, 2])
with c0:
    q = st.text_input("Buscar jugador", placeholder="Nombre...")
with c1:
    pos_filter = st.multiselect("Posicion", POS_ORDER, default=POS_ORDER)
with c2:
    team_names = sorted(view["team_name_effective"].dropna().unique().tolist()) if "team_name_effective" in view.columns else []
    team_filter = st.multiselect("Equipo", team_names, default=team_names)

filtered = view.copy()
if q:
    filtered = filtered[filtered["name"].astype(str).str.contains(q, case=False, na=False)]
if "position_effective" in filtered.columns:
    filtered = filtered[filtered["position_effective"].isin(pos_filter)]
if "team_name_effective" in filtered.columns and team_filter:
    filtered = filtered[filtered["team_name_effective"].isin(team_filter)]

st.subheader("Distribucion por posicion")
if "position_effective" in filtered.columns:
    dist = (
        filtered["position_effective"]
        .value_counts(dropna=False)
        .reindex(POS_ORDER)
        .fillna(0)
        .astype(int)
        .rename_axis("position")
        .reset_index(name="count")
    )
    st.dataframe(dist, use_container_width=True, hide_index=True)

st.subheader("Vista de jugadores")
st.caption(f"Jugadores filtrados: {len(filtered)}")
cols_show = safe_cols(
    filtered,
    [
        "player_id",
        "name",
        "position_effective",
        "team_name_effective",
        "team_id_effective",
        "price",
        "minutesplayed",
        "matches_played",
        "goals",
        "assists",
        "saves",
        "fouls",
    ],
)
players_table = filtered[cols_show]
if "price" in players_table.columns:
    players_table = players_table.sort_values("price", ascending=False)
st.dataframe(players_table, use_container_width=True)

# -------------------------
# Detalle por jugador
# -------------------------
st.divider()
st.subheader("Detalle por jugador")

player_ids = filtered["player_id"].dropna().astype(int).unique().tolist()
if not player_ids:
    st.info("No hay jugadores con los filtros actuales.")
    st.stop()

sel = st.selectbox("player_id", options=player_ids)

row = view[view["player_id"] == sel].head(1)
if row.empty:
    st.warning("No encontrado.")
    st.stop()

r = row.iloc[0]
d1, d2, d3, d4 = st.columns(4)
d1.metric("Jugador", str(r.get("name", "")))
d2.metric("Posicion", str(r.get("position_effective", "")))
d3.metric("Equipo (id)", str(r.get("team_id_effective", "")))
d4.metric("Precio", str(r.get("price", "")))

st.subheader("Eliminar jugador del fantasy")
delete_from_fantasy = st.checkbox("Eliminar este jugador de players_fantasy.parquet")

if delete_from_fantasy:
    if st.button("Eliminar jugador", type="primary"):
        updated_fantasy = remove_player_rows(
            players_fantasy,
            sel,
        )
        save_parquet(updated_fantasy, FILES["players_fantasy"])
        st.success("Jugador eliminado del fantasy.")
        st.cache_data.clear()
        st.rerun()

st.subheader("Transferencia manual de equipo")
current_pos = normalize_pos(r.get("position_effective"))
name_value = str(r.get("name", "")).strip()
team_options = []
team_label_by_id: dict[int, str] = {}
if not teams.empty and "team_id" in teams.columns:
    team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
    for _, row_team in team_lookup.iterrows():
        team_id_val = row_team.get("team_id")
        if pd.isna(team_id_val):
            continue
        team_id_int = int(team_id_val)
        team_name = str(row_team.get("team_name", "")).strip() or "Equipo"
        team_options.append(team_id_int)
        team_label_by_id[team_id_int] = f"{team_name} ({team_id_int})"
team_options = sorted(set(team_options))

if team_options:
    selected_team_id = st.selectbox(
        "Nuevo equipo (lista)",
        options=team_options,
        format_func=lambda tid: team_label_by_id.get(tid, str(tid)),
    )
    manual_team_id = st.number_input("O ingresar team_id manual", min_value=0, step=1, value=0)
    use_manual_team = st.checkbox("Usar team_id manual", value=False)
    proposed_team_id = manual_team_id if use_manual_team else selected_team_id
else:
    proposed_team_id = st.number_input("Nuevo team_id", min_value=0, step=1, value=0)

if st.button("Aplicar transferencia de equipo", type="primary"):
    new_team_id = normalize_team_id(proposed_team_id)
    if pd.isna(new_team_id) or int(new_team_id) <= 0:
        st.warning("team_id invalido.")
    else:
        updated_players = update_players_row(
            players,
            sel,
            current_pos,
            new_team_id,
            name_value if name_value else None,
        )
        save_parquet(updated_players, FILES["players"])
        updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
        save_parquet(updated_fantasy, FILES["players_fantasy"])
        st.success("Equipo actualizado y precios recalculados.")
        st.cache_data.clear()
        st.rerun()

tab1, tab2, tab3 = st.tabs(["player_totals", "player_match", "player_transfer"])

with tab1:
    if totals.empty:
        st.info("player_totals.parquet no existe o esta vacio.")
    elif "player_id" in totals.columns:
        st.dataframe(totals[totals["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_totals.parquet no tiene columna player_id.")

with tab2:
    if pmatch.empty:
        st.info("player_match.parquet no existe o esta vacio.")
    elif "player_id" in pmatch.columns:
        pmatch_player = pmatch[pmatch["player_id"] == sel].copy()
        if pmatch_player.empty:
            st.info("Sin partidos para este jugador.")
        else:
            cols_match = [
                c
                for c in [
                    "match_id",
                    "team_id",
                    "position",
                    "minutesplayed",
                    "goals",
                    "assists",
                    "saves",
                    "rating",
                ]
                if c in pmatch_player.columns
            ]
            st.dataframe(pmatch_player[cols_match], use_container_width=True)

            pmatch_player = pmatch_player.reset_index(drop=True)
            labels = []
            for idx, row_m in pmatch_player.iterrows():
                label = (
                    f"{idx + 1} | match {row_m.get('match_id', '')} | "
                    f"pos {row_m.get('position', '')} | team {row_m.get('team_id', '')}"
                )
                labels.append(label)

            selected_idx = st.selectbox(
                "Fila para actualizar jugador",
                options=list(range(len(labels))),
                format_func=lambda i: labels[i],
            )
            selected_row = pmatch_player.iloc[selected_idx]
            new_pos = normalize_pos(selected_row.get("position"))
            new_team = normalize_team_id(selected_row.get("team_id"))
            st.caption(f"Seleccion: position={new_pos} team_id={new_team}")

            if st.button("Actualizar jugador con esta fila", type="primary"):
                name_value = str(r.get("name", "")).strip()
                updated_players = update_players_row(
                    players,
                    sel,
                    new_pos,
                    new_team,
                    name_value if name_value else None,
                )
                save_parquet(updated_players, FILES["players"])
                updated_fantasy = recalc_players_fantasy(players_fantasy, updated_players)
                save_parquet(updated_fantasy, FILES["players_fantasy"])
                st.success("Parquets actualizados.")
                st.cache_data.clear()
                st.rerun()
    else:
        st.warning("player_match.parquet no tiene columna player_id.")

with tab3:
    if ptr.empty:
        st.info("player_transfer.parquet no existe o esta vacio.")
    elif "player_id" in ptr.columns:
        st.dataframe(ptr[ptr["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_transfer.parquet no tiene columna player_id.")
