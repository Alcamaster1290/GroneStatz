import pandas as pd
import streamlit as st
#import ScraperFC
from LanusStats import SofaScore
from io import BytesIO

def parse_match_summary(data):
    resumen = {
        "Equipo Local": data["homeTeam"]["name"],
        "Manager Local": data["homeTeam"]["manager"]["name"],
        "Goles 1T Local": data["homeScore"]["period1"],
        "Goles 2T Local": data["homeScore"]["period2"],
        "Total Goles Local": data["homeScore"]["display"],

        "Equipo Visitante": data["awayTeam"]["name"],
        "Manager Visitante": data["awayTeam"]["manager"]["name"],
        "Goles 1T Visitante": data["awayScore"]["period1"],
        "Goles 2T Visitante": data["awayScore"]["period2"],
        "Total Goles Visitante": data["awayScore"]["display"],

        "Resultado Final": f"{data['homeScore']['display']} - {data['awayScore']['display']}",
        "Estadio": data["venue"]["name"],
        "Ciudad": data["venue"]["city"]["name"],
        "Fecha": pd.to_datetime(data["startTimestamp"], unit="s"),
        "Arbitro": data["referee"]["name"],
    }

    return pd.DataFrame([resumen])

def rename_duplicate_columns(df):
    cols = pd.Series(df.columns)
    for dup in cols[cols.duplicated()].unique():
        dups = cols[cols == dup].index.tolist()
        for i, idx in enumerate(dups):
            if i == 0:
                continue
            cols[idx] = f"{dup}_{i}"
    df.columns = cols
    return df


# Crear una instancia del objeto Sofascore
#sofascore = ScraperFC.Sofascore()
sofascore = SofaScore()

# Configuración de la página de Streamlit
st.title("Scraping de Datos de Partidos de Fútbol")
st.write("Esta aplicación realiza scraping de datos de partidos de fútbol desde Sofascore y permite descargar los datos en un archivo Excel.")

# Pedir el match_id al usuario
match_url = st.text_input("Introduce el URL del partido:")

if st.button("Obtener Datos y Generar Excel"):
    try:
        match_id = sofascore.get_match_id(match_url)
        match_stats = sofascore.get_match_data(match_url) # Objeto dict

        if isinstance(match_stats, dict) and "event" in match_stats:
            event = match_stats["event"]
            match_stats_df = parse_match_summary(event)
            st.dataframe(match_stats_df)
        else:
            st.error("No se pudo obtener información del partido. Favor de verificar el URL.")

        player_stats_home, player_stats_away = sofascore.get_players_match_stats(match_url)

        player_stats_home["Equipo"] = "Local"
        player_stats_away["Equipo"] = "Visitante"

        player_stats_home = rename_duplicate_columns(player_stats_home)
        player_stats_away = rename_duplicate_columns(player_stats_away)

        player_stats_df = pd.concat([player_stats_home, player_stats_away], ignore_index=True)

        # Posiciones promedio de los jugadores
        average_positions_home, average_positions_away = sofascore.get_players_average_positions(match_url)
        average_positions_home["Equipo"] = "Local"
        average_positions_away["Equipo"] = "Visitante"
        # Renombrar columnas duplicadas posicion promedio
        average_positions_home = rename_duplicate_columns(average_positions_home)
        average_positions_away = rename_duplicate_columns(average_positions_away)
        # Combinar posiciones promedio de ambos equipos
        average_positions_df = pd.concat([average_positions_home, average_positions_away], ignore_index=True)


        match_shotmap_df = sofascore.get_match_shotmap(match_url)
        match_shotmap_df = rename_duplicate_columns(match_shotmap_df)

        match_momentum = sofascore.get_match_momentum(match_url)

        # Guardar en memoria en lugar de archivo local
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            match_stats_df.to_excel(writer, sheet_name='Team Stats', index=False)
            player_stats_df.to_excel(writer, sheet_name='Player Stats', index=False)
            average_positions_df.to_excel(writer, sheet_name='Average Positions', index=False)
            match_shotmap_df.to_excel(writer, sheet_name='Shotmap', index=False)
            match_momentum.to_excel(writer, sheet_name='Match Momentum', index=False)

        output.seek(0)
        
        st.success("Datos obtenidos con éxito.")
        
        # Vista previa
        st.subheader("Vista Previa de los Datos")
        st.write("### Team Stats")
        st.dataframe(match_stats_df.head())

        st.write("### Player Stats")
        st.dataframe(player_stats_df.head())

        st.write("### Average Positions")
        st.dataframe(average_positions_df.head())

        st.write("### Shotmap")
        st.dataframe(match_shotmap_df.head())

        st.write("### Match Momentum")
        st.dataframe(match_momentum.head())


        # Botón para descargar el archivo Excel
        st.download_button(
            label="Descargar Archivo Excel",
            data=output,
            file_name=f'Sofascore_{match_id}.xlsx',
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        st.error(f"Error al obtener datos para el partido {match_id}: {e}")