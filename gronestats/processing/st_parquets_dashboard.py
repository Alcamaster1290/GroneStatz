from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Parquets Dashboard - Fantasy", layout="wide")

BASE_DIR = Path(__file__).resolve().parents[2]
PARQUETS_DIR = BASE_DIR / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets" / "normalized"
PLAYERS_IMG_DIR = BASE_DIR / "gronestats" / "images" / "players"

POS_ORDER = ["G", "D", "M", "F"]


@st.cache_data(show_spinner=False)
def read_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


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


def find_player_image(player_id: int | str | None) -> Path | None:
    if player_id is None:
        return None
    try:
        player_str = str(int(player_id))
    except (TypeError, ValueError):
        player_str = str(player_id).strip()
    if not player_str:
        return None
    for ext in [".png", ".jpg", ".jpeg", ".webp"]:
        candidate = PLAYERS_IMG_DIR / f"{player_str}{ext}"
        if candidate.exists():
            return candidate
    return None


def normalize_player_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    work = df.copy()
    work = coalesce_columns(work, "player_id", ["player_id", "PLAYER_ID", "playerId", "playerid"])
    work = coalesce_columns(work, "match_id", ["match_id", "MATCH_ID", "matchId", "matchid"])
    work = coalesce_columns(work, "team_id", ["team_id", "TEAM_ID", "teamId", "teamid"])
    work = coalesce_columns(work, "name", ["name", "NAME", "player", "player_name"])
    work = coalesce_columns(work, "position", ["position", "POSITION", "pos"])
    work = coalesce_columns(work, "goals", ["goals", "GOALS", "goal"])
    work = coalesce_columns(work, "assists", ["assists", "ASSISTS", "assist", "GOALASSIST", "goalassist", "goal_assist"])
    work = coalesce_columns(work, "saves", ["saves", "SAVES", "save"])
    work = coalesce_columns(work, "fouls", ["fouls", "FOULS", "foul"])
    work = coalesce_columns(work, "minutesplayed", ["minutesplayed", "MINUTESPLAYED", "minutes_played", "minutes"])
    work = coalesce_columns(work, "matches_played", ["matches_played", "MATCHES_PLAYED", "matchesplayed", "matches"])
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


@st.cache_data(show_spinner=False)
def load_parquets() -> dict[str, pd.DataFrame]:
    return {
        "players_fantasy": read_parquet(PARQUETS_DIR / "players_fantasy.parquet"),
        "players": read_parquet(PARQUETS_DIR / "players.parquet"),
        "teams": read_parquet(PARQUETS_DIR / "teams.parquet"),
        "player_totals": read_parquet(PARQUETS_DIR / "player_totals.parquet"),
        "player_match": read_parquet(PARQUETS_DIR / "player_match.parquet"),
        "player_transfer": read_parquet(PARQUETS_DIR / "player_transfer.parquet"),
        "matches": read_parquet(PARQUETS_DIR / "matches.parquet"),
    }


@st.cache_data(show_spinner=False)
def build_fantasy_view(
    players_fantasy: pd.DataFrame,
    players: pd.DataFrame,
    teams: pd.DataFrame,
) -> pd.DataFrame:
    fantasy = normalize_player_columns(players_fantasy)
    players = normalize_player_columns(players)
    teams = normalize_teams(teams)
    for col in ["name", "position", "team_id"]:
        if col not in fantasy.columns:
            fantasy[col] = pd.NA

    if not players.empty and "player_id" in players.columns:
        cols = [c for c in ["player_id", "name", "position", "team_id", "dateofbirth", "age_jan_2026"] if c in players.columns]
        fantasy = fantasy.merge(players[cols], on="player_id", how="left", suffixes=("", "_players"))
        for col in ["name", "position", "team_id"]:
            col_alt = f"{col}_players"
            if col_alt in fantasy.columns:
                fantasy[col] = fantasy[col_alt].combine_first(fantasy[col])
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

    if "position" not in fantasy.columns:
        fantasy["position"] = pd.NA
    if "team_id" not in fantasy.columns:
        fantasy["team_id"] = pd.NA
    fantasy["position_effective"] = fantasy["position"].astype(str).str.strip().str.upper().replace({"NAN": pd.NA})
    fantasy["team_id_effective"] = pd.to_numeric(fantasy["team_id"], errors="coerce").astype("Int64")

    if not teams.empty and "team_id" in teams.columns:
        team_lookup = teams[["team_id", "team_name"]].dropna(subset=["team_id"]).drop_duplicates()
        fantasy = fantasy.merge(
            team_lookup,
            left_on="team_id_effective",
            right_on="team_id",
            how="left",
            suffixes=("", "_team"),
        )
        fantasy["team_name_effective"] = fantasy["team_name"]
    else:
        fantasy["team_name_effective"] = pd.NA

    fantasy["position"] = fantasy["position_effective"]
    return fantasy


def build_player_match_view(pmatch: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    pmatch = normalize_player_columns(pmatch)
    if pmatch.empty:
        return pmatch
    if matches.empty:
        return pmatch
    matches = matches.copy()
    if "match_id" in matches.columns:
        matches["match_id"] = pd.to_numeric(matches["match_id"], errors="coerce").astype("Int64")
    if "match_id" in pmatch.columns:
        pmatch["match_id"] = pd.to_numeric(pmatch["match_id"], errors="coerce").astype("Int64")
    match_cols = [c for c in ["match_id", "round_number", "home", "away", "home_score", "away_score", "fecha"] if c in matches.columns]
    return pmatch.merge(matches[match_cols], on="match_id", how="left")


st.title("Parquets Dashboard - Fantasy")
st.caption(f"Parquets: {PARQUETS_DIR}")

data = load_parquets()
missing = [k for k in ["players_fantasy", "teams"] if data[k].empty]
if missing:
    st.error("Faltan parquets requeridos para el dashboard.")
    st.stop()

fantasy_view = build_fantasy_view(
    data["players_fantasy"],
    data["players"],
    data["teams"],
)

avg_price = float(fantasy_view["price"].mean()) if not fantasy_view.empty else 0

m0, m1 = st.columns(2)
m0.metric("Jugadores", int(len(fantasy_view)))
m1.metric("Precio promedio", f"{avg_price:.1f}")

tabs = st.tabs(["Jugadores", "Equipos", "Jugador", "Transferencias"])

with tabs[0]:
    st.subheader("Jugadores")
    c0, c1, c2 = st.columns([2, 2, 2])
    with c0:
        q = st.text_input("Buscar", placeholder="Nombre...")
    with c1:
        pos_filter = st.multiselect("Posicion", POS_ORDER, default=POS_ORDER)
    with c2:
        team_options = sorted(fantasy_view["team_name_effective"].dropna().unique().tolist())
        team_filter = st.multiselect("Equipo", team_options, default=team_options)

    filtered = fantasy_view.copy()
    if q:
        filtered = filtered[filtered["name"].astype(str).str.contains(q, case=False, na=False)]
    if "position_effective" in filtered.columns:
        filtered = filtered[filtered["position_effective"].isin(pos_filter)]
    if team_filter and "team_name_effective" in filtered.columns:
        filtered = filtered[filtered["team_name_effective"].isin(team_filter)]

    cols_show = [
        c
        for c in [
            "player_id",
            "name",
            "position_effective",
            "team_name_effective",
            "price",
            "minutesplayed",
            "matches_played",
            "goals",
            "assists",
            "saves",
            "fouls",
            "penaltywon",
            "penaltysave",
            "penaltyconceded",
        ]
        if c in filtered.columns
    ]
    players_table = filtered[cols_show]
    if "price" in players_table.columns:
        players_table = players_table.sort_values("price", ascending=False)
    st.dataframe(players_table, use_container_width=True)

with tabs[1]:
    st.subheader("Equipo")
    if "team_id_effective" not in fantasy_view.columns:
        st.info("No hay team_id_effective para cruce por equipo.")
    else:
        team_choices = (
            fantasy_view[["team_id_effective", "team_name_effective"]]
            .dropna(subset=["team_id_effective"])
            .drop_duplicates()
            .sort_values("team_name_effective")
        )
        team_labels = [
            f"{row.team_id_effective} - {row.team_name_effective}"
            for row in team_choices.itertuples(index=False)
        ]
        if not team_labels:
            st.info("No hay equipos disponibles.")
        else:
            selected = st.selectbox("Equipo", options=team_labels)
            team_id = int(str(selected).split(" - ")[0])
            team_df = fantasy_view[fantasy_view["team_id_effective"] == team_id].copy()

            st.caption("Plantel")
            cols_team = [
                c
                for c in [
                    "player_id",
                    "name",
                    "position_effective",
                    "price",
                    "minutesplayed",
                    "matches_played",
                    "goals",
                    "assists",
                    "saves",
                ]
                if c in team_df.columns
            ]
            team_table = team_df[cols_team]
            if "price" in team_table.columns:
                team_table = team_table.sort_values("price", ascending=False)
            st.dataframe(team_table, use_container_width=True)

            st.caption("Totales del equipo")
            stats_cols = [c for c in ["minutesplayed", "matches_played", "goals", "assists", "saves", "fouls"] if c in team_df.columns]
            if stats_cols:
                totals = team_df[stats_cols].sum(numeric_only=True).to_frame("total").reset_index()
                st.dataframe(totals, use_container_width=True, hide_index=True)

            matches = data["matches"].copy()
            if not matches.empty and "home_id" in matches.columns and "away_id" in matches.columns:
                matches["home_id"] = pd.to_numeric(matches["home_id"], errors="coerce").astype("Int64")
                matches["away_id"] = pd.to_numeric(matches["away_id"], errors="coerce").astype("Int64")
                team_matches = matches[(matches["home_id"] == team_id) | (matches["away_id"] == team_id)].copy()
                if not team_matches.empty:
                    cols_match = [
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
                    st.caption("Partidos del equipo")
                    st.dataframe(team_matches[cols_match], use_container_width=True)

with tabs[2]:
    st.subheader("Jugador")
    player_labels = []
    if "player_id" in fantasy_view.columns:
        player_labels = (
            fantasy_view[["player_id", "name"]]
            .dropna(subset=["player_id"])
            .drop_duplicates()
            .assign(label=lambda df: df["player_id"].astype(str) + " - " + df["name"].astype(str))
            .sort_values("label")["label"]
            .tolist()
        )

    if not player_labels:
        st.info("No hay jugadores disponibles.")
    else:
        selected_label = st.selectbox("Jugador", options=player_labels)
        selected_id = int(selected_label.split(" - ")[0])
        row = fantasy_view[fantasy_view["player_id"] == selected_id].head(1)
        if row.empty:
            st.warning("Jugador no encontrado.")
        else:
            r = row.iloc[0]
            img_col, stats_col = st.columns([1, 3])
            with img_col:
                img_path = find_player_image(selected_id)
                if img_path:
                    st.image(str(img_path), width=140)
                else:
                    st.caption("Sin foto disponible.")
            with stats_col:
                d1, d2, d3, d4 = st.columns((3,1,2,1))
                d1.metric("Jugador", str(r.get("name", "")))
                d2.metric("Posicion", str(r.get("position_effective", "")))
                d3.metric("Equipo", str(r.get("team_name_effective", "")))
                d4.metric("Precio", str(r.get("price", "")))

            st.caption("Totales")
            totals = normalize_player_columns(data["player_totals"])
            if not totals.empty and "player_id" in totals.columns:
                st.dataframe(totals[totals["player_id"] == selected_id], use_container_width=True)
            else:
                st.info("player_totals vacio o sin player_id.")

            st.caption("Partidos")
            pmatch_view = build_player_match_view(data["player_match"], data["matches"])
            if not pmatch_view.empty and "player_id" in pmatch_view.columns:
                cols_pmatch = [
                    c
                    for c in [
                        "match_id",
                        "round_number",
                        "home",
                        "away",
                        "minutesplayed",
                        "goals",
                        "assists",
                        "saves",
                        "rating",
                        "fecha",
                    ]
                    if c in pmatch_view.columns
                ]
                st.dataframe(
                    pmatch_view[pmatch_view["player_id"] == selected_id][cols_pmatch],
                    use_container_width=True,
                )
            else:
                st.info("player_match vacio o sin player_id.")

with tabs[3]:
    st.subheader("Transferencias")
    transfers = normalize_player_columns(data["player_transfer"])
    if transfers.empty:
        st.info("player_transfer vacio.")
    else:
        cols_transfer = [c for c in ["player_id", "team_id", "name", "position"] if c in transfers.columns]
        st.dataframe(transfers[cols_transfer], use_container_width=True)
