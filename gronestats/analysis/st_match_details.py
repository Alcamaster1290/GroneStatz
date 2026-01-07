import pandas as pd
import streamlit as st
from pathlib import Path

MASTER_FILE = Path("gronestats/data/master_data/Partidos_Liga 1 Peru_2025_limpio.xlsx")
DETAILS_DIR = Path("gronestats/data/Liga 1 Peru/2025")


@st.cache_data
def load_master() -> pd.DataFrame:
    if not MASTER_FILE.exists():
        st.error(f"No se encontró el archivo maestro: {MASTER_FILE}")
        return pd.DataFrame()
    df = pd.read_excel(MASTER_FILE)
    df["match_id"] = df["match_id"].astype(str)
    df["home_id"] = df["home_id"].astype(str)
    df["away_id"] = df["away_id"].astype(str)
    return df


def load_details(match_id: str) -> dict[str, pd.DataFrame]:
    file_path = DETAILS_DIR / f"Sofascore_{match_id}.xlsx"
    if not file_path.exists():
        st.error(f"No existe el archivo de detalles: {file_path}")
        return {}
    try:
        return pd.read_excel(file_path, sheet_name=None)
    except Exception as e:
        st.error(f"No se pudo leer {file_path}: {e}")
        return {}


def _first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _coalesce_columns(df: pd.DataFrame, target: str, aliases: list[str]) -> pd.DataFrame:
    work = df.copy()
    cols = [c for c in aliases if c in work.columns]
    if not cols:
        return work
    if target not in work.columns:
        work[target] = None
    for c in cols:
        mask = work[target].isna() & work[c].notna()
        work.loc[mask, target] = work.loc[mask, c]
    drop_cols = [c for c in cols if c != target]
    work = work.drop(columns=drop_cols, errors="ignore")
    return work


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
        # timestamps en segundos para las filas numéricas
        dt_num = pd.to_datetime(dob_num, unit="s", errors="coerce")
        # para las no numéricas, intenta parseo normal
        mask_num = dob_num.notna()
        dt = dt_num.copy()
        dt.loc[~mask_num] = pd.to_datetime(dob_series[~mask_num], errors="coerce")
        # formato dd/mm/aaaa para visualización consistente
        work["dateOfBirth"] = dt.dt.strftime("%d/%m/%Y")
        # edad a enero 2026
        ref = pd.Timestamp("2026-01-01")
        age_years = (ref - dt).dt.days / 365.25
        work["age_jan_2026"] = age_years.round(1)
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
def load_player_rows() -> pd.DataFrame:
    all_stats = load_all_player_stats()
    if all_stats.empty:
        return pd.DataFrame()
    cols_required = [c for c in ["NAME", "PLAYER_ID", "POSITION", "TEAM_ID", "DATEOFBIRTH"] if c in all_stats.columns]
    if not cols_required:
        return pd.DataFrame()
    cols_keep = cols_required + ([c for c in ["AGE_JAN_2026"] if c in all_stats.columns])
    df = all_stats[cols_keep].copy()
    df = df.dropna(subset=cols_required).drop_duplicates()
    df.columns = [c.lower() for c in df.columns]
    return df


def main():
    st.title("Navegador de partidos - Liga 1 2025")
    st.caption("Fuente: Partidos_Liga 1 Peru_2025_limpio.xlsx + archivos Sofascore_<id>.xlsx")

    df_master = load_master()
    if df_master.empty:
        st.stop()

    tab_partido, tab_jugadores = st.tabs(["Partido", "Jugadores"])

    with tab_partido:
        equipos = pd.unique(pd.concat([df_master["home"], df_master["away"]], ignore_index=True).dropna()).tolist()
        equipos = sorted(equipos)

        match_ids = df_master["match_id"].astype(str).tolist()
        match_id = st.text_input("match_id", value=match_ids[0] if match_ids else "")
        eq_sel = st.selectbox("Filtrar por equipo (home o away)", options=["(todos)"] + equipos, index=0)

        if eq_sel != "(todos)":
            df_filtrado = df_master[(df_master["home"] == eq_sel) | (df_master["away"] == eq_sel)]
            st.write(f"Partidos del equipo seleccionado ({eq_sel}):")
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

    with tab_jugadores:
        st.subheader("Jugadores - detalles 2025")
        players_df = load_player_rows()
        st.write(f"Total jugadores : {len(players_df)}")
        if not players_df.empty:
            st.dataframe(players_df, use_container_width=True)

            names = sorted(players_df["name"].astype(str).unique().tolist())
            sel_name = st.selectbox("Selecciona jugador para ver sus apariciones", options=["(elige)"] + names, index=0)
            if sel_name != "(elige)":
                ids_sel = players_df.loc[players_df["name"] == sel_name, "player_id"].dropna().astype(str).unique().tolist()
                all_stats = load_all_player_stats()
                if not all_stats.empty:
                    df_hit = all_stats[
                        all_stats["PLAYER_ID"].astype(str).isin(ids_sel) | all_stats["NAME"].astype(str).isin([sel_name])
                    ]
                else:
                    df_hit = pd.DataFrame()

                if not df_hit.empty:
                    st.subheader(f"Apariciones de {sel_name}")
                    merged = df_hit.drop_duplicates()

                    master_map = df_master[
                        ["match_id", "resultado_final", "home", "away", "home_id", "away_id"]
                    ].copy()
                    master_map["home_id"] = master_map["home_id"].astype(str)
                    master_map["away_id"] = master_map["away_id"].astype(str)

                    if "MATCH_ID" in merged.columns:
                        merged["MATCH_ID"] = merged["MATCH_ID"].astype(str)
                        merged["RESULTADO_FINAL"] = merged["MATCH_ID"].map(
                            dict(zip(master_map["match_id"], master_map["resultado_final"]))
                        )

                        if "TEAM_ID" in merged.columns:
                            team_map = dict(
                                zip(
                                    master_map["match_id"],
                                    zip(
                                        master_map["home_id"], master_map["away_id"],
                                        master_map["home"], master_map["away"]
                                    )
                                )
                            )

                            def _opponent(mid, team_id):
                                pair = team_map.get(mid)
                                if not pair:
                                    return None
                                home_id, away_id, home_name, away_name = pair
                                tid = str(team_id)
                                if tid == home_id:
                                    return away_name
                                if tid == away_id:
                                    return home_name
                                return None

                            merged["OPPONENT_TEAM"] = [
                                _opponent(mid, tid) for mid, tid in zip(merged["MATCH_ID"], merged["TEAM_ID"])
                            ]

                    merged = merged.reindex(sorted(merged.columns), axis=1)
                    st.dataframe(merged, use_container_width=True)

                    if "MATCH_ID" in merged.columns:
                        ids_hit = merged["MATCH_ID"].dropna().astype(str).unique().tolist()
                        master_hit = df_master[df_master["match_id"].isin(ids_hit)]
                        if not master_hit.empty:
                            st.subheader("Partidos en maestro para este jugador")
                            st.dataframe(master_hit, use_container_width=True)

                    if not merged.empty:
                        num_cols = merged.select_dtypes(include=["number"]).columns
                        resumen_rows = [{"metric": "matches_played", "value": len(merged)}]
                        for c in num_cols:
                            resumen_rows.append({"metric": f"total_{c}", "value": merged[c].sum()})
                            resumen_rows.append({"metric": f"avg_{c}", "value": merged[c].mean()})
                        resumen_df = pd.DataFrame(resumen_rows)
                        st.subheader("Totales y promedios del jugador")
                        st.dataframe(resumen_df, use_container_width=True)
                else:
                    st.info("No se encontraron apariciones para ese jugador en los archivos de detalles.")
        else:
            st.info("No se encontraron archivos Sofascore_* en la carpeta de detalles o no hay hoja 'Player Stats'.")


if __name__ == "__main__":
    main()
