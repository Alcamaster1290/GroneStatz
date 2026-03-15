# GroneStatz

GroneStatz es un repositorio de analisis de datos para la Liga 1 de Peru. El foco actual del repo es un dashboard en Streamlit para explorar temporada, equipos, jugadores y partidos usando parquets normalizados.

## Estado actual

El MVP analitico vive en `gronestats/dashboard/` y trabaja sobre la temporada 2025.

Incluye:

- `Overview`: panorama general de la liga, standings, lideres y partidos destacados.
- `Equipos`: resumen por club, forma reciente y contribuyentes principales.
- `Jugadores`: ranking, perfil individual, posicion promedio y heatmap.
- `Partidos`: explorador con contexto, protagonistas y posicion promedio de ambos equipos.

El dashboard ya distingue:

- `Liga 1, Apertura`
- `Liga 1, Clausura`
- `Primera Division, Grand Final`

Por defecto abre con `Apertura + Clausura`. La `Grand Final` queda disponible como filtro explicito.

## Estructura relevante

- `gronestats/dashboard/`
  Aplicacion Streamlit, estado de filtros, modelos, metricas y vistas.
- `gronestats/processing/st_create_parquets.py`
  Construccion de parquets base a partir de la fuente limpia de partidos y tablas principales.
- `gronestats/processing/build_positional_parquets.py`
  Generacion de `average_positions.parquet` y `heatmap_points.parquet` desde los workbooks de Sofascore.
- `gronestats/data/Liga 1 Peru/2025/parquets/normalized/`
  Fuente principal consumida por el dashboard.
- `tests/test_dashboard_metrics.py`
  Cobertura de standings, filtros, leaders, heatmaps, average positions y contratos principales del dashboard.

## Ejecutar el dashboard

```powershell
cd "C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
.venv\Scripts\python.exe -m streamlit run gronestats/dashboard/app.py
```

## Regenerar datos

### Parquets base

El script de procesamiento principal es `gronestats/processing/st_create_parquets.py`. Asegura que `matches.parquet` preserve `tournament` y que la normalizacion genere `tournament_label` y `round_label`.

### Datos posicionales

Para reconstruir posiciones promedio y heatmaps:

```powershell
cd "C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz"
.venv\Scripts\python.exe gronestats/processing/build_positional_parquets.py
```

Esto genera:

- `gronestats/data/Liga 1 Peru/2025/parquets/normalized/average_positions.parquet`
- `gronestats/data/Liga 1 Peru/2025/parquets/normalized/heatmap_points.parquet`

## Criterios del dashboard

- La capa de producto ya no usa `Rating` de Sofascore.
- Los filtros globales se apoyan en `tournament` y `round_range`.
- Los mapas de jugador soportan dos alcances:
  - `Partido contextual`
  - `Acumulado del tramo regular`
- El explorador de partidos muestra el torneo de forma explicita para evitar colisiones entre rondas de Apertura y Clausura.

## Tests

```powershell
cd "C:\Users\Alvaro\Proyectos\Proyecto Gronestats\GroneStatz"
.venv\Scripts\python.exe -m pytest tests/test_dashboard_metrics.py
```

## Notas

- El repo contiene otras lineas de trabajo, por ejemplo `FantasyL1-2026/`, pero no forman parte del MVP Streamlit documentado aqui.
- Si actualizas la fuente de partidos o los workbooks de Sofascore, vuelve a generar los parquets antes de revisar el dashboard.
