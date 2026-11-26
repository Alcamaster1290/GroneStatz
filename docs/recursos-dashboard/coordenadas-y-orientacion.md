# Coordenadas y orientación: lo verificado con el código local

Verificado el **2026-11-25** imprimiendo valores con las funciones de `gronestats/dashboard` (el código funcional de Streamlit) y con los parquets del proyecto. Script: `prototipos/verificar_orientacion_con_codigo_local.py`.

> **Regla de trabajo:** cualquier supuesto sobre coordenadas se imprime y se contrasta con este código **antes** de usarlo. Si algo no coincide, manda el código local.

## Convenciones confirmadas

| Dato | Convención | Evidencia (2023, tiros con coordenadas completas) |
|---|---|---|
| **Tiros** `x` | Distancia a la línea de fondo del **arco que se ataca** (0 = línea de gol), en unidades Opta (0–100 del largo). **Igual para local y visita** | Goles: `x` medio **10,6 local y 10,6 visita** (509 y 315 goles). Penales: **11,5 en ambos lados**, el punto de penal de Opta |
| **Tiros** `y` | Ancho de 0 a 100, centrado en 50 | Goles: `y` medio 50,2 y 50,5; penales 50,0 |
| **Posiciones medias** `average_x` | **Dirección de ataque** (0 = arco propio, 100 = arco rival) | Arqueros ≈ 9; defensas ≈ 42; medios ≈ 58; delanteros ≈ 66 |
| **Relación** | **Tiros y posiciones usan sentidos opuestos**: `x_posición ≈ 100 − x_tiro` | Delanteros: posición media 66,2, tiran desde `x` = 13,7 (distancia al arco) |
| Escala | Cancha Opta 100×100 se dibuja como 105×68 m (`VerticalPitch(pitch_type="opta")`) | `pitch.py:22-32` |
| Portería | Postes en `y` = 44,2 y 55,8 (Opta) | Estándar de mplsoccer para `opta` |
| Punto de penal | 11,5 unidades de la línea de fondo (= 12,1 m, no 11 m: es una proporción de Opta) | Penales de los datos |

**Consecuencia:** cualquier pantalla que combine tiros y posiciones (red de compañeros, figura del equipo, zonas) debe convertir uno de los dos (`100 − x`) o la mezcla sale invertida.

## Qué hace tu código (con referencias)

| Dónde | Qué hace |
|---|---|
| `gronestats/dashboard/metrics.py:1426-1435` (`build_match_shot_events`) | `display_x/y` = crudo para el **local**; `100 − x` y `100 − y` para la **visita** |
| `gronestats/dashboard/views/pitch.py:178-182` | Mismo reflejo para las posiciones medias de la visita |
| `gronestats/dashboard/views/pitch.py:22-32` | Cancha vertical `opta`: x va de abajo (0) a arriba (100) |
| `gronestats/dashboard/data.py:335-366` (`normalize_shot_events`) | Convierte tipos y `is_home` a booleano; **no** toca coordenadas |

Resultado impreso de `build_match_shot_events` (partido 11034404): un gol de la visita con `x` crudo 7,0 se dibuja en **93,0**; los del local (9,8 y 7,7) quedan en 9,8 y 7,7. Es decir, **cada equipo aparece en el arco que ataca, en lados opuestos**.

> **Observación sobre el texto, no sobre la lógica:** el comentario de `metrics.py:1430-1431` y la nota de `:1467` dicen que se refleja a la visita «para comparar ambos ataques hacia la misma portería». Con los datos, el efecto es el contrario (arcos opuestos). El comportamiento visual es correcto; lo que conviene revisar es el texto.

## Defectos del pipeline descubiertos al verificar

`gronestats/processing/pipeline.py:1434-1503` (`build_shot_events_curated`) lee solo `x`, `y`, `z` y el id del jugador desde `id.1`. SofaScore cambió el formato del shotmap durante 2024-2025: los workbooks nuevos traen **`playerCoordinates`** y **`player`** como diccionarios anidados. Consecuencia, **sin que falten datos en los workbooks**:

| Temporada | Tiros | Con coordenadas en el parquet curado | Con jugador en el parquet curado |
|---|---|---|---|
| 2022 | 7.986 | 100 % | 100 % |
| 2023 | 8.485 | 100 % | 100 % |
| 2024 | 7.862 | 88,6 % | 88,6 % |
| 2025 | 8.532 | **15,1 %** | **4,9 %** |
| 2026 | 1.797 | **0 %** | **0 %** |

Leyendo los diccionarios anidados se recupera el **100 %** de coordenadas y de jugadores. Comprobaciones de la recuperación: el 99,9 % de los tiros de 2025 con jugador aparece en las estadísticas de ese partido y el 100 % juega en el equipo que tira; en 2024-2026 los goles del mapa de tiros coinciden con el marcador en el 100 % de los partidos sin autogoles (2022: 86,3 %, porque 47 partidos no tienen shotmap; 2023: 96,9 %).

**El formato anidado usa el mismo sistema de coordenadas que el plano** (verificado dentro de 2024 y 2025): ambos dan el punto de penal en `x` = 11,5 e `y` = 50,0, medias de `y` de 49,8 a 50,1, percentiles 10 y 90 de `x` casi iguales (5,6-6,6 y 28,4-29,1) y ningún partido mezcla los dos formatos. No hace falta convertir nada al leerlo.

## Arreglo aplicado (2026-11-26)

`build_shot_events_curated` ahora lee `playerCoordinates` y `player` (diccionarios o texto de diccionario, con `parse_nested_dict`) y la variante de columna `id_1` de algunos workbooks de 2025. Solo rellena los huecos: **el valor plano sigue mandando** cuando existe. Pruebas en `tests/test_processing_pipeline.py` (formato plano como regresión, anidado, mezcla, `id_1`, valores malformados).

| Temporada | Coordenadas antes → después | Jugador antes → después | Tiros | Valores ya publicados que cambian |
|---|---|---|---|---|
| 2024 | 88,6 % → 100 % | 88,6 % → 100 % | 7.862 | 0 de 6.969 |
| 2025 | 15,1 % → 100 % | 4,9 % → 100 % | 8.532 | 0 de 1.287 |
| 2026 | 0 % → 100 % | 0 % → 100 % | 4.906 en 177 partidos | (no había) |

Se republicaron 2024 y 2025 desde el staging existente (`--from-phase build-curated`, sin scrapear) y 2026 con `--no-scrape`. En 2024 y 2025 las otras 10 tablas del bundle salieron **idénticas** y solo cambiaron las 8 columnas esperadas de `shot_events`; validación `passed` en las tres.

**Verificado con tu código de Streamlit tras el arreglo** (`normalize_shot_events` y `build_match_shot_events`, filas recuperadas frente a filas planas de siempre): el penal cae en `x` = 11,5 en todos los grupos y en el 2026 publicado (n = 35 local, 26 visita); los goles sin penal quedan en torno a `x` = 8-9; `y` en torno a 50; tu función espeja solo a la visita (`display_x = 100 − x`). En 2026 los goles del mapa coinciden con el marcador en 159 de 159 partidos sin autogoles.

**Un test lo defendía:** `test_published_2026_shot_events_support_goal_mouth_only_mode` exigía `has_pitch_map is False` sobre el 2026 publicado, es decir, daba por bueno el defecto. Se renombró a `..._support_pitch_and_goal_mouth_maps` y ahora exige `True`; el modo "solo portería" sigue cubierto por la prueba sintética `test_build_match_shot_events_parses_goal_mouth_only_payloads_and_invalid_values`.
