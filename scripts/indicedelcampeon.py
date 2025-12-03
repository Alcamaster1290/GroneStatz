import pandas as pd
import streamlit as st
import plotly.express as px

st.title("Índice del Campeón – Evolución Liga 1 2025 (normalizado por puntos)")

archivo = st.file_uploader("Sube el archivo Excel aqui", type="xlsx")

if archivo:
    df = pd.read_excel(archivo)

    # === MAPEO DE PESOS POR NIVEL ===
    pesos = {"Candidato": 1.00, "Competitivo": 0.95, "Promedio": 0.90, "Descenso": 0.85}
    df["Peso"] = df["Nivel_Competitividad"].map(pesos)
    w_prom = df["Peso"].mean()

    # === PARÁMETROS ===
    PARTIDOS_VALIDOS = 34
    PUNTOS_CAMPEON = 80
    F = PUNTOS_CAMPEON / (PARTIDOS_VALIDOS * (1 / w_prom))

    # === PUNTOS ESPERADOS (REDONDEADOS) ===
    df["Puntos_Esperados"] = (
        PARTIDOS_VALIDOS * (df["Peso"] / w_prom) * F
    ).round(0).astype(int)

    # === PUNTOS REALES ===
    cols_fechas = [c for c in df.columns if c.startswith("J")]
    df["Puntos_Reales"] = df[cols_fechas].ffill(axis=1).iloc[:, -1]

    # === ÍNDICE FINAL ===
    df["Indice_del_Campeon"] = (
        df["Puntos_Reales"] / df["Puntos_Esperados"]
    ).clip(upper=1.00).round(2)

    # === TABLA GENERAL ===
    df_resultado = df[["Equipo", "Nivel_Competitividad", "Puntos_Reales",
                       "Puntos_Esperados", "Indice_del_Campeon"]].sort_values(
                       "Indice_del_Campeon", ascending=False)

    st.subheader("Tabla general – Índice del Campeón (Acumulado)")
    st.dataframe(df_resultado, use_container_width=True)

    # === GRÁFICO FINAL ===
    fig = px.bar(
        df_resultado,
        x="Equipo",
        y="Indice_del_Campeon",
        color="Nivel_Competitividad",
        text="Indice_del_Campeon",
        category_orders={"Equipo": df_resultado["Equipo"].tolist()},
        height=600
    )
    equipos_descenso = 4
    x_pos = len(df_resultado) - equipos_descenso + 0.5
    fig.add_vline(
        x=x_pos,
        line_dash="dash",
        line_color="red",
        annotation_text="Zona de descenso",
        annotation_position="top right"
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(yaxis=dict(range=[0, 1]))
    st.subheader("Gráfico de rendimiento final")
    st.plotly_chart(fig, use_container_width=True)

    # === EVOLUCIÓN DEL ÍNDICE POR JORNADA ===
    jornadas = [c for c in df.columns if c.startswith("J")]

    # Calcular índices jornada por jornada
    df_evol = df[["Equipo", "Puntos_Esperados"]].copy()
    for j in jornadas:
        df_evol[j] = (df[j] / df_evol["Puntos_Esperados"]).clip(upper=1.0).round(2)
    df_evol.drop(columns="Puntos_Esperados", inplace=True)

    # === TABLA DE EVOLUCIÓN (AMPLIA) ===
    st.subheader("Evolución del Índice del Campeón por Jornada")
    st.dataframe(df_evol.set_index("Equipo"), use_container_width=True)

    # === GRÁFICO DE EVOLUCIÓN (LÍNEAS, CON COLORES Y FILTROS COMPLETOS) ===
    df_evol_long = df_evol.melt(
        id_vars="Equipo",
        var_name="Jornada",
        value_name="Índice_del_Campeon"
    )
    df_evol_long["Jornada_Num"] = df_evol_long["Jornada"].str.extract("(\d+)").astype(int)

    # Vincula color, nivel, región, departamento y altura
    color_map = dict(zip(df["Equipo"], df["Color"]))
    df_evol_long = df_evol_long.merge(
        df[["Equipo", "Nivel_Competitividad", "Región", "Departamento", "Es_Equipo_Altura"]],
        on="Equipo",
        how="left"
    )

    st.subheader("Filtros de visualización")

    # === FILTROS MULTISELECCIÓN ===
    col1, col2, col3 = st.columns(3)

    with col1:
        niveles_opts = sorted(df["Nivel_Competitividad"].unique().tolist())
        niveles_sel = st.multiselect(
            "Nivel de Competitividad",
            options=niveles_opts,
            default=niveles_opts
        )

    with col2:
        regiones_opts = sorted(df["Región"].unique().tolist())
        regiones_sel = st.multiselect(
            "Región",
            options=regiones_opts,
            default=regiones_opts
        )

    with col3:
        deptos_opts = sorted(df["Departamento"].unique().tolist())
        deptos_sel = st.multiselect(
            "Departamento",
            options=deptos_opts,
            default=deptos_opts
        )

    # === FILTRO POR EQUIPOS DE ALTURA (BOOLEANO) ===
    st.markdown("### Filtro por Condición de Altura")
    col_alt1, col_alt2 = st.columns(2)
    with col_alt1:
        mostrar_altura = st.checkbox("Mostrar equipos de altura", value=True)
    with col_alt2:
        mostrar_no_altura = st.checkbox("Mostrar equipos sin altura", value=True)

    # === APLICAR FILTROS ===
    df_plot = df_evol_long[
        (df_evol_long["Nivel_Competitividad"].isin(niveles_sel)) &
        (df_evol_long["Región"].isin(regiones_sel)) &
        (df_evol_long["Departamento"].isin(deptos_sel))
    ]

    # Filtro booleano de altura
    if not (mostrar_altura and mostrar_no_altura):
        if mostrar_altura and not mostrar_no_altura:
            df_plot = df_plot[df_plot["Es_Equipo_Altura"] == 1]
        elif mostrar_no_altura and not mostrar_altura:
            df_plot = df_plot[df_plot["Es_Equipo_Altura"] == 0]
        else:
            df_plot = df_plot.iloc[0:0]

    # === GRÁFICO ===
    fig_evol = px.line(
        df_plot,
        x="Jornada_Num",
        y="Índice_del_Campeon",
        color="Equipo",
        title="Evolución del Índice del Campeón (Jornada a Jornada)",
        markers=True,
        color_discrete_map=color_map
    )

    # === LÍNEA PUNTEADA DE PERMANENCIA Y CAMPEONATO ===
    fig_evol.add_hline(
        y=0.5,
        line_dash="dot",
        line_color="orange",
        annotation_text="Permanencia en Liga 1",
        annotation_position="top right"
    )

    fig_evol.add_hline(
        y=1,
        line_dash="dot",
        line_color="yellow",
        annotation_text="CAMPEÓN DE LIGA 1",
        annotation_position="top right"
    )

    fig_evol.update_layout(
        yaxis=dict(range=[0, 1]),
        legend_title_text="Equipo",
        xaxis_title="Jornada",
        yaxis_title="Índice del Campeón (normalizado)"
    )

    st.plotly_chart(fig_evol, use_container_width=True)

    st.caption(
        "Usa los filtros para combinar Nivel de Competitividad, Región, Departamento y Condición de Altura. "
        "Cada línea mantiene el color oficial definido en el Excel; los valores cercanos a 1 indican ritmo de campeón. "
        "La línea naranja punteada representa el umbral de permanencia en Liga 1 (≈0.5)."
    )


else:
    st.info("Sube el archivo Excel para calcular los índices.")
