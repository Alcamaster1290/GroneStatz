# Backfill de Shotmap y Momentum

## Punto de entrada real del repo

La ruta productiva para obtener detalles de partido desde SofaScore ya existe en `gronestats/processing/data_loader_unprep.py`.

El flujo actual usa `ScraperFC` con `Sofascore()` y llama estas funciones por partido:

- `scrape_team_match_stats(match_ref)`
- `scrape_player_match_stats(match_ref)`
- `scrape_player_average_positions(match_ref)`
- `scrape_match_shots(match_ref)`
- `scrape_match_momentum(match_ref)`
- `scrape_heatmaps(match_id)`

Luego escribe un workbook `Sofascore_<match_id>.xlsx` con estas hojas:

- `Team Stats`
- `Player Stats`
- `Average Positions`
- `Shotmap`
- `Match Momentum`
- `Heatmaps`

## Notebooks útiles

### `notebooks/active/nb_05_extraer_partido_por_match_id.ipynb`

Es el mejor cuaderno para depurar un partido puntual. Ya está pensado para:

- recibir un `match_id`
- instanciar `sofascore = sfc.Sofascore()`
- extraer `match_dict`
- probar `scrape_player_match_stats(match_id)`
- revisar el payload del partido antes de pasarlo a Fantasy

Debe ser el notebook de diagnóstico rápido cuando un solo `match_id` falle.

### `notebooks/legacy/nb_03_detallar_partidos.ipynb`

Este cuaderno es la referencia más útil para fallback directo contra la API de SofaScore. Incluye wrappers manuales:

- `safe_scrape_team_stats(match_id)` -> `/event/{match_id}/statistics`
- `safe_scrape_player_stats(match_id)` -> `/event/{match_id}/player-statistics`
- `safe_scrape_avg_positions(match_id)` -> `/event/{match_id}/average-positions`
- `safe_scrape_shotmap(match_id)` -> `/event/{match_id}/shotmap`
- `safe_scrape_momentum(match_id)` -> `/event/{match_id}/graph`

También contiene `safe_get_json()` para limpiar respuestas HTML con `<pre>...</pre>`.

### `notebooks/legacy/nb_02_limpiar_partidos.ipynb`

Replica el flujo de extracción por partido y deja claro cómo convertir cada respuesta en hojas Excel. Sirve como antecedente del loader productivo.

### `notebooks/legacy/nb_01_obtener_partidos_liga_anual.ipynb`

Es la referencia para reconstruir el maestro anual de partidos usando:

- `sofascore.get_match_dicts(year=year, league=liga)`
- `sofascore.get_match_dict(match_id)`

## Hallazgos validados en ejecución

Se probaron llamadas reales con `ScraperFC` sobre partidos que hoy siguen con warning:

- `15362086` (`2026`, warning de `momentum`)
- `13596389` (`2025`, warning de `momentum`)
- `11018862` (`2023`, warnings de `shotmap` y `momentum`)

Resultados observados:

- `15362086`
  - `scrape_match_shots()` devuelve filas
  - `scrape_match_momentum()` devuelve vacío
  - `ScraperFC` reporta `404` en `/event/15362086/graph`
- `13596389`
  - `scrape_match_shots()` devuelve filas
  - `scrape_match_momentum()` devuelve vacío
  - `ScraperFC` reporta `404` en `/event/13596389/graph`
- `11018862`
  - `scrape_match_shots()` devuelve vacío
  - `scrape_match_momentum()` devuelve vacío
  - `ScraperFC` reporta `404` en `/event/11018862/shotmap`
  - `ScraperFC` reporta `404` en `/event/11018862/graph`

Conclusión práctica:

- Hay warnings que sí parecen backfillables, sobre todo cuando `shotmap` ya existe en origen y faltó por una corrida anterior.
- Hay warnings que no son “faltó scrapear”, sino “el endpoint hoy no entrega ese recurso”.
- En particular, `momentum` está faltando en varios partidos porque `/graph` devuelve `404`, incluso cuando `shotmap` sí existe.

## Estrategia recomendada

### 1. Diagnóstico por partido

Usar `nb_05_extraer_partido_por_match_id.ipynb` para probar un `match_id` antes de relanzar una temporada completa.

Orden recomendado:

1. `get_match_dict(match_id)`
2. `scrape_match_shots(match_id)`
3. `scrape_match_momentum(match_id)`
4. si falla, probar fallback manual del notebook `nb_03`

### 2. Backfill masivo por warnings

La fuente para decidir qué reintentar ya está en:

- `gronestats/data/Liga 1 Peru/<season>/dashboard/current/validation.json`

Conviene armar un backfill por lista de `match_id` faltantes para:

- `shotmap`
- `momentum`
- `heatmaps`
- `average_positions`

sin reconstruir toda la temporada.

### 3. Criterio de cierre del warning

Separar dos casos:

- `missing_from_run`
  - el recurso existe hoy y se puede reintentar con `ScraperFC`
- `missing_from_source`
  - el endpoint responde `404` y no vale seguir reintentando indefinidamente

Esto permitiría que el pipeline deje de tratar todos los warnings iguales.

### 4. Mejor punto de integración

Si se implementa un backfill automático, debe salir desde el loader productivo:

- `gronestats/processing/data_loader_unprep.py`

y no desde notebooks.

Los notebooks deben quedar como:

- diagnóstico
- exploración
- validación manual de casos raros

## Recomendación operativa inmediata

Prioridad alta:

- backfill dirigido de `shotmap` para `2022-2023`, donde todavía hay partidos que podrían recuperar tiros si el endpoint sigue vivo

Prioridad media:

- reintento dirigido de `momentum` en `2024-2026`, pero marcando explícitamente los `404` como ausencia real del origen si se repiten

Prioridad baja:

- insistir sobre partidos viejos donde tanto `shotmap` como `graph` devuelven `404`, porque ahí el problema ya parece ser disponibilidad histórica del recurso en SofaScore

## Siguiente implementación sugerida

Crear un comando dedicado, por ejemplo:

`python -m gronestats.processing.backfill_optional_sheets --season 2023 --sheet shotmap --match-ids 11018862,11018863`

Ese comando debería:

- leer los warnings actuales
- reintentar solo los `match_id` faltantes
- sobrescribir o completar `Sofascore_<match_id>.xlsx`
- volver a correr `build-staging -> publish`
- distinguir `404` persistente de error transitorio
