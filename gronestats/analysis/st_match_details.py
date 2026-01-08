from pathlib import Path

import pandas as pd
import streamlit as st

MASTER_FILE = Path("gronestats/data/master_data/Partidos_Liga 1 Peru_2025_limpio.xlsx")
DETAILS_DIR = Path("gronestats/data/Liga 1 Peru/2025")


@st.cache_data
def load_master() -> pd.DataFrame:
    if not MASTER_FILE.exists():
        st.error(f"No se encontró el archivo maestro: {MASTER_FILE}")
        return pd.DataFrame()
    df = pd.read_excel(MASTER_FILE)
    for col in ["match_id", "home_id", "away_id"]:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def load_details(match_id: str) -> dict[str, pd.DataFrame]:
    file_path = DETAILS_DIR / f"Sofascore_{match_id}.xlsx"
    if not file_path.exists():
        st.error(f"No existe el archivo de detalles: {file_path}")
        return {}
    try:
        return pd.read_excel(file_path, sheet_name=None)
    except Exception as exc:
        st.error(f"No se pudo leer {file_path}: {exc}")
        return {}


def _coalesce_columns(df: pd.DataFrame, target: str, aliases: list[str]) -> pd.DataFrame:
    work = df.copy()
    cols = [c for c in aliases if c in work.columns]
    if not cols:
        return work
    if target not in work.columns:
        work[target] = None
    for c in cols:
        work[target] = work[target].fillna(work[c])
    drop_cols = [c for c in cols if c != target]
    return work.drop(columns=drop_cols, errors="ignore")


def _normalize_player_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work = _coalesce_columns(work, "player_id", ["playerId", "id", "player id", "player_id", "__pid"])
    work = _coalesce_columns(work, "name", ["name", "player", "player_name", "__name"])
    work = _coalesce_columns(work, "team_id", ["teamId", "team id", "team_id"])
    work = _coalesce_columns(work, "position", ["position", "pos"])
    work = _coalesce_columns(work, "dateOfBirth", ["dateOfBirthTimestamp", "dateOfBirth", "dob", "birthTimestamp"])
    if "dateOfBirth" in work.columns:
        dob_series = work["dateOfBirth"]
        dob_num = pd.to_numeric(dob_series, errors="coerce")
        dt_num = pd.to_datetime(dob_num, unit="s", errors="coerce")
        mask_num = dob_num.notna()
        dt = dt_num.copy()
        dt.loc[~mask_num] = pd.to_datetime(dob_series[~mask_num], errors="coerce")
        work["dateOfBirth"] = dt.dt.strftime("%d/%m/%Y")
        ref = pd.Timestamp("2026-01-01")
        work["age_jan_2026"] = ((ref - dt).dt.days / 365.25).round(1)
    return work


@st.cache_data
def load_all_player_stats() -> pd.DataFrame:
    rows = []
    if not DETAILS_DIR.exists():
        return pd.DataFrame()
    for f in DETAILS_DIR.glob("Sofascore_*.xlsx"):
        try:
            df_ps = pd.read_excel(f, sheet_name="Player Stats")
        except Exception:
            continue
        if df_ps.empty:
            continue
        df_ps = _normalize_player_stats_df(df_ps)
        df_ps.columns = [c.upper() for c in df_ps.columns]
        if "MATCH_ID" not in df_ps.columns:
            df_ps["MATCH_ID"] = f.stem.replace("Sofascore_", "")
        rows.append(df_ps)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


@st.cache_data
def load_team_stats() -> pd.DataFrame:
    rows = []
    if not DETAILS_DIR.exists():
        return pd.DataFrame()
    for f in DETAILS_DIR.glob("Sofascore_*.xlsx"):
        try:
            df_team = pd.read_excel(f, sheet_name="Team Stats")
        except Exception:
            continue
        if df_team.empty:
            continue
        df_team.columns = [c.upper() for c in df_team.columns]
        if "MATCH_ID" not in df_team.columns:
            df_team["MATCH_ID"] = f.stem.replace("Sofascore_", "")
        rows.append(df_team)
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)


@st.cache_data
def load_player_rows() -> pd.DataFrame:
    all_stats = load_all_player_stats()
    if all_stats.empty:
        return pd.DataFrame()
    cols_required = [c for c in ["NAME", "PLAYER_ID", "POSITION", "TEAM_ID", "DATEOFBIRTH"] if c in all_stats.columns]
    if not cols_required:
        return pd.DataFrame()
    cols_keep = cols_required + [c for c in ["AGE_JAN_2026"] if c in all_stats.columns]
    df = all_stats[cols_keep].copy()
    df = df.dropna(subset=cols_required).drop_duplicates()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data
def build_matches_schema(df_master: pd.DataFrame) -> pd.DataFrame:
    if df_master.empty:
        return pd.DataFrame()
    cols = [
        "match_id",
        "round_number",
        "season",
        "home_id",
        "away_id",
        "home",
        "away",
        "home_score",
        "away_score",
        "resultado_final",
        "fecha",
        "estadio",
        "ciudad",
        "arbitro",
    ]
    cols = [c for c in cols if c in df_master.columns]
    return df_master[cols].copy()


@st.cache_data
def build_teams_schema(df_master: pd.DataFrame) -> pd.DataFrame:
    if df_master.empty:
        return pd.DataFrame()
    team_cols = ["home_id", "home", "home_team_colors", "away_id", "away", "away_team_colors"]
    if not set(team_cols).intersection(df_master.columns):
        return pd.DataFrame()
    home = df_master[["home_id", "home", "home_team_colors"]].rename(
        columns={"home_id": "team_id", "home": "team_name", "home_team_colors": "team_colors"}
    )
    away = df_master[["away_id", "away", "away_team_colors"]].rename(
        columns={"away_id": "team_id", "away": "team_name", "away_team_colors": "team_colors"}
    )
    return pd.concat([home, away], ignore_index=True).dropna().drop_duplicates()


@st.cache_data
def build_player_match_schema(df_player_stats: pd.DataFrame) -> pd.DataFrame:
    if df_player_stats.empty:
        return pd.DataFrame()
    cols = [
        "MATCH_ID",
        "PLAYER_ID",
        "NAME",
        "TEAM_ID",
        "POSITION",
        "MINUTESPLAYED",
        "GOALS",
        "GOALASSIST",
        "YELLOWCARDS",
        "REDCARDS",
        "SAVES",
        "RATING",
    ]
    cols = [c for c in cols if c in df_player_stats.columns]
    return df_player_stats[cols].copy()


def main() -> None:
    st.title("Fantasy Liga 1 2026 - Dataframes base")
    st.caption("Visualización de esquemas previos a exportar a parquet.")

    df_master = load_master()
    if df_master.empty:
        st.stop()

    tab_esquemas, tab_partidos = st.tabs(["Esquemas", "Detalle partido"])

    with tab_esquemas:
        st.subheader("Matches")
        matches_df = build_matches_schema(df_master)
        st.write(f"Filas: {len(matches_df)}")
        st.dataframe(matches_df, use_container_width=True)

        st.subheader("Teams")
        teams_df = build_teams_schema(df_master)
        st.write(f"Filas: {len(teams_df)}")
        st.dataframe(teams_df, use_container_width=True)

        st.subheader("Players")
        players_df = load_player_rows()
        st.write(f"Filas: {len(players_df)}")
        st.dataframe(players_df, use_container_width=True)

        st.subheader("Player Match Stats")
        player_stats_df = load_all_player_stats()
        player_match_df = build_player_match_schema(player_stats_df)
        st.write(f"Filas: {len(player_match_df)}")
        st.dataframe(player_match_df, use_container_width=True)

        st.subheader("Team Match Stats")
        team_stats_df = load_team_stats()
        st.write(f"Filas: {len(team_stats_df)}")
        st.dataframe(team_stats_df, use_container_width=True)

    with tab_partidos:
        equipos = pd.unique(pd.concat([df_master["home"], df_master["away"]], ignore_index=True).dropna()).tolist()
        equipos = sorted(equipos)
        match_ids = df_master["match_id"].astype(str).tolist()
        match_id = st.text_input("match_id", value=match_ids[0] if match_ids else "")
        eq_sel = st.selectbox("Filtrar por equipo (home o away)", options=["(todos)"] + equipos, index=0)

        if eq_sel != "(todos)":
            df_filtrado = df_master[(df_master["home"] == eq_sel) | (df_master["away"] == eq_sel)]
            st.dataframe(df_filtrado, use_container_width=True)

        if match_id and match_id not in match_ids:
            st.warning("El match_id no está en el maestro. Aun así, intentaré cargar los detalles.")

        if st.button("Cargar detalles"):
            details = load_details(match_id)
            if not details:
                st.stop()
            st.subheader("Resumen maestro")
            row = df_master[df_master["match_id"].astype(str) == str(match_id)]
            if not row.empty:
                st.dataframe(row, use_container_width=True)
            st.subheader("Hojas del archivo Sofascore")
            tabs = st.tabs(list(details.keys()))
            for tab, (sheet, df) in zip(tabs, details.items()):
                with tab:
                    st.write(f"Hoja: {sheet}")
                    st.dataframe(df, use_container_width=True)


if __name__ == "__main__":
    main()
