import os
import glob
import zipfile
import traceback
from pathlib import Path
import argparse
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import pandas as pd
import ScraperFC as sfc

# Valores por defecto (sobrescribibles por CLI o env)
DEFAULT_YEAR = os.getenv("GRONESTATS_YEAR", "2024")
DEFAULT_LEAGUE = os.getenv("GRONESTATS_LEAGUE", "Liga 1 Peru")
DEFAULT_MIN_FILE_KB = int(os.getenv("GRONESTATS_MIN_FILE_KB", "15"))

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

sofascore = sfc.Sofascore()


class _State:
    """Estado global para la UI web."""

    def __init__(self) -> None:
        self.stage = "idle"
        self.message = ""
        self.total_steps = 0
        self.done_steps = 0
        self.total_details = 0
        self.done_details = 0
        self.error = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage,
            "message": self.message,
            "total_steps": self.total_steps,
            "done_steps": self.done_steps,
            "total_details": self.total_details,
            "done_details": self.done_details,
            "error": self.error,
        }


STATE = _State()


class _StatusHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, content: str, content_type: str = "text/html") -> None:
        payload = content.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/status":
            content = json.dumps(STATE.to_dict())
            self._send(200, content, "application/json")
            return

        html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>GroneStatz Loader</title>
<style>
body {{ font-family: Arial, sans-serif; background: #0e1117; color: #e8e9ed; padding: 24px; }}
.card {{ background: #161b22; padding: 16px; border-radius: 10px; max-width: 640px; }}
.bar-container {{ background: #2d333b; border-radius: 6px; overflow: hidden; height: 18px; }}
.bar-fill {{ background: linear-gradient(90deg, #3fb950, #238636); height: 100%; width: 0%; transition: width 0.3s; }}
.row {{ margin: 10px 0; }}
.error {{ color: #f85149; }}
</style>
<script>
async function refresh() {{
    const res = await fetch('/status');
    const data = await res.json();
    document.getElementById('stage').textContent = data.stage;
    document.getElementById('msg').textContent = data.message;
    document.getElementById('error').textContent = data.error || '';
    const tsteps = data.total_steps || 0;
    const dsteps = data.done_steps || 0;
    const pctAll = tsteps > 0 ? Math.min(100, Math.round((dsteps / tsteps) * 100)) : 0;
    document.getElementById('bar-all').style.width = pctAll + '%';
    document.getElementById('pct-all').textContent = pctAll + '%';
    document.getElementById('counts-all').textContent = tsteps ? `${dsteps} / ${tsteps} pasos totales` : 'N/A';
    const total = data.total_details || 0;
    const done = data.done_details || 0;
    const pct = total > 0 ? Math.min(100, Math.round((done / total) * 100)) : 0;
    document.getElementById('bar-details').style.width = pct + '%';
    document.getElementById('pct-details').textContent = pct + '%';
    document.getElementById('counts-details').textContent = total ? `${done} / ${total} partidos` : 'N/A';
}}
setInterval(refresh, 1000);
window.onload = refresh;
</script>
</head>
<body>
  <div class="card">
    <h2>GroneStatz Loader</h2>
    <div class="row">Estado: <strong id="stage">-</strong></div>
    <div class="row">Mensaje: <span id="msg">-</span></div>
    <div class="row">Progreso general: <span id="counts-all">N/A</span> (<span id="pct-all">0%</span>)</div>
    <div class="bar-container"><div class="bar-fill" id="bar-all"></div></div>
    <div class="row">Progreso detalles: <span id="counts-details">N/A</span> (<span id="pct-details">0%</span>)</div>
    <div class="bar-container"><div class="bar-fill" id="bar-details"></div></div>
    <div class="row error" id="error"></div>
  </div>
</body>
</html>
"""
        self._send(200, html, "text/html")


def _serve_status(port: int) -> HTTPServer:
    server = HTTPServer(("0.0.0.0", port), _StatusHandler)

    def _run() -> None:
        server.serve_forever()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"[LOADING] UI web en http://localhost:{port}")
    return server


def _print_loading(msg: str) -> None:
    """Salida simple de estado para interfaz de carga en consola."""
    STATE.message = msg
    print(f"[LOADING] {msg}")


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


def _normalize_match_id(match_ref) -> str:
    s = str(match_ref)
    return s.split("#id:")[-1] if "#id:" in s else s


def _existing_match_ids(out_dir: Path) -> set[str]:
    ids = set()
    if not out_dir.exists():
        return ids
    for f in out_dir.glob("Sofascore_*.xlsx"):
        name = f.stem  # Sofascore_<id>
        parts = name.split("_", 1)
        if len(parts) == 2:
            ids.add(parts[1])
    return ids


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


def load_and_clean(league: str, year: str, base_dir: Path) -> tuple[pd.DataFrame, Path]:
    STATE.stage = "load_and_clean"
    STATE.total_steps = 1  # paso de load/clean
    STATE.done_steps = 0
    _print_loading(f"Inicio load_and_clean | liga={league} | year={year}")
    base_dir.mkdir(parents=True, exist_ok=True)
    _print_loading("Descargando listado de partidos desde SofaScore...")
    df_raw = fetch_matches(liga=league, year=year)
    raw_path = base_dir / f"Partidos_{league}_{year}.xlsx"
    df_raw.to_excel(raw_path, index=False, engine="openpyxl")
    _print_loading(f"Guardado crudo en {raw_path}")
    _print_loading("Limpiando marcadores (home_score/away_score)...")
    df_clean = clean_scores(df_raw)
    clean_path = base_dir / f"Partidos_{league}_{year}_limpio.xlsx"
    df_clean.to_excel(clean_path, index=False, engine="openpyxl")
    master_clean_path = Path(f"gronestats/data/master_data/Partidos_{league}_{year}_limpio.xlsx")
    master_clean_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_excel(master_clean_path, index=False, engine="openpyxl")
    _print_loading(f"Guardado limpio en {clean_path} y copia a {master_clean_path}")
    print(f"Guardado crudo: {raw_path}")
    print(f"Guardado limpio: {clean_path}")
    print(f"Copia limpia para master: {master_clean_path}")
    _print_loading("load_and_clean completado.")
    STATE.done_steps = 1
    return df_clean, clean_path


def scrape_match_details(df_matches: pd.DataFrame, out_dir: Path, min_file_kb: int, error_log: Path) -> Path:
    STATE.stage = "scrape_details"
    STATE.total_details = len(df_matches)
    STATE.done_details = 0
    out_dir.mkdir(parents=True, exist_ok=True)

    # Normaliza IDs y filtra los ya existentes para no duplicar archivos
    df_work = df_matches.copy()
    df_work["norm_id"] = df_work.apply(lambda r: _normalize_match_id(r.get("match_url") or r.get("match_id")), axis=1)
    df_work = df_work[~df_work["norm_id"].isna()]

    existing = _existing_match_ids(out_dir)
    if existing:
        df_work = df_work[~df_work["norm_id"].isin(existing)]
        print(f"[INFO] {len(existing)} partidos ya existen en {out_dir}, se omiten.")

    total = len(df_work)
    STATE.total_details = total
    STATE.done_details = 0
    STATE.total_steps = STATE.done_steps + total

    for i, row in df_work.iterrows():
        match_ref = row.get("match_url") or row.get("match_id")
        if pd.isna(match_ref):
            print(f"[{i+1}/{total}] skip: sin match_url/match_id")
            continue
        match_id = row["norm_id"]
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

            size_kb = out_xlsx.stat().st_size / 1024
            if size_kb < min_file_kb:
                msg = (
                    f"[{i+1}/{total}] error {match_id}: "
                    f"archivo menor a {min_file_kb} KB ({size_kb:.1f} KB). "
                    "Se elimina y se detiene el proceso."
                )
                try:
                    out_xlsx.unlink(missing_ok=True)
                except Exception:
                    pass
                error_log.parent.mkdir(parents=True, exist_ok=True)
                with error_log.open("a", encoding="utf-8") as f:
                    f.write(msg + "\n")
                print(msg)
                STATE.error = msg
                raise SystemExit(msg)

            print(f"[{i+1}/{total}] ok {match_id}")
            STATE.done_details = i + 1
            STATE.done_steps = STATE.done_steps + 1
        except Exception as e:
            print(f"[{i+1}/{total}] error {match_id}: {e}")
            traceback.print_exc()
            STATE.error = str(e)

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(out_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(out_dir.parent)
                zipf.write(file_path, arcname)
    print(f"zip listo: {zip_path}")
    return zip_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Loader/cleaner dinámico para SofaScore (GroneStatz).")
    parser.add_argument("-l", "--league", default=DEFAULT_LEAGUE, help="Nombre de liga (ej: 'Liga 1 Peru').")
    parser.add_argument("-y", "--year", default=DEFAULT_YEAR, help="Año (ej: 2025).")
    parser.add_argument("--min-file-kb", type=int, default=DEFAULT_MIN_FILE_KB, help="Umbral mínimo en KB para XLSX de detalles.")
    parser.add_argument("--skip-details", action="store_true", help="Omitir scraping de detalles y solo dejar crudo/limpio.")
    parser.add_argument("--web-port", type=int, default=None, help="Levanta UI web de progreso en este puerto.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    league = args.league
    year = args.year
    min_file_kb = args.min_file_kb
    base_dir = Path(f"gronestats/data/{league}")
    details_dir = Path(f"gronestats/data/{league}/{year}")
    error_log = Path(f"logs/matches_details_errors_{league}_{year}.txt")

    server = None
    if args.web_port:
        server = _serve_status(args.web_port)

    df_clean, _ = load_and_clean(league=league, year=year, base_dir=base_dir)

    if not args.skip_details:
        scrape_match_details(df_clean, details_dir, min_file_kb=min_file_kb, error_log=error_log)

    if server:
        server.shutdown()


if __name__ == "__main__":
    main()
