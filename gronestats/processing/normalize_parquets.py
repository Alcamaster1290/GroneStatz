# gronestats/processing/normalize_parquets.py
# Normaliza TODOS los parquets en:
#   gronestats\data\Liga 1 Peru\2025\parquets
# antes de registrarlos en DuckDB.
#
# Qué hace:
# - columnas *_id -> Int64 (nullable)
# - minutes*, matches*, goals, assists, saves, fouls, etc -> Int64
# - *_pm, price -> float64
# - position -> string UPPER (G/D/M/F si aplica)
# - flags tipo exclude*/transfer*/is_* -> boolean
# - escribe parquets normalizados en: ...\parquets\normalized\
#   (no pisa tus parquets originales)
#
# Ejecutar:
#   python .\gronestats\processing\normalize_parquets.py

from __future__ import annotations

from pathlib import Path
import re
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]  # .../GroneStatz
PARQUETS_DIR = BASE_DIR / "gronestats" / "data" / "Liga 1 Peru" / "2025" / "parquets"
OUT_DIR = PARQUETS_DIR / "normalized"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Heurísticas (ajusta si quieres)
ID_RE = re.compile(r".*_id$|^id$|^playerid$|^teamid$|^matchid$", re.IGNORECASE)
INT_RE = re.compile(
    r"^(minutes|minutesplayed|matches_played|matches|goals|assists|saves|fouls|cards|yellow|red|shots|xg|xa|penalty.*)$",
    re.IGNORECASE,
)
FLOAT_RE = re.compile(r".*_pm$|^price$|^xg$|^xa$|^rating$", re.IGNORECASE)
BOOL_RE = re.compile(r"^(is_|has_|exclude|transfer|active|injured|available)", re.IGNORECASE)

POS_COLS = {"position", "pos"}

CANONICAL_COLS = {
    "player_id": ["player_id", "playerid", "playerId", "PLAYER_ID"],
    "match_id": ["match_id", "matchid", "matchId", "MATCH_ID"],
    "team_id": ["team_id", "teamid", "teamId", "TEAM_ID"],
    "name": ["name", "NAME", "player_name", "player"],
    "position": ["position", "POSITION", "pos"],
    "dateofbirth": ["dateofbirth", "date_of_birth", "dateOfBirth", "DATEOFBIRTH"],
    "age_jan_2026": ["age_jan_2026", "AGE_JAN_2026", "age_enero_2026"],
    "minutesplayed": ["minutesplayed", "minutes_played", "MINUTESPLAYED", "minutes"],
    "matches_played": ["matches_played", "matchesplayed", "MATCHES_PLAYED", "matches"],
    "goals": ["goals", "GOALS", "goal"],
    "assists": ["assists", "ASSISTS", "assist", "GOALASSIST", "goalassist", "goal_assist"],
    "saves": ["saves", "SAVES", "save"],
    "fouls": ["fouls", "FOULS", "foul"],
    "yellowcards": ["yellowcards", "YELLOWCARDS", "yellow_cards"],
    "redcards": ["redcards", "REDCARDS", "red_cards"],
    "penaltywon": ["penaltywon", "PENALTYWON", "penalty_won"],
    "penaltysave": ["penaltysave", "PENALTYSAVE", "penalty_save"],
    "penaltyconceded": ["penaltyconceded", "PENALTYCONCEDED", "penalty_conceded"],
    "rating": ["rating", "RATING"],
}


def to_int64_nullable(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def to_float64(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("float64")


def to_bool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    # acepta 0/1, "true/false", "yes/no"
    x = s.astype("string").str.strip().str.lower()
    truthy = {"1", "true", "t", "yes", "y", "si", "sí"}
    falsy = {"0", "false", "f", "no", "n"}
    out = pd.Series(pd.NA, index=s.index, dtype="boolean")
    out[x.isin(truthy)] = True
    out[x.isin(falsy)] = False
    # si ya venía numérico
    num = pd.to_numeric(s, errors="coerce")
    out[num == 1] = True
    out[num == 0] = False
    return out.astype("boolean")


def normalize_position(s: pd.Series) -> pd.Series:
    x = s.astype("string").str.strip().str.upper()
    # normaliza valores comunes
    mapping = {
        "GK": "G",
        "GOALKEEPER": "G",
        "ARQ": "G",
        "DEF": "D",
        "DF": "D",
        "DEFENDER": "D",
        "MID": "M",
        "MF": "M",
        "MIDFIELDER": "M",
        "FWD": "F",
        "FW": "F",
        "FORWARD": "F",
        "DEL": "F",
        "ST": "F",
    }
    x = x.replace(mapping)
    # deja solo G/D/M/F si aplica
    x = x.where(x.isin(["G", "D", "M", "F"]), other=x)
    return x


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


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    for target, candidates in CANONICAL_COLS.items():
        work = coalesce_columns(work, target, candidates)
    return work


def normalize_df(df: pd.DataFrame, filename: str) -> pd.DataFrame:
    df = normalize_column_names(df)

    # columnas a string (seguro)
    for c in df.columns:
        # evita convertir listas/dicts raros
        if df[c].dtype == "object":
            # no fuerces si son estructuras
            sample = df[c].dropna().head(20)
            if not sample.empty and any(isinstance(v, (list, dict, set, tuple)) for v in sample):
                continue

    for c in df.columns:
        cl = c.lower()

        # position
        if cl in POS_COLS:
            df[c] = normalize_position(df[c])
            continue

        # booleans (por prefijo)
        if BOOL_RE.match(cl):
            df[c] = to_bool(df[c])
            continue

        # ids
        if ID_RE.match(cl) or cl.endswith("_id"):
            df[c] = to_int64_nullable(df[c])
            continue

        # floats
        if FLOAT_RE.match(cl):
            df[c] = to_float64(df[c])
            continue

        # ints exactos por nombre
        if INT_RE.match(cl) or cl.startswith("penalty"):
            df[c] = to_int64_nullable(df[c])
            continue

        # casos típicos por sufijo
        if cl.endswith("_count") or cl.endswith("_played") or cl.endswith("_minutes"):
            df[c] = to_int64_nullable(df[c])
            continue

        # fechas (si existen)
        if "date" in cl or cl.endswith("_at"):
            parsed = pd.to_datetime(df[c], errors="coerce", utc=False)
            # solo si parsea algo real, sino deja como está
            if parsed.notna().mean() > 0.2:
                df[c] = parsed
            continue

    # enforce player_id si existe con variantes típicas
    for alt in ["player_id", "playerid", "playerId"]:
        if alt in df.columns:
            df[alt] = to_int64_nullable(df[alt])

    return df


def main():
    files = sorted(PARQUETS_DIR.glob("*.parquet"))
    if not files:
        print(f"No se encontraron parquets en: {PARQUETS_DIR}")
        return

    print(f"Entrada : {PARQUETS_DIR}")
    print(f"Salida  : {OUT_DIR}\n")

    for fp in files:
        try:
            df = pd.read_parquet(fp)
            df2 = normalize_df(df, fp.name)

            out_fp = OUT_DIR / fp.name
            df2.to_parquet(out_fp, index=False)

            print(f"[OK] {fp.name:24} rows={len(df2):6} cols={df2.shape[1]:3} -> {out_fp.name}")
        except Exception as e:
            print(f"[FAIL] {fp.name}: {e}")

    print("\nListo.")


if __name__ == "__main__":
    main()
