import pytest
import pandas as pd
from gronestats.scraping.match_data import obtener_datos_completos_del_partido

@pytest.mark.slow  # para indicar que es un test lento (usa scraping)
def test_obtener_datos_completos_del_partido():
    url = "https://www.sofascore.com/es/football/match/alianza-lima-club-sporting-cristal/cWslW#id:14186609"
    datos = obtener_datos_completos_del_partido(url)

    assert "match_data" in datos
    assert isinstance(datos["match_data"], dict)

    assert "shotmap" in datos
    assert datos["shotmap"] is not None

    assert "alineacion_local" in datos
    assert isinstance(datos["alineacion_local"], (list, pd.DataFrame))


    assert "heatmaps" in datos
    assert isinstance(datos["heatmaps"], dict)
