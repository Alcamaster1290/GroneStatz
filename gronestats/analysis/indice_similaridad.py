import pandas as pd
import numpy as np
from pathlib import Path

# === CONFIG ===
FILE = Path(r"data\Jugadores_Datos_totales_Liga 1 Peru_2025.xlsx")
NORIEGA_ID = 1020375

# ---------- utilidades ----------
def per90(s, minutes):
    return s * 90 / minutes.replace(0, np.nan)

def preparar_datos(df):
    df = df.copy()
    base_p90 = [
        "tackles","interceptions","clearances","dribbledPast",
        "accuratePasses","accurateLongBalls","accurateFinalThirdPasses",
        "keyPasses","bigChancesCreated","fouls","wasFouled","yellowCards","redCards","goals"
    ]
    for c in base_p90:
        df[c+"_p90"] = per90(df[c], df["minutesPlayed"])
    df["cards_p90"] = df["yellowCards_p90"] + df["redCards_p90"]

    # excluir arqueros y exigir muestra razonable
    mask_no_gk = (df["saves"]+df["highClaims"]+df["runsOut"]+df["punches"] == 0)
    df = df[(df["minutesPlayed"] >= 900) & mask_no_gk].reset_index(drop=True)
    return df

def ref_row(df, player_id):
    r = df[df["player id"] == player_id]
    if r.empty:
        raise ValueError("No se encontró a Erick Noriega en el dataset filtrado.")
    return r.iloc[0]

def p5_p95(series):
    p5, p95 = np.nanpercentile(series, 5), np.nanpercentile(series, 95)
    if np.isclose(p95, p5):
        # fallback a min-max
        p5, p95 = float(np.nanmin(series)), float(np.nanmax(series))
    if np.isclose(p95, p5):
        p95 = p5 + 1e-6
    return p5, p95

def sim_from_ref(series, ref_val, mode="two_sided"):
    """Devuelve similitudes en [0,1] relativas a Noriega, con rango robusto p5–p95."""
    lo, hi = p5_p95(series)
    R = max(hi - lo, 1e-6)
    x = series.astype(float)

    if mode == "two_sided":
        sim = 1 - (abs(x - ref_val) / R)
    elif mode == "at_least":
        # igual o por encima de Noriega = 1; por debajo penaliza lineal
        sim = np.where(x >= ref_val, 1.0, 1 - ((ref_val - x) / R))
    elif mode == "at_most":
        # igual o por debajo de Noriega = 1; por encima penaliza lineal
        sim = np.where(x <= ref_val, 1.0, 1 - ((x - ref_val) / R))
    else:
        sim = 1 - (abs(x - ref_val) / R)

    return np.clip(sim, 0, 1)

def construir_indice(df, ref):
    # pesos y dirección de similitud
    feats = {
        # aire y duelos
        "aerialDuelsWonPercentage": ("at_least", 0.22),
        "groundDuelsWonPercentage": ("at_least", 0.10),
        # salida y volumen de pase
        "accuratePassesPercentage": ("at_least", 0.14),
        "accuratePasses_p90":       ("at_least", 0.08),
        "accurateLongBallsPercentage": ("at_least", 0.08),
        "accurateLongBalls_p90":       ("at_least", 0.08),
        "accurateFinalThirdPasses_p90":("at_least", 0.08),
        "keyPasses_p90":              ("at_least", 0.04),
        # defensa táctica
        "interceptions_p90":       ("at_least", 0.07),
        "tackles_p90":             ("at_least", 0.05),
        # despejes con menor peso para no sesgar a centrales puros
        "clearances_p90":          ("two_sided", 0.03),
        # seguridad
        "dribbledPast_p90":        ("at_most", 0.06),
        "cards_p90":               ("at_most", 0.04),
    }

    score = pd.Series(0.0, index=df.index, dtype=float)
    total_w = sum(w for _, w in feats.values())

    for col, (mode, w) in feats.items():
        ref_val = ref[col]
        sim = sim_from_ref(df[col], ref_val, mode=mode)
        score += sim * w

    df = df.copy()
    df["similarity_score"] = (score / total_w) * 100.0
    return df

def filtrar_rol(df):
    """Garante perfil pivote/central con salida y buen juego aéreo."""
    return df[
        (df["aerialDuelsWonPercentage"] >= 50) &
        (df["groundDuelsWonPercentage"] >= 50) &
        (df["accuratePassesPercentage"] >= 70) &
        ((df["accuratePasses_p90"] >= 25) | (df["accurateFinalThirdPasses_p90"] >= 2)) &
        (df["clearances_p90"].between(2, 11, inclusive="both"))
    ].copy()

def main():
    df0 = pd.read_excel(FILE, sheet_name="Sheet1")
    df = preparar_datos(df0)

    # ancla de referencia: Noriega tras preparación
    ref = ref_row(df, NORIEGA_ID)

    # filtro de rol antes de puntuar
    df_role = filtrar_rol(df)

    # construir índice de similitud a Noriega
    df_scored = construir_indice(df_role, ref)

    # columnas de salida
    cols_out = [
        "player","team","minutesPlayed","similarity_score",
        "totalDuelsWonPercentage","aerialDuelsWonPercentage","groundDuelsWonPercentage",
        "accuratePassesPercentage","accuratePasses_p90",
        "accurateLongBallsPercentage","accurateLongBalls_p90",
        "accurateFinalThirdPasses_p90","keyPasses_p90",
        "interceptions_p90","tackles_p90","clearances_p90",
        "dribbledPast_p90","cards_p90"
    ]

    top50 = df_scored.sort_values("similarity_score", ascending=False)[cols_out].head(50).copy()

    # resumen de Noriega en mismas features
    noriega_cols = ["player","team"] + [c for c in cols_out if c not in ["player","team","similarity_score"]]
    noriega = ref_row(df_scored, NORIEGA_ID)[noriega_cols].to_frame().T

    # redondeo y guardado con dos decimales
    top50_2d = top50.round(2)
    noriega_2d = noriega.round(2)
    top50_2d.to_csv("top50_similares_a_noriega.csv", index=False, encoding="utf-8-sig", float_format="%.2f")
    # muestra en consola con dos decimales
    pd.set_option("display.float_format", lambda x: f"{x:.2f}")
    print("Top-50 similares guardado en top50_similares_a_noriega.csv")
    print("Resumen de Noriega guardado en noriega_resumen.csv")
    print("\nTop-50 preview:")
    print(top50_2d.to_string(index=False))
    print("\nNoriega resumen:")
    print(noriega_2d.to_string(index=False))

if __name__ == "__main__":
    main()
