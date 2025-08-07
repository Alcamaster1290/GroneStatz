from gronestats.scraping.match_data import obtener_datos_completos_del_partido

if __name__ == "__main__":
    URL_match = "https://www.sofascore.com/es/football/match/alianza-lima-club-sporting-cristal/cWslW#id:14186609"
    datos = obtener_datos_completos_del_partido(URL_match)

    print("🎯 Datos obtenidos correctamente.")
    print(datos["match_data"])
    print(datos["momentum"])
    print(datos["shotmap"])
    print(datos["alineacion_local"])
    print(datos["alineacion_visita"])
    print(datos["posiciones_promedio_local"])
    print(datos["posiciones_promedio_visita"])
    for player, heatmap in datos["heatmaps"].items():
        if heatmap is not None:
            print(f"Heatmap para {player}:")
            print(heatmap)
        else:
            print(f"No hay heatmap disponible para {player}.")
