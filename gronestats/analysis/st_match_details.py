from pathlib import Path

import pandas as pd
import streamlit as st

MASTER_FILE = Path("gronestats/data/master_data/Partidos_Liga 1 Peru_2025_limpio.xlsx")
DETAILS_DIR = Path("gronestats/data/Liga 1 Peru/2025")
ALKAGRONE_FILE = Path("gronestats/data/master_data/BD Alkagrone 2025.xlsx")


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


@st.cache_data
def load_alkagrone_teams() -> pd.DataFrame:
    if not ALKAGRONE_FILE.exists():
        st.error(f"No se encontro el archivo BD Alkagrone: {ALKAGRONE_FILE}")
        return pd.DataFrame()
    try:
        return pd.read_excel(ALKAGRONE_FILE, sheet_name="Equipos")
    except Exception as exc:
        st.error(f"No se pudo leer {ALKAGRONE_FILE} (Equipos): {exc}")
        return pd.DataFrame()


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


def _normalize_id_series(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    as_int = numeric.dropna().astype("Int64").astype(str)
    result = series.astype(str).str.strip()
    result.loc[numeric.notna()] = as_int
    result = result.str.replace(".0", "", regex=False)
    return result


def _normalize_match_datetime(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        dt = pd.to_datetime(series, errors="coerce", utc=True)
    else:
        max_val = numeric.abs().max()
        unit = "ms" if max_val >= 1_000_000_000_000 else "s"
        dt_num = pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
        dt_txt = pd.to_datetime(series, errors="coerce", utc=True)
        dt = dt_num.copy()
        dt.loc[numeric.isna()] = dt_txt[numeric.isna()]
    try:
        dt = dt.dt.tz_convert("America/Lima")
    except Exception:
        dt = dt.dt.tz_convert("Etc/GMT+5")
    return dt.dt.strftime("%d/%m/%Y %H:%M")


def render_schema_section(title: str, source_df: pd.DataFrame, schema_df: pd.DataFrame) -> None:
    st.subheader(title)
    st.caption("Columnas completas (fuente)")
    st.write(f"Filas: {len(source_df)}")
    st.dataframe(source_df, use_container_width=True)
    st.caption("Esquema parquet")
    st.write(f"Filas: {len(schema_df)}")
    st.dataframe(schema_df, use_container_width=True)


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
    df = df.dropna(subset=cols_required)
    if "PLAYER_ID" in df.columns:
        df = df.drop_duplicates(subset=["PLAYER_ID"])
    else:
        df = df.drop_duplicates()
    df.columns = [c.lower() for c in df.columns]
    return df


@st.cache_data
def build_matches_schema(df_master: pd.DataFrame, normalize_date: bool = True) -> pd.DataFrame:
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
    result = df_master[cols].copy()
    if normalize_date and "fecha" in result.columns:
        result["fecha"] = _normalize_match_datetime(result["fecha"])
    return result


@st.cache_data
def build_teams_schema(df_teams: pd.DataFrame) -> pd.DataFrame:
    if df_teams.empty:
        return pd.DataFrame()
    work = df_teams.copy()
    work = _coalesce_columns(work, "team_id", ["team_id", "teamId", "team id", "id", "ID_Equipo", "ID Equipo"])
    work = _coalesce_columns(
        work,
        "short_name",
        ["team_name", "team", "name", "equipo", "club", "Nombre_Corto", "Nombre corto"],
    )
    work = _coalesce_columns(work, "full_name", ["Nombre_Completo", "Nombre completo", "nombre_completo"])
    work = _coalesce_columns(
        work,
        "team_colors",
        ["team_colors", "team_color", "colors", "color", "colores", "Color"],
    )
    work = _coalesce_columns(
        work,
        "is_altitude_team",
        ["Es_Equipo_Altura", "Es Equipo Altura", "equipo_altura"],
    )
    work = _coalesce_columns(
        work,
        "competitiveness_level",
        ["Nivel_Competitividad", "Nivel Competitividad"],
    )
    work = _coalesce_columns(
        work,
        "stadium_id",
        ["ID_Estadio_Principal", "ID Estadio Principal"],
    )
    work = _coalesce_columns(
        work,
        "stadium_name_city",
        ["Nombre_Estadio / Ciudad", "Nombre Estadio / Ciudad", "Nombre_Estadio_Ciudad"],
    )
    work = _coalesce_columns(work, "province", ["Provincia_Equipo", "Provincia Equipo", "provincia"])
    work = _coalesce_columns(work, "department", ["Departamento", "departamento"])
    work = _coalesce_columns(work, "region", ["Region", "Regi\u00f3n", "region", "regi\u00f3n"])
    cols = [
        c
        for c in [
            "team_id",
            "short_name",
            "full_name",
            "team_colors",
            "is_altitude_team",
            "competitiveness_level",
            "stadium_id",
            "stadium_name_city",
            "province",
            "department",
            "region",
        ]
        if c in work.columns
    ]
    if not cols:
        return pd.DataFrame()
    return work[cols].copy()


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


@st.cache_data
def build_player_team_schema(df_player_stats: pd.DataFrame) -> pd.DataFrame:
    if df_player_stats.empty:
        return pd.DataFrame()
    cols = [c for c in ["PLAYER_ID", "TEAM_ID", "NAME", "POSITION"] if c in df_player_stats.columns]
    if not cols:
        return pd.DataFrame()
    df = df_player_stats[cols].copy()
    if "PLAYER_ID" in df.columns:
        df["PLAYER_ID"] = _normalize_id_series(df["PLAYER_ID"])
    if "TEAM_ID" in df.columns:
        df["TEAM_ID"] = _normalize_id_series(df["TEAM_ID"])
    drop_subset = [c for c in ["PLAYER_ID", "TEAM_ID"] if c in df.columns]
    if "POSITION" in df.columns:
        drop_subset.append("POSITION")
    df = df.dropna(subset=drop_subset)
    if "TEAM_ID" in df.columns:
        df = df[~df["TEAM_ID"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
    if "POSITION" in df.columns:
        df = df[~df["POSITION"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
    dedupe_cols = [c for c in ["PLAYER_ID", "TEAM_ID", "POSITION"] if c in df.columns]
    if dedupe_cols:
        return df.drop_duplicates(subset=dedupe_cols)
    return df


@st.cache_data
def build_player_transfer_schema(
    player_team_df: pd.DataFrame,
    players_df: pd.DataFrame,
    teams_df: pd.DataFrame,
) -> pd.DataFrame:
    if player_team_df.empty:
        return pd.DataFrame()
    work = player_team_df.copy()
    if "PLAYER_ID" in work.columns:
        work["PLAYER_ID"] = _normalize_id_series(work["PLAYER_ID"])
    if "TEAM_ID" in work.columns:
        work["TEAM_ID"] = _normalize_id_series(work["TEAM_ID"])
    transfer_ids = (
        work.dropna(subset=["PLAYER_ID", "TEAM_ID"])
        .groupby("PLAYER_ID")["TEAM_ID"]
        .nunique()
    )
    transfer_ids = transfer_ids[transfer_ids > 1].index
    transfer_df = work[work["PLAYER_ID"].isin(transfer_ids)].copy()
    if not players_df.empty and "player_id" in players_df.columns:
        players_lookup = players_df.copy()
        players_lookup["player_id"] = _normalize_id_series(players_lookup["player_id"])
        transfer_df = transfer_df.merge(
            players_lookup,
            left_on="PLAYER_ID",
            right_on="player_id",
            how="left",
            suffixes=("", "_players"),
        )
    if not teams_df.empty and "team_id" in teams_df.columns:
        teams_lookup = teams_df.copy()
        teams_lookup["team_id"] = _normalize_id_series(teams_lookup["team_id"])
        transfer_df = transfer_df.merge(
            teams_lookup,
            left_on="TEAM_ID",
            right_on="team_id",
            how="left",
            suffixes=("", "_teams"),
        )
    return transfer_df


def main() -> None:
    st.title("Fantasy Liga 1 2026 - Dataframes base")
    st.caption("Visualizacion de esquemas previos a exportar a parquet.")

    df_master = load_master()
    if df_master.empty:
        st.stop()

    matches_df = build_matches_schema(df_master, normalize_date=True)  # Parquet export: matches_df
    teams_source_df = load_alkagrone_teams()
    teams_df = build_teams_schema(teams_source_df)  # Parquet export: teams_df
    player_stats_df = load_all_player_stats()
    players_df = load_player_rows()  # Parquet export: players_df
    player_match_df = build_player_match_schema(player_stats_df)  # Parquet export: player_match_df
    player_team_df = build_player_team_schema(player_stats_df)  # Parquet export: player_team_df
    player_transfer_df = build_player_transfer_schema(  # Parquet export: player_transfer_df
        player_team_df,
        players_df,
        teams_df,
    )
    team_stats_df = load_team_stats()  # Parquet export: team_stats_df

    tab_esquemas, tab_cruce, tab_partidos = st.tabs(["Esquemas", "Cruce info", "Detalle partido"])

    with tab_esquemas:
        render_schema_section("Matches", df_master, matches_df)
        render_schema_section("Teams", teams_source_df, teams_df)
        render_schema_section("Players", player_stats_df, players_df)
        render_schema_section("Player Match Stats", player_stats_df, player_match_df)
        render_schema_section("Player Team", player_stats_df, player_team_df)
        render_schema_section("Player Transfers", player_team_df, player_transfer_df)
        render_schema_section("Team Match Stats", team_stats_df, team_stats_df)

    with tab_cruce:
        st.subheader("Resumen por equipo")
        matches_cruce = build_matches_schema(df_master, normalize_date=False)
        if matches_cruce.empty or teams_df.empty:
            st.info("No hay datos suficientes para resumir equipos.")
            st.stop()

        matches_cruce = matches_cruce.copy()
        teams_cruce = teams_df.copy()
        if "home_id" in matches_cruce.columns:
            matches_cruce["home_id"] = _normalize_id_series(matches_cruce["home_id"])
        if "away_id" in matches_cruce.columns:
            matches_cruce["away_id"] = _normalize_id_series(matches_cruce["away_id"])
        if "match_id" in matches_cruce.columns:
            matches_cruce["match_id"] = _normalize_id_series(matches_cruce["match_id"])
        if "team_id" in teams_cruce.columns:
            teams_cruce["team_id"] = _normalize_id_series(teams_cruce["team_id"])

        teams_cruce["label"] = teams_cruce["team_id"]
        if "short_name" in teams_cruce.columns:
            teams_cruce["label"] = teams_cruce["team_id"] + " - " + teams_cruce["short_name"].fillna("")
        elif "full_name" in teams_cruce.columns:
            teams_cruce["label"] = teams_cruce["team_id"] + " - " + teams_cruce["full_name"].fillna("")

        options = teams_cruce.sort_values("label")["label"].dropna().tolist()
        selected_label = st.selectbox("Equipo", options=options, index=0 if options else None)

        if not selected_label:
            st.stop()

        selected_team_id = selected_label.split(" - ")[0]
        team_row = teams_cruce[teams_cruce["team_id"] == selected_team_id]
        st.caption("Ficha del equipo")
        st.dataframe(team_row, use_container_width=True)

        if "home_id" in matches_cruce.columns and "away_id" in matches_cruce.columns:
            team_matches = matches_cruce[
                (matches_cruce["home_id"] == selected_team_id) | (matches_cruce["away_id"] == selected_team_id)
            ].copy()
        else:
            team_matches = pd.DataFrame()

        st.caption("Resumen de partidos")
        st.write(f"Partidos: {len(team_matches)}")

        if not team_matches.empty:
            home_count = (team_matches["home_id"] == selected_team_id).sum()
            away_count = (team_matches["away_id"] == selected_team_id).sum()
            st.write(f"Home: {home_count} | Away: {away_count}")

            if "home_score" in team_matches.columns and "away_score" in team_matches.columns:
                home_mask = team_matches["home_id"] == selected_team_id
                away_mask = team_matches["away_id"] == selected_team_id
                goals_for = team_matches.loc[home_mask, "home_score"].sum() + team_matches.loc[away_mask, "away_score"].sum()
                goals_against = team_matches.loc[home_mask, "away_score"].sum() + team_matches.loc[away_mask, "home_score"].sum()
                st.write(f"Goles a favor: {goals_for} | Goles en contra: {goals_against}")

            cols_show = [
                c
                for c in [
                    "match_id",
                    "round_number",
                    "home",
                    "away",
                    "home_score",
                    "away_score",
                    "resultado_final",
                    "fecha",
                ]
                if c in team_matches.columns
            ]
            st.dataframe(team_matches[cols_show], use_container_width=True)

        st.subheader("Resumen por jugador")
        if player_match_df.empty:
            st.info("No hay datos suficientes para resumir jugadores.")
            st.stop()

        player_matches_df = player_match_df.copy()
        if "PLAYER_ID" in player_matches_df.columns:
            player_matches_df["PLAYER_ID"] = _normalize_id_series(player_matches_df["PLAYER_ID"])
        if "MATCH_ID" in player_matches_df.columns:
            player_matches_df["MATCH_ID"] = _normalize_id_series(player_matches_df["MATCH_ID"])

        if "NAME" in player_matches_df.columns:
            player_labels_df = player_matches_df[["PLAYER_ID", "NAME"]].dropna().drop_duplicates()
            player_labels_df["label"] = player_labels_df["PLAYER_ID"] + " - " + player_labels_df["NAME"].astype(str)
        else:
            player_labels_df = player_matches_df[["PLAYER_ID"]].dropna().drop_duplicates()
            player_labels_df["label"] = player_labels_df["PLAYER_ID"]
        player_options = player_labels_df.sort_values("label")["label"].tolist()
        selected_player_label = st.selectbox("Jugador", options=player_options, index=0 if player_options else None)

        if not selected_player_label:
            st.stop()

        selected_player_id = selected_player_label.split(" - ")[0]
        player_cols = [c for c in ["PLAYER_ID", "NAME", "TEAM_ID", "POSITION"] if c in player_matches_df.columns]
        player_row = player_matches_df[player_matches_df["PLAYER_ID"] == selected_player_id][player_cols].drop_duplicates()
        if "TEAM_ID" in player_row.columns:
            player_row = player_row[~player_row["TEAM_ID"].astype(str).str.strip().str.lower().isin(["nan", "none", ""])]
        st.caption("Ficha del jugador")
        st.dataframe(player_row, use_container_width=True)

        player_rows = player_matches_df[player_matches_df["PLAYER_ID"] == selected_player_id]
        if not player_rows.empty and "MATCH_ID" in player_rows.columns:
            player_match_list = pd.merge(
                matches_cruce,
                player_rows,
                left_on="match_id",
                right_on="MATCH_ID",
                how="inner",
            )
        else:
            player_match_list = pd.DataFrame()

        st.caption("Partidos del jugador")
        st.write(f"Partidos: {len(player_match_list)}")
        if not player_match_list.empty:
            cols_player_show = [
                c
                for c in [
                    "match_id",
                    "round_number",
                    "home",
                    "away",
                    "home_score",
                    "away_score",
                    "resultado_final",
                    "fecha",
                    "MINUTESPLAYED",
                    "GOALS",
                    "GOALASSIST",
                    "YELLOWCARDS",
                    "REDCARDS",
                    "RATING",
                ]
                if c in player_match_list.columns
            ]
            st.dataframe(player_match_list[cols_player_show], use_container_width=True)

        st.subheader("Jugadores transferidos")
        if player_transfer_df.empty:
            st.info("No hay datos suficientes para detectar transferencias.")
            st.stop()

        st.caption("Jugadores con mas de un TEAM_ID en player team")
        if "PLAYER_ID" in player_transfer_df.columns:
            st.write(f"Total: {player_transfer_df['PLAYER_ID'].nunique()}")
        cols_transfer = [
            c
            for c in [
                "PLAYER_ID",
                "TEAM_ID",
                "NAME",
                "POSITION",
                "team_id",
                "short_name",
                "full_name",
            ]
            if c in player_transfer_df.columns
        ]
        st.dataframe(player_transfer_df[cols_transfer], use_container_width=True)

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
            st.warning("El match_id no esta en el maestro. Aun asi, intentare cargar los detalles.")

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
