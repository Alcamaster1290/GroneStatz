from LanusStats import SofaScore

def obtener_datos_completos_del_partido(URL_match):
    ss = SofaScore()
    try:
        print("▶️ Obteniendo datos generales del partido...")
        match_data = ss.get_match_data(URL_match)

        print("▶️ Obteniendo equipos...")
        home_team, away_team = ss.get_team_names(URL_match)
        print(f"📌 Local: {home_team} vs Visitante: {away_team}")

        print("▶️ Obteniendo mapa de tiros...")
        shotmap = ss.get_match_shotmap(URL_match)

        print("▶️ Obteniendo momentum del partido...")
        momentum = ss.get_match_momentum(URL_match)

        print("▶️ Obteniendo alineaciones y estadísticas por jugador...")
        home_players, away_players = ss.get_players_match_stats(URL_match)

        print("▶️ Obteniendo posiciones promedio de los jugadores...")
        avg_pos_home, avg_pos_away = ss.get_players_average_positions(URL_match)

        print("▶️ Obteniendo heatmap por jugador...")
        player_ids = ss.get_player_ids(URL_match)
        heatmaps = {}
        for player in list(player_ids.keys())[:3]:  # limitar para pruebas
            try:
                heatmaps[player] = ss.get_player_heatmap(URL_match, player)
            except:
                heatmaps[player] = None
                print(f"⚠️ No se pudo obtener heatmap para {player}")

        return {
            "match_data": match_data,
            "momentum": momentum,
            "shotmap": shotmap,
            "alineacion_local": home_players,
            "alineacion_visita": away_players,
            "posiciones_promedio_local": avg_pos_home,
            "posiciones_promedio_visita": avg_pos_away,
            "heatmaps": heatmaps
        }

    finally:
        # cerrar navegador si existe atributo driver
        if hasattr(ss, "driver"):
            try:
                ss.driver.quit()
                print("✅ Navegador cerrado correctamente.")
            except Exception as e:
                print(f"⚠️ Error al cerrar navegador: {e}")
