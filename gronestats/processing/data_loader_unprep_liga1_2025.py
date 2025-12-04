import os
import glob
import zipfile
import traceback
from pathlib import Path
import pandas as pd
import ScraperFC as sfc

# Config por defecto (puedes sobreescribir LIGA/YEAR antes de correr main)
YEAR = "2025"
LIGA = "Liga 1 Peru"
MIN_FILE_KB = 15  # umbral mÍnimo aceptable para el XLSX de cada partido

# Mapa de ligas (SofaScore)
COMPS = {
    "World Cup": 16, "Euros": 1, "Gold Cup": 140, "Copa America": 133,
    "Champions League": 7, "Europa League": 679, "Europa Conference League": 17015,
    "Copa Libertadores": 384, "Copa Sudamericana": 480,
    "EPL": 17, "La Liga": 8, "Bundesliga": 35, "Serie A": 23, "Ligue 1": 34, "Turkish Super Lig": 52,
    "Argentina Liga Profesional": 155, "Argentina Copa de la Liga Profesional": 13475,
    "Liga 1 Peru": 406, "Chile Primera Division": 11653, "Venezuela Primera Division": 231,
    "Uruguay Primera Division": 278, "Ecuador LigaPro": 240, "Brasileirão Série A": 325,
    "MLS": 242, "USL Championship": 13363, "USL1": 13362, "USL2": 13546,
    "Mexico LigaMX Apertura": 11621, "LigaMX Clausura": 11620,
    "Saudi Pro League": 955,
    "Women's World Cup": 290,
}
ERROR_LOG = Path("matches_details_errors.txt")

sofascore = sfc.Sofascore()

# Rutas destino alineadas con prep_and_test_data_liga1_2025.py
DETAILS_DIR = Path(f"gronestats/data/{LIGA}/2025")
MASTER_CLEAN_PATH = Path(f"gronestats/data/master_data/Partidos_{LIGA}_{YEAR}_limpio.xlsx")

def rename_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = pd.Series(df.columns, dtype="object")
    for name in cols[cols.duplicated()].unique():
        idxs = cols[cols == name].index.tolist()
        for k, i in enumerate(idxs):
            if k:
                cols.iloc[i] = f"{name}_{k}"
    df.columns = cols
    return df

def clean_scores(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["home_score"] = pd.to_numeric(out["home_score"], errors="coerce")
    out["away_score"] = pd.to_numeric(out["away_score"], errors="coerce")
    return out.dropna(subset=["home_score", "away_score"])

def fetch_matches(liga: str, year: str) -> pd.DataFrame:
    partidos = sofascore.get_match_dicts(year=year, league=liga)
    rows = []
    for partido in partidos:
        match_id = str(partido.get("id", ""))
        home_slug = partido.get("homeTeam", {}).get("slug", "")
        away_slug = partido.get("awayTeam", {}).get("slug", "")
        custom_id = partido.get("customId", "")
        match_url = f"https://www.sofascore.com/{home_slug}-{away_slug}/{custom_id}#id:{match_id}"

        md = sofascore.get_match_dict(match_id)
        ht = md.get("homeTeam", {}) or {}
        at = md.get("awayTeam", {}) or {}
        venue_dict = md.get("venue") or ht.get("venue") or at.get("venue") or {}

        hs = md.get("homeScore", {}) or {}
        as_ = md.get("awayScore", {}) or {}

        row = {
            "match_id": match_id,
            "match_url": match_url,
            "home": partido.get("homeTeam", {}).get("name"),
            "home_id": partido.get("homeTeam", {}).get("id"),
            "home_score": partido.get("homeScore", {}).get("current"),
            "away": partido.get("awayTeam", {}).get("name"),
            "away_id": partido.get("awayTeam", {}).get("id"),
            "away_score": partido.get("awayScore", {}).get("current"),
            "home_team_colors": f"Primary: { (partido.get('homeTeam', {}).get('teamColors', {}) or {}).get('primary','') }, Secondary: { (partido.get('homeTeam', {}).get('teamColors', {}) or {}).get('secondary','') }",
            "away_team_colors": f"Primary: { (partido.get('awayTeam', {}).get('teamColors', {}) or {}).get('primary','') }, Secondary: { (partido.get('awayTeam', {}).get('teamColors', {}) or {}).get('secondary','') }",
            "tournament": partido.get("tournament", {}).get("name"),
            "round_number": partido.get("roundInfo", {}).get("round"),
            "season": partido.get("season", {}).get("name"),
            "manager_home": (ht.get("manager") or {}).get("name"),
            "manager_away": (at.get("manager") or {}).get("name"),
            "goles_1T_home": hs.get("period1"),
            "goles_2T_home": hs.get("period2"),
            "goles_1T_away": as_.get("period1"),
            "goles_2T_away": as_.get("period2"),
            "resultado_final": f"{hs.get('display')} - {as_.get('display')}" if hs.get("display") is not None and as_.get("display") is not None else None,
            "estadio": venue_dict.get("name"),
            "ciudad": (venue_dict.get("city") or {}).get("name"),
            "fecha": pd.to_datetime(md.get("startTimestamp"), unit="s", errors="coerce"),
            "arbitro": (md.get("referee") or {}).get("name"),
        }
        rows.append(row)
    return pd.DataFrame(rows).reset_index(drop=True)

def load_and_clean(liga: str = LIGA, year: str = YEAR, base_dir: Path = Path("gronestats/data/Liga 1 Peru")):
    base_dir.mkdir(parents=True, exist_ok=True)
    df_raw = fetch_matches(liga=liga, year=year)
    raw_path = base_dir / f"Partidos_{liga}_{year}.xlsx"
    df_raw.to_excel(raw_path, index=False, engine="openpyxl")
    df_clean = clean_scores(df_raw)
    clean_path = base_dir / f"Partidos_{liga}_{year}_limpio.xlsx"
    df_clean.to_excel(clean_path, index=False, engine="openpyxl")
    # Copia al master_data que usa el prep
    MASTER_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_excel(MASTER_CLEAN_PATH, index=False, engine="openpyxl")
    print(f"Guardado crudo: {raw_path}")
    print(f"Guardado limpio: {clean_path}")
    print(f"Copia limpia para master: {MASTER_CLEAN_PATH}")
    return df_clean, clean_path

def scrape_match_details(df_matches: pd.DataFrame, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    total = len(df_matches)
    for i, row in df_matches.iterrows():
        match_ref = row.get("match_url") or row.get("match_id")
        if pd.isna(match_ref):
            print(f"[{i+1}/{total}] skip: sin match_url/match_id")
            continue
        match_id = str(match_ref).split("#id:")[-1] if "#id:" in str(match_ref) else str(match_ref)
        try:
            try:
                team_stats_df = sofascore.scrape_team_match_stats(match_ref)
            except Exception:
                team_stats_df = pd.DataFrame()
            try:
                player_stats_df = sofascore.scrape_player_match_stats(match_ref)
            except Exception:
                player_stats_df = pd.DataFrame()
            try:
                avg_positions_df = sofascore.scrape_player_average_positions(match_ref)
            except Exception:
                avg_positions_df = pd.DataFrame()
            try:
                shotmap_df = sofascore.scrape_match_shots(match_ref)
            except Exception:
                shotmap_df = pd.DataFrame()
            try:
                momentum_df = sofascore.scrape_match_momentum(match_ref)
            except Exception:
                momentum_df = pd.DataFrame()
            heatmaps_df = pd.DataFrame(columns=["player", "player_id", "heatmap"])
            try:
                hm_dict = sofascore.scrape_heatmaps(match_id)
                heatmaps_list = []
                for pname, info in hm_dict.items():
                    if isinstance(info, dict) and info.get("heatmap"):
                        heatmaps_list.append({"player": pname, "player_id": info.get("id"), "heatmap": info.get("heatmap")})
                if heatmaps_list:
                    heatmaps_df = rename_duplicate_columns(pd.DataFrame(heatmaps_list))
            except Exception:
                pass

            for df_ in (team_stats_df, player_stats_df, avg_positions_df, shotmap_df, momentum_df):
                if isinstance(df_, pd.DataFrame) and not df_.empty:
                    rename_duplicate_columns(df_)

            out_xlsx = out_dir / f"Sofascore_{match_id}.xlsx"
            with pd.ExcelWriter(out_xlsx, engine="openpyxl") as w:
                team_stats_df.to_excel(w, sheet_name="Team Stats", index=False)
                player_stats_df.to_excel(w, sheet_name="Player Stats", index=False)
                avg_positions_df.to_excel(w, sheet_name="Average Positions", index=False)
                shotmap_df.to_excel(w, sheet_name="Shotmap", index=False)
                momentum_df.to_excel(w, sheet_name="Match Momentum", index=False)
                heatmaps_df.to_excel(w, sheet_name="Heatmaps", index=False)

            # verificar peso del archivo; si es sospechosamente pequeño, borrar y detener todo
            size_kb = out_xlsx.stat().st_size / 1024
            if size_kb < MIN_FILE_KB:
                msg = (
                    f"[{i+1}/{total}] error {match_id}: "
                    f"archivo menor a {MIN_FILE_KB} KB ({size_kb:.1f} KB). "
                    "Se elimina y se detiene el proceso."
                )
                try:
                    out_xlsx.unlink(missing_ok=True)
                except Exception:
                    pass
                with ERROR_LOG.open("a", encoding="utf-8") as f:
                    f.write(msg + "\n")
                print(msg)
                raise SystemExit(msg)

            print(f"[{i+1}/{total}] ok {match_id}")
        except Exception as e:
            print(f"[{i+1}/{total}] error {match_id}: {e}")
            traceback.print_exc()

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(out_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(out_dir.parent)
                zipf.write(file_path, arcname)
    print(f"zip listo: {zip_path}")
    return zip_path

def main():
    df_clean, _ = load_and_clean()
    #scrape_match_details(df_clean, DETAILS_DIR)

if __name__ == "__main__":
    main()
