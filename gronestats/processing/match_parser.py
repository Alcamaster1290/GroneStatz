import pandas as pd

def parse_match_summary(data):
    return pd.DataFrame([{
        "ID": data["id"],
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
        "Fecha": pd.to_datetime(data["startTimestamp"], unit="s", errors="coerce"),
        "Torneo": data["tournament"]["name"],
        "Temporada": data["season"]["name"],
        "Árbitro": data["referee"]["name"]
    }])
