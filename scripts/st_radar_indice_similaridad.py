# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(layout="wide", page_title="Radar - Similitud a Noriega")

CSV = Path("top50_similares_a_noriega.csv")

# --- Diccionario Español - Inglés ---
METRICS_DICT = {
    "aerialDuelsWonPercentage": "Porcentaje duelos aéreos ganados",
    "groundDuelsWonPercentage": "Porcentaje duelos suelo ganados",
    "accuratePassesPercentage": "Precisión de pases",
    "accuratePasses_p90": "Pases precisos por 90 ",
    "accurateLongBallsPercentage": "Precisión balones largos ",
    "accurateLongBalls_p90": "Balones largos precisos por 90 ",
    "accurateFinalThirdPasses_p90": "Pases al último tercio por 90 ",
    "keyPasses_p90": "Pases clave por 90 ",
    "interceptions_p90": "Intercepciones por 90 ",
    "tackles_p90": "Entradas por 90 ",
    "clearances_p90": "Despejes por 90 ",
    "dribbledPast_p90": "Veces regateado por 90 ",
    "cards_p90": "Tarjetas por 90 "
}

FEATURES = {
    "aerialDuelsWonPercentage": "at_least",
    "groundDuelsWonPercentage": "at_least",
    "accuratePassesPercentage": "at_least",
    "accuratePasses_p90": "at_least",
    "accurateLongBallsPercentage": "at_least",
    "accurateLongBalls_p90": "at_least",
    "accurateFinalThirdPasses_p90": "at_least",
    "keyPasses_p90": "at_least",
    "interceptions_p90": "at_least",
    "tackles_p90": "at_least",
    "clearances_p90": "two_sided",
    "dribbledPast_p90": "at_most",
    "cards_p90": "at_most",
}

DEFAULT_WEIGHTS = {
    "aerialDuelsWonPercentage": 0.22,
    "groundDuelsWonPercentage": 0.10,
    "accuratePassesPercentage": 0.14,
    "accuratePasses_p90": 0.08,
    "accurateLongBallsPercentage": 0.08,
    "accurateLongBalls_p90": 0.08,
    "accurateFinalThirdPasses_p90": 0.08,
    "keyPasses_p90": 0.04,
    "interceptions_p90": 0.07,
    "tackles_p90": 0.05,
    "clearances_p90": 0.03,
    "dribbledPast_p90": 0.06,
    "cards_p90": 0.04,
}

if not CSV.exists():
    st.error(f"No se encuentra {CSV}. Ejecuta antes el script que genera top10_similares_a_noriega.csv.")
    st.stop()

df = pd.read_csv(CSV, encoding="utf-8-sig").fillna(0)

# --- Sidebar: reset button + sliders stored in session_state ---
st.sidebar.header("Peso de métricas (ajusta y aplica)")
st.sidebar.write("Los pesos se normalizan automáticamente (suman 1).")

# Initialize session state keys for weights
for feat, default in DEFAULT_WEIGHTS.items():
    key = f"w__{feat}"
    if key not in st.session_state:
        st.session_state[key] = float(default)

# Reset button
if st.sidebar.button("Restablecer valores"):
    for feat, default in DEFAULT_WEIGHTS.items():
        st.session_state[f"w__{feat}"] = float(default)
    st.rerun()

# Sliders using session_state keys
weights = {}
total_input = 0.0
for feat in DEFAULT_WEIGHTS.keys():
    key = f"w__{feat}"
    w = st.sidebar.slider(
        METRICS_DICT[feat], 0.0, 1.0, st.session_state[key], step=0.01, key=key + "_slider"
    )
    st.session_state[key] = w
    weights[feat] = w
    total_input += w

# Normalize weights
if total_input == 0:
    norm_weights = {k: 1/len(weights) for k in weights}
else:
    norm_weights = {k: v/total_input for k, v in weights.items()}

st.sidebar.markdown("**Pesos normalizados:**")
for k, v in norm_weights.items():
    st.sidebar.write(f"{METRICS_DICT[k]}: {v:.2f}")

# --- Compute _sim columns (percentiles / two_sided logic) ---
df_proc = df.copy()
for col, mode in FEATURES.items():
    if col not in df_proc.columns:
        df_proc[col] = 0.0
    pct = df_proc[col].rank(pct=True, method="average").values  # 0-1
    if mode == "at_least":
        sim = pct
    elif mode == "at_most":
        sim = 1 - pct # type: ignore
    elif mode == "two_sided":
        ref_val = df_proc.loc[df_proc["player"] == "Erick Noriega", col].values
        if len(ref_val) == 0:
            ref_val = np.array([df_proc[col].median()])
        ref_val = float(ref_val[0])
        rng = df_proc[col].quantile(0.95) - df_proc[col].quantile(0.05)
        if np.isclose(rng, 0):
            rng = df_proc[col].max() - df_proc[col].min()
        if np.isclose(rng, 0):
            rng = 1.0
        sim = 1 - (np.abs(df_proc[col] - ref_val) / rng)
        sim = np.clip(sim, 0, 1)
    else:
        sim = pct
    df_proc[col + "_sim"] = sim

# --- Dynamic score with normalized weights ---
df_proc["dynamic_score"] = 0.0
for f in FEATURES.keys():
    df_proc["dynamic_score"] += df_proc[f + "_sim"] * norm_weights[f]
max_score = df_proc["dynamic_score"].max()
if np.isclose(max_score, 0):
    max_score = 1.0
df_proc["dynamic_score"] = (df_proc["dynamic_score"] / max_score) * 100
df_proc["dynamic_score"] = df_proc["dynamic_score"].round(2)

# --- Player selection: Erick always + up to 2 more ---
st.title("Radar de percentiles - Similitud a Erick Noriega con datos de Liga 1 2025")
st.markdown("Este radar muestra la similitud de jugadores a Erick Noriega, usando un índice dinámico basado en percentiles de métricas clave. Los pesos de las métricas se pueden ajustar en la barra lateral.")
st.markdown("Selecciona hasta 2 jugadores además de Erick Noriega (siempre aparece)")

players_all = df_proc["player"].tolist()
players_no_noriega = [p for p in players_all if p != "Erick Noriega"]

default_choices = [p for p in ["Renzo Garcés", "Matías Di Benedetto", "Leonel Galeano"] if p in players_no_noriega][:2]
selected_extra = st.multiselect("Selecciona hasta 2 jugadores (además de Noriega)", players_no_noriega, default=default_choices)

if len(selected_extra) > 2:
    st.warning("Máximo 2 jugadores además de Erick Noriega. Selección recortada a los primeros 2.")
    selected_extra = selected_extra[:2]

selected = ["Erick Noriega"] + selected_extra

# --- Radar plot ---
radar_metrics = list(FEATURES.keys())
categories = [METRICS_DICT[m] for m in radar_metrics]

fig = go.Figure()
for pl in selected:
    row = df_proc[df_proc["player"] == pl].iloc[0]
    vals = [float(row[m + "_sim"]) * 100 for m in radar_metrics]
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]],
        theta=categories + [categories[0]],
        fill='toself',
        name=f"{pl} ({row['dynamic_score']:.2f})"
    ))

fig.update_layout(
    polar=dict(radialaxis=dict(visible=True, range=[0,100])),
    showlegend=True,
    margin=dict(l=40, r=40, t=60, b=40),
    height=600
)

col1, col2 = st.columns((2,1))
with col1:
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Ranking según pesos actuales")
    display_base = ["player", "team", "minutesPlayed", "dynamic_score"]

    # Construcción de tabla visible
    table = df_proc[display_base + [c + "_sim" for c in radar_metrics]].copy()
    for m in radar_metrics:
        table[METRICS_DICT[m]] = (table[m + "_sim"] * 100).round(2)
        table.drop(columns=[m + "_sim"], inplace=True)
    table = table.sort_values("dynamic_score", ascending=False).reset_index(drop=True)
    st.dataframe(table.round(2))

    st.markdown("**Exportar resultado**")

    # 📌 Exportar con datos originales + dynamic_score (no percentiles)
    export_cols = ["player", "team", "minutesPlayed", "dynamic_score"] + list(FEATURES.keys())
    export_table = df_proc[export_cols].sort_values("dynamic_score", ascending=False).reset_index(drop=True)

    # 🔑 Convertir a CSV en memoria (en bytes)
    csv = export_table.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="📥 Descargar CSV",
        data=csv,
        file_name="mis_candidatos_reemplazo_noriega.csv",
        mime="text/csv"
    )


st.markdown("- Erick Noriega siempre se incluye en el radar. - Selecciona hasta 2 jugadores adicionales.")
