
# Directorio de parquets (Windows):
#   gronestats\data\Liga 1 Peru\2025\parquets
#
# Requisitos:
#   pip install streamlit pandas pyarrow duckdb

from __future__ import annotations

from pathlib import Path
import pandas as pd
import numpy as np
import duckdb
import streamlit as st

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

OVERRIDES_FILE = PARQUETS_DIR / "player_overrides.parquet"  # se crea si no existe

POS_ORDER = ["G", "D", "M", "F"]


# -------------------------
# Helpers
# -------------------------
@st.cache_data(show_spinner=False)
def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)

def ensure_overrides_schema() -> pd.DataFrame:
    cols = [
        "player_id",
        "position_manual",
        "team_id_manual",
        "exclude_no_minutes",
        "transfer_out_2026",
        "notes",
    ]
    if OVERRIDES_FILE.exists():
        ov = pd.read_parquet(OVERRIDES_FILE)
        for c in cols:
            if c not in ov.columns:
                ov[c] = pd.NA
        # tipos
        ov["player_id"] = pd.to_numeric(ov["player_id"], errors="coerce").astype("Int64")
        ov["team_id_manual"] = pd.to_numeric(ov["team_id_manual"], errors="coerce").astype("Int64")
        ov["exclude_no_minutes"] = ov["exclude_no_minutes"].fillna(False).astype(bool)
        ov["transfer_out_2026"] = ov["transfer_out_2026"].fillna(False).astype(bool)
        ov["position_manual"] = ov["position_manual"].astype("object")
        ov["notes"] = ov["notes"].astype("string")
        return ov[cols].copy()

    empty = pd.DataFrame({c: pd.Series(dtype="object") for c in cols})
    empty["player_id"] = empty["player_id"].astype("Int64")
    empty["team_id_manual"] = empty["team_id_manual"].astype("Int64")
    empty["exclude_no_minutes"] = pd.Series(dtype="bool")
    empty["transfer_out_2026"] = pd.Series(dtype="bool")
    return empty[cols].copy()

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
    if "position" in work.columns:
        work["position"] = work["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    return work


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
teams = read_parquet(FILES["teams"])
totals = normalize_player_columns(read_parquet(FILES["player_totals"]))
pmatch = normalize_player_columns(read_parquet(FILES["player_match"]))
ptr = normalize_player_columns(read_parquet(FILES["player_transfer"]))
overrides = ensure_overrides_schema()

# -------------------------
# Canonical view via DuckDB
# -------------------------
con = duckdb.connect(database=":memory:")
con.register("players_fantasy", players_fantasy)
con.register("players", players)
con.register("teams", teams)
con.register("overrides", overrides)

# Ajusta este SELECT si tu schema usa nombres diferentes.
# Necesita al menos: player_id, name, position, team_id.
view = con.execute(
    """
    WITH base AS (
        SELECT
            pf.player_id,
            COALESCE(pf.name, p.name) AS name,
            pf.position,
            pf.team_id,
            pf.price,
            pf.minutesplayed,
            pf.matches_played,
            pf.goals,
            pf.assists,
            pf.saves,
            pf.goals_pm,
            pf.assists_pm,
            pf.saves_pm
        FROM players_fantasy pf
        LEFT JOIN players p USING (player_id)
    )
    SELECT
        b.*,
        COALESCE(o.position_manual, b.position) AS position_effective,
        COALESCE(o.team_id_manual, b.team_id) AS team_id_effective,
        o.position_manual,
        o.team_id_manual,
        COALESCE(o.exclude_no_minutes, FALSE) AS exclude_no_minutes,
        COALESCE(o.transfer_out_2026, FALSE) AS transfer_out_2026,
        o.notes,
        COALESCE(t.short_name, t.full_name) AS team_name_effective
    FROM base b
    LEFT JOIN overrides o USING (player_id)
    LEFT JOIN teams t ON t.team_id = COALESCE(o.team_id_manual, b.team_id)
    """
).df()

# normaliza tipos útiles
if "player_id" in view.columns:
    view["player_id"] = pd.to_numeric(view["player_id"], errors="coerce").astype("Int64")
if "team_id_effective" in view.columns:
    view["team_id_effective"] = pd.to_numeric(view["team_id_effective"], errors="coerce").astype("Int64")
if "team_id" in view.columns:
    view["team_id"] = pd.to_numeric(view["team_id"], errors="coerce").astype("Int64")
if "position_effective" in view.columns:
    view["position_effective"] = view["position_effective"].astype(str).str.upper().replace({"NAN": pd.NA})


# -------------------------
# UI
# -------------------------
st.title("Fantasy — Editor manual (posición / equipo)")

c0, c1, c2, c3 = st.columns([2, 2, 2, 2])
with c0:
    q = st.text_input("Buscar jugador", placeholder="Nombre...")
with c1:
    pos_filter = st.multiselect("Posición (effective)", POS_ORDER, default=POS_ORDER)
with c2:
    team_names = sorted(view["team_name_effective"].dropna().unique().tolist()) if "team_name_effective" in view.columns else []
    team_filter = st.multiselect("Equipo (effective)", team_names, default=team_names)
with c3:
    show_excluded = st.toggle("Mostrar excluidos", value=True)

filtered = view.copy()
if q:
    filtered = filtered[filtered["name"].astype(str).str.contains(q, case=False, na=False)]
if "position_effective" in filtered.columns:
    filtered = filtered[filtered["position_effective"].isin(pos_filter)]
if "team_name_effective" in filtered.columns and team_filter:
    filtered = filtered[filtered["team_name_effective"].isin(team_filter)]
if not show_excluded and "exclude_no_minutes" in filtered.columns:
    filtered = filtered[~filtered["exclude_no_minutes"].fillna(False)]

st.subheader("Distribución por posición (effective)")
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

st.subheader("Editor de overrides")
st.caption("Edita position_manual y team_id_manual. Guardado en player_overrides.parquet.")

cols_show = safe_cols(filtered, [
    "player_id", "name", "position", "team_name_effective", "team_id_effective",
    "price", "minutesplayed", "matches_played",
    "goals", "assists", "saves",
    "position_manual", "team_id_manual",
    "exclude_no_minutes", "transfer_out_2026",
    "notes",
])

editor_df = filtered[cols_show].copy()
if "notes" in editor_df.columns:
    editor_df["notes"] = editor_df["notes"].astype("string")

editable_cols = {"position_manual", "team_id_manual", "exclude_no_minutes", "transfer_out_2026", "notes"}
disabled = [c for c in cols_show if c not in editable_cols]

pos_options = ["", *POS_ORDER]
team_id_options = [""] + sorted(view["team_id_effective"].dropna().astype(int).unique().tolist())

col_config = {}
if "position_manual" in editor_df.columns:
    col_config["position_manual"] = st.column_config.SelectboxColumn(
        "position_manual",
        options=pos_options,
        help="Override de posición (G/D/M/F). Vacío = usar base.",
    )
if "team_id_manual" in editor_df.columns:
    col_config["team_id_manual"] = st.column_config.SelectboxColumn(
        "team_id_manual",
        options=team_id_options,
        help="Override de team_id. Vacío = usar base.",
    )
if "exclude_no_minutes" in editor_df.columns:
    col_config["exclude_no_minutes"] = st.column_config.CheckboxColumn("exclude_no_minutes")
if "transfer_out_2026" in editor_df.columns:
    col_config["transfer_out_2026"] = st.column_config.CheckboxColumn("transfer_out_2026")
if "notes" in editor_df.columns:
    col_config["notes"] = st.column_config.TextColumn("notes")

edited = st.data_editor(
    editor_df,
    use_container_width=True,
    hide_index=True,
    disabled=disabled,
    column_config=col_config,
    key="editor",
)

if st.button("Guardar cambios", type="primary"):
    keep = ["player_id", "position_manual", "team_id_manual", "exclude_no_minutes", "transfer_out_2026", "notes"]
    keep = [c for c in keep if c in edited.columns]
    ov_new = edited[keep].copy()

    ov_new["player_id"] = pd.to_numeric(ov_new["player_id"], errors="coerce").astype("Int64")

    if "team_id_manual" in ov_new.columns:
        ov_new["team_id_manual"] = ov_new["team_id_manual"].apply(normalize_team_id).astype("Int64")
    if "position_manual" in ov_new.columns:
        ov_new["position_manual"] = ov_new["position_manual"].apply(normalize_pos)

    def row_is_empty(r):
        pm = r.get("position_manual", pd.NA)
        tm = r.get("team_id_manual", pd.NA)
        ex = bool(r.get("exclude_no_minutes", False))
        tr = bool(r.get("transfer_out_2026", False))
        nt = r.get("notes", "")
        nt_empty = (pd.isna(nt) or str(nt).strip() == "")
        return (pd.isna(pm)) and (pd.isna(tm)) and (not ex) and (not tr) and nt_empty

    ov_new = ov_new[~ov_new.apply(row_is_empty, axis=1)].copy()

    ov_old = ensure_overrides_schema()
    ov_old["player_id"] = pd.to_numeric(ov_old["player_id"], errors="coerce").astype("Int64")
    ov_merged = ov_old[~ov_old["player_id"].isin(ov_new["player_id"])].copy()
    ov_merged = pd.concat([ov_merged, ov_new], ignore_index=True)

    OVERRIDES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ov_merged.to_parquet(OVERRIDES_FILE, index=False)

    st.success(f"Guardado: {OVERRIDES_FILE} ({len(ov_merged)} overrides activos)")

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
d2.metric("Pos (base → efectiva)", f"{r.get('position','')} → {r.get('position_effective','')}")
d3.metric("Equipo (id efectivo)", str(r.get("team_id_effective", "")))
d4.metric("Precio", str(r.get("price", "")))

tab1, tab2, tab3 = st.tabs(["player_totals", "player_match", "player_transfer"])

with tab1:
    if totals.empty:
        st.info("player_totals.parquet no existe o está vacío.")
    elif "player_id" in totals.columns:
        st.dataframe(totals[totals["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_totals.parquet no tiene columna player_id.")

with tab2:
    if pmatch.empty:
        st.info("player_match.parquet no existe o está vacío.")
    elif "player_id" in pmatch.columns:
        st.dataframe(pmatch[pmatch["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_match.parquet no tiene columna player_id.")

with tab3:
    if ptr.empty:
        st.info("player_transfer.parquet no existe o está vacío.")
    elif "player_id" in ptr.columns:
        st.dataframe(ptr[ptr["player_id"] == sel], use_container_width=True)
    else:
        st.warning("player_transfer.parquet no tiene columna player_id.")
