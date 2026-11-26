# Plan para completar los datos faltantes

Estado al **2026-11-25**. Es un diagnóstico y un plan: **no se ha scrapeado nada** para producirlo (todo salió de archivos locales y de leer el código de ScraperFC en GitHub).

## 1. Lo que hay que saber de ScraperFC

| Hecho | Evidencia |
|---|---|
| **ScraperFC es el cliente de SofaScore, no una alternativa a SofaScore.** Cada llamada de su módulo `Sofascore` pasa por `botasaurus_browser_get_json`: abre un Chrome (botasaurus) y le pide el JSON a `api.sofascore.com` | `sofascore.py` de la v4.5.0 en `oseymour/ScraperFC` |
| **Tu pipeline ya usa ScraperFC.** `data_loader_unprep.py` y `optional_sheet_backfill.py` importan `ScraperFC.sofascore`; `sofascore_session.py` reemplaza su transporte porque el original recibía 403 | Código del repo |
| **Para la Liga 1 de Perú, ScraperFC solo soporta SofaScore** (`Peru Liga 1: SOFASCORE: 406`). No hay FBref, Transfermarkt, Capology ni Understat para tu liga | `comps.yaml` de ScraperFC |
| **ScraperFC tiene hoy el mismo bloqueo.** El issue #93 (junio 2026, abierto) reporta `{'error': {'code': 403, 'reason': 'challenge'}}` | GitHub |
| **Actualizar de la 3.4.0 (instalada) a la 4.5.0 (abril 2026) no arregla el bloqueo.** La 4.5.0 sigue usando botasaurus; sus novedades son ligas nuevas. El punto de parche que usa tu repo (`sofascore_module.botasaurus_browser_get_json`) sigue existiendo | Notas de la release v4.5.0 y código |
| El transporte que **sí funcionó** en tu proyecto es la **sesión visible y persistente** de `sofascore_session.py` | Notas del proyecto (octubre 2026) |

**Conclusión:** no hay manera de obtener datos de SofaScore sin conectarse a SofaScore. Lo que se puede decidir es *cuánto* y *cómo*, y reducirlo al mínimo.

## 2. Qué falta de verdad, por temporada

Partidos terminados en el maestro → con workbook de detalle descargado → publicados en el bundle:

| Temporada | Maestro | Con detalle | En el bundle | Hallazgo |
|---|---|---|---|---|
| 2022 | 348 | 348 | 348 | Completa, **sin fechas** (el maestro no tiene columna `fecha` ni existe maestro crudo) |
| 2023 | 342 | 336 | 342 | **6 partidos del Apertura sin detalle**; **sin fechas**; el Clausura tiene 169 de 171 (rondas 3 y 8 con 8 partidos) |
| 2024 | 306 | 306 | 306 | Completa, con fechas |
| 2025 | 333 | 333 | 333 | Completa, con fechas (ver nota sobre Binacional) |
| 2026 | 261 | **177** | **72** | **84 partidos sin detalle** (72 Apertura, 12 Clausura); **105 workbooks ya descargados no se procesaron**; el maestro llega al 2026-10-18 |

Hojas opcionales (ya se intentó recuperarlas en 2024, 2025 y 2026): quedaron como **`missing_from_source`** (1, 6 y 1 partidos): SofaScore no las tiene, no se pueden obtener scrapeando. En 2022 y 2023 faltan algunas hojas (por ejemplo posiciones medias en 44 partidos de 2022) y no se intentó recuperarlas.

**Heatmaps de 2026:** la hoja venía **sin filas** (se omitieron adrede para reducir el riesgo de bloqueo). **Resuelto el 2026-11-26** (sección 9): 306 de 306 partidos con heatmap. La tabla de arriba describe el estado del 2026-11-25.

> **Corrección importante sobre el Clausura 2025.** Antes lo di por «incompleto (158 de 171)». Probablemente **no falta nada**: Deportivo Binacional aparece con solo 5 partidos en ese torneo y a otros 13 equipos les falta exactamente uno (el que debían jugar contra Binacional). Universitario figura con 17 partidos y 40 puntos, que coincide con la imagen del umbral; con un partido más habría superado esa cifra. **Confirmado por Alvaro (2026-11-25):** Deportivo Binacional descendió administrativamente a mitad del torneo y no jugó el Clausura. No faltan datos ni es un fallo de scraping. Por eso «partidos que le quedan = equipos − 1» es incorrecto en ese torneo: hay que usar los partidos programados de cada equipo en el calendario.

## 3. Qué se resuelve sin tocar la red

1. ~~**2026: reprocesar lo ya descargado.**~~ **Hecho (2026-11-26)** con `--no-scrape`: el bundle pasó de 72 a 177 partidos con detalle (306 en `matches`). Sin `--no-scrape`, el pipeline scrapea todo workbook que falte (ver sección 8).
2. **Niveles de competitividad:** resuelto (ver `datos-de-apoyo/nivel_competitividad_faltante.csv`): los 7 equipos son «Descenso» y los 15 restantes heredan el nivel de 2024-2026.
3. **Altitud y publicación de columnas avanzadas** (157 frente a 16): trabajo manual y de pipeline, sin scraping.
4. ~~**Coordenadas y jugador de los tiros (defecto del pipeline).**~~ **Corregido y republicado 2024-2026 (2026-11-26).** Los datos estaban en los workbooks; el pipeline no leía el formato anidado. Detalle y verificación en `coordenadas-y-orientacion.md`.

## 4. Qué requiere hablar con SofaScore

| Prioridad | Qué | Estimación | Riesgo |
|---|---|---|---|
| 1 | ~~**Actualizar la lista de partidos de 2026**~~ **Hecho (2026-11-26)**, ver sección 8 | — | — |
| 2 | ~~**Detalle de los 129 partidos de 2026 sin workbook**~~ **Hecho (2026-11-26)**, ver sección 9 | — | — |
| 3 | ~~**Fechas de 2022 y 2023**~~ **Hecho (2026-11-26)**: 25 llamadas, ver sección 10 | — | — |
| 4 | ~~**Detalle de los 6 partidos del Apertura 2023**~~ **No existe en origen**: son resultados administrativos 3-0; ver sección 10 | — | — |
| 5 | ~~**Heatmaps de 2026**~~ **Hecho (2026-11-26)**: 229 partidos, 41 llamadas cada uno, sin bloqueos; ver sección 9 | — | — |

Reglas heredadas del diseño de octubre: tandas pequeñas, parar al primer 403 o `challenge`, un libro de registro por partido (`pendiente / ok / vacío / bloqueado`), sin reintentos en bucle y siempre con la sesión persistente de `sofascore_session.py`.

## 5. Lo que NO se puede conseguir de SofaScore
Eventos con coordenadas (pases, take-ons, zonas defensivas), xG por tiro o por jugador, minuto de entrada y salida de suplentes y fotos/escudos de mayor resolución. Para eso hace falta otra fuente (sin identificar para la Liga 1).

**Por verificar con una sola petición:** el endpoint `/event/{id}/lineups`, que ScraperFC ya consulta pero del que solo lee los jugadores, podría traer la **formación declarada** de cada equipo. Si existiera, sustituiría al conteo D-M-F.

## 6. Qué hace falta de Alvaro antes de scrapear nada
1. **Autorización explícita** para abrir la sesión visible de Chrome de `sofascore_session.py` (el único transporte que funcionó). ScraperFC no evita abrir SofaScore.
2. **Prueba mínima propuesta:** una petición a la lista de partidos y una a las alineaciones de un partido, con parada inmediata ante cualquier bloqueo.
3. **Decisión sobre los heatmaps de 2026:** omitirlos (recomendado), limitarlos a jugadores con muchos minutos o hacerlos todos en tandas autorizadas.
4. ~~Confirmar lo de Binacional~~ (confirmado, ver arriba).

## 7. Prueba autorizada: resultado (2026-11-25)
Alvaro autorizó pruebas, **sin heatmaps**. Se hicieron **2 peticiones de solo lectura** con `sofascore_session.py` (1 intento por petición, pausa de 2,5 s, parada ante el primer bloqueo, navegador cerrado al terminar). Script: `prototipos/sofascore_prueba_minima.py`; resultados en `datos-de-apoyo/pruebas-sofascore/`.

| Petición | Resultado |
|---|---|
| Alineaciones de un partido que ya teníamos (Alianza Lima contra Cusco FC, ronda 1 de 2025) | **Sin bloqueo.** Trae la **formación declarada**: local `4-1-4-1`, visita `4-2-3-1` (campo `formation`), que ScraperFC descarta |
| Lista de partidos de 2026 (página 0 de los más recientes) | **Sin bloqueo.** 30 partidos del 2026-11-01 al 2026-11-22 (25 terminados, 5 aplazados), **ninguno en tu maestro**; hay más páginas |

**Qué implica:** (1) el transporte actual funciona hoy; (2) la formación declarada existe en SofaScore para cada partido: descargar las alineaciones de todos los partidos costaría **una petición por partido**; (3) el maestro de 2026 está desactualizado al menos desde el 2026-10-18.

**Sigue sin autorización:** actualizar el maestro completo, descargar detalles de partidos y cualquier heatmap.

## 8. Maestro de 2026 actualizado (2026-11-26)
Alvaro autorizó actualizar el maestro. Se ejecutó `data_loader_unprep -l "Liga 1 Peru" -y 2026 --skip-details` con `GRONESTATS_SOFASCORE_ATTEMPTS=2` (como máximo 2 intentos por llamada, parada ante un bloqueo): el listado de partidos más una consulta de cabecera por partido (fecha, estadio, árbitro, técnicos). **Sin bloqueos, sin detalles de jugadores y sin heatmaps.** Se guardó antes una copia del maestro previo en `datos-de-apoyo/maestro_2026_pre_refresco_2026-11-26.xlsx`.

| | Antes | Ahora |
|---|---|---|
| Partidos | 261 | **306** (sin duplicados ni desaparecidos) |
| Apertura | 153 (rondas 1-17) | 153 (rondas 1-17) |
| Clausura | 108 (rondas 1-12) | **153 (rondas 1-17)**: las 45 novedades son las rondas 13 a 17 |
| Fecha máxima | 2026-10-18 | **2026-11-22** |
| Con marcador | 261 | 306 |

**Reprocesado sin scrapear:** el pipeline de 2026 corrió con el interruptor nuevo `--no-scrape`, que omite la llamada a `scrape_match_details` y **no borra** los workbooks incompletos (el flujo normal los borra antes de re-scrapear). Quedó registrado en el manifiesto (`no_scrape: true`, `scrape_skipped: true`). El bundle de 2026 pasó a 306 partidos en `matches`, 177 con detalle (4.906 tiros, 7.049 filas de `player_match`, 543 jugadores). Se publicaron `dashboard` y `fantasy` para mantener la regla del repo de que lo publicado coincide con el warehouse en ambos destinos (`test_published_targets_match_warehouse_exports_by_row_count`).

**Pendiente, sin autorización:** los **129 partidos sin workbook** (84 anteriores + 45 nuevos). Aparecen como advertencias de la validación (`player_stats`, `team_stats`, `average_positions`, `shotmap` ausentes en 129 partidos; `heatmaps` en 229).

**Cuidado con los técnicos (`manager_home` / `manager_away`):** SofaScore devuelve el técnico **actual del equipo al consultar**, no el del partido. Por eso cada equipo tiene un único técnico en toda la tabla, y el refresco reescribió 47 filas locales y 44 visitantes de Clausura (rondas 6-12) con el técnico de hoy (por ejemplo Alianza Lima: Pablo Guede → Salomón Libman en todas sus filas). Si el análisis por técnico llega a hacer falta, hay que pedir los técnicos por partido (endpoint de partido o alineaciones) y no fiarse de esta columna. Además un partido cambió de estadio (ronda 7 Grau contra Melgar: «Estadio Miguel Grau» → «Estadio Municipal Ambrosio Maco Arroyo») y dos partidos del Clausura con Moquegua no traen estadio.

**Corrección de un dato de esta nota:** el log antiguo de `bootstrap-raw` contaba como «faltantes» todos los partidos ausentes de la carpeta *legacy* (306), no los que de verdad faltan en `raw/details` (129). El mensaje de `--no-scrape` ya informa el número real.

**Cómo repetir sin scrapear:** `py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --mode full --publish-target all --no-scrape`.

## 9. Detalles y heatmaps de 2026 completados (2026-11-26)
Alvaro autorizó scrapear los 129 detalles faltantes sin heatmaps y después traer los heatmaps por tandas pequeñas.

**Ejecutor:** `gronestats/processing/sofascore_batches.py` (`details` y `heatmaps`). Envuelve el transporte con un `BlockGuard`: un 404 es dato ausente legítimo y **cualquier otro error es un bloqueo**; desde el primero no se hace ninguna llamada más, y tres fallos seguidos sin progreso también detienen la ejecución. Cada partido queda en `2026/raw/scrape_ledger.jsonl` (estado, llamadas, segundos, filas por hoja), base del monitor de datos. Es reanudable. La razón de existir: `ScraperFC.scrape_heatmaps` convierte cualquier error, incluido un 403, en una lista vacía («el jugador no jugó»), de modo que un bloqueo habría guardado heatmaps vacíos que después se darían por buenos.

**Detalles:** 129 de 129 en `ok` (piloto de 3 y 126 en tandas de 5 con pausa de 20 s), **903 llamadas** (7 por partido, unos 5-7 s), sin bloqueos y sin hojas vacías salvo Heatmaps. Reprocesado con `--no-scrape` y publicados `dashboard` y `fantasy`: **306 partidos, todos con detalle**; 12.183 filas de `player_match`, 8.495 tiros (100 % con coordenadas y jugador; los goles del mapa coinciden con el marcador en 283 de 283 partidos sin autogoles), validación `passed`. Única advertencia de datos: la hoja `momentum` del partido 15362086 (404 en origen).

**Defecto de formato de heatmaps (corregido):** `scrape_match_details` y el backfill escriben la celda como lista de puntos y `parse_heatmap_payload` solo entendía el diccionario histórico, así que se publicaban 0 puntos. Ahora acepta ambos (la lista con el `player_id` de la fila). Efecto inmediato: los 77 workbooks de 2026 que ya traían heatmaps pasaron de 0 a **99.509 puntos** publicados. Orientación verificada: el heatmap medio de cada jugador coincide con su posición media (correlación 1,000 y pendiente 1,00 en x e y, local y visita, 2025 y 2026), de modo que tu `build_player_heatmap_figure` debe dibujarlos sin espejar, como ya hace.

**Heatmaps:** piloto de 2 partidos (41 llamadas cada uno, unos 25 s; 31 de 31 y 32 de 32 jugadores con minutos tienen heatmap) y después los 227 restantes en tandas de 3 con pausa de 45 s. **229 de 229 en `ok`, sin bloqueos, sin fallos y sin reintentos** (unas 41 llamadas y 25 s por partido; el ledger tiene 358 entradas: 129 de detalles y 229 de heatmaps). Reprocesado con `--no-scrape` desde `build-staging` y publicados `dashboard` y `fantasy`; validación `passed`. Solo cambió `heatmap_points`: de 99.509 a **398.936 puntos** (796 KB). Las demás tablas, dashboard y fantasy, conservan el mismo número de filas que antes del reproceso (se comparó el conteo, no el contenido).

**Verificación del bundle final:**
- **Cobertura:** 306 de 306 partidos con heatmap; 9.456 de 9.482 jugadores-partido con minutos (**99,7 %**) y ningún partido por debajo del 80 %. Los 26 restantes están repartidos en 23 partidos (máximo 2 por partido): 16 jugaron 1 minuto, 9 entre 2 y 19 y uno 72. El ledger los marca `ok` porque SofaScore no devolvió error; no se verificó si el origen los trae vacíos.
- **Rango:** x e y en 0-100, sin nulos.
- **Orientación:** sobre 9.455 pares jugador-partido, la media del heatmap contra la posición media de `average_positions` da correlación **0,9998 en x y 0,9997 en y**, con diferencia media absoluta de 0,47 unidades. Los heatmaps están en sentido de ataque (0→100) y se dibujan sin espejar, igual que las posiciones medias.
- **Tests:** `pytest tests`, 113 pasan y 2 omitidos.

**Qué queda de 2026:** el único hueco es la hoja `momentum` del partido 15362086 (404 en origen, no se puede obtener; reintentado el 2026-11-26 con el mismo resultado). Los 12 partidos «sin marcador» del maestro crudo **no son faltantes**: son aplazados cuyo cruce se jugó después con otro `match_id` (verificado el 2026-11-26: cada uno tiene su partido jugado y cada torneo suma 153 de 153). Para la próxima jornada basta `sofascore_batches details` y luego `heatmaps`, con las mismas tandas y el mismo ledger (los ya registrados se omiten).

## 10. 2022-2023 y momentum faltantes (2026-11-26)
Alvaro autorizó: «Scrapea 2022-2023 y los momentum que faltan». Se hizo con `sofascore_batches` (modos nuevos `fixtures`, `apply-fixtures` y `momentum`), sin bloqueos.

**Fechas y estadios (listado de la temporada, sin pedir partido por partido).** 12 llamadas en 2022 y 13 en 2023. El listado ya trae fecha, estado y sede de cada evento.

| | Eventos | `finished` | `postponed` | `canceled` | Con sede |
|---|---|---|---|---|---|
| 2022 | 356 | 348 | 5 | 3 | 338 |
| 2023 | 371 | 336 | 31 | 4 | 354 |

Todos los eventos traen fecha. Se volcó `fecha`, `estadio` y `ciudad` en `2022/0_Matches.xlsx` y `2023/0_Matches.xlsx` (`apply-fixtures`, sin red) y se reprocesaron ambas temporadas con `--no-scrape`. Bundle final: 348 de 348 y 342 de 342 partidos con fecha (2022-02-04 a 2022-11-13 y 2023-02-03 a 2023-11-08, hora de Lima) y estadio en 330 y 327. Los 33 sin estadio son todos partidos de local de ADT Tarma, que SofaScore no trae con sede (tres de sus partidos sí dicen Estadio Unión Tarma; no se rellenó el resto).

**Defecto del pipeline encontrado y corregido.** El primer reproceso publicó fechas dañadas (127 de 348 válidas): `normalize_finished_master` convertía `fecha` a texto y `normalize_match_datetime` la normalizaba otra vez, restando 5 horas por segunda vez y leyendo el día como mes. No aparecía en 2024-2026 porque su maestro trae `fecha` como fecha real. Ahora el maestro conserva la fecha real y la hora de Lima se aplica una sola vez (prueba en `tests/test_processing_pipeline.py`).

**Qué son los partidos sin marcador o sin detalle, revisado cruce por cruce.** Cada torneo es un todos contra todos a una vuelta de 19 equipos (171 cruces).
- **2022:** Apertura 171 de 171 y Clausura 171 de 171. Los 8 eventos no jugados (5 `postponed`, 3 `canceled`) son originales aplazados cuyo cruce se disputó después, a veces con local y visita invertidos. Completo.
- **2023 Apertura:** 171 de 171, pero **6 partidos de la fecha 3 son resultados administrativos** (3-0 o 0-3; SofaScore los marca `canceled` o `postponed`, sin repetición): 11018862, 11018863, 11018866, 11018869, 11018870 y 11034403. Suman puntos en la tabla, pero no hay datos de partido: los 5 endpoints devuelven 404 (comprobado en 3, y los otros 3 no se pidieron porque el listado ya no los marca `finished`). Por eso **no se pueden scrapear los 6 detalles que faltaban**. Los otros 27 eventos no jugados son aplazados con su repetición.
- **2023 Clausura:** 169 de 171. **Faltan dos cruces, Grau–Municipal (fecha 8, `canceled`, 2023-08-14) y Mannucci–Municipal (fecha 3, `postponed`, 2023-07-09), sin marcador y sin repetición en SofaScore.** Aquí no se trata de un cambio de fecha: el listado no trae ningún evento jugado de esos cruces. **Decisión de Alvaro (2026-11-26): esos dos cruces no se toman en cuenta en el análisis.** Fuente: Infobae, 2023-08-09 (<https://www.infobae.com/peru/2023/08/09/fpf-modifico-sancion-a-municipal-y-es-inapelable-no-jugara-fecha-8-y-perdera-puntos-contra-atletico-grau/>): el Tribunal de Licencias de la FPF **suspendió la licencia de Municipal por una fecha** (no la perdió), por lo que no jugó la fecha 8 contra Atlético Grau; la nota dice que Grau «se quedaría con los tres puntos» solo como posibilidad (como Mannucci en julio) y no habla de reprogramación. Ninguno de los dos aparece con marcador en SofaScore, así que **ya estaban fuera**: no están en el maestro limpio, no suman puntos y Municipal figura con 16 partidos en ese torneo. Si algún día se quisiera contar los 3 puntos que pudieron otorgarse a Grau y a Mannucci, habría que confirmar el resultado oficial y agregarlo como resultado administrativo.

**Momentum.** 50 hojas faltantes intentadas, una llamada cada una: 2022 (39), 2023 (3), 2024 (1), 2025 (6) y 2026 (1). **Las 50 devolvieron 404**: SofaScore no tiene el momentum de esos partidos, así que quedan `missing_from_source` (en 2022 y 2023 no se había intentado).

**Hojas que faltaban en 2022-2023 (autorizado después, 2026-11-26).** Se pidieron con los modos `team-stats`, `average-positions` y `shotmap`, una llamada por partido y hoja (posiciones medias pide además una para los nombres de equipo): 102 partidos-hoja intentados, **99 devolvieron 404** (SofaScore no las tiene), 2 entraron y 1 falló.

| Hoja | 2022 | 2023 |
|---|---|---|
| Estadísticas de equipo | 1 intentada: 404 | 2 intentadas: 1 entró (partido 11118014, 3 filas), 1 con 404 |
| Posiciones medias | 44 intentadas: 43 con 404 y 1 con error | 4 intentadas: 4 con 404 |
| Mapa de tiros | 47 intentadas: 1 entró (partido 10097776, 26 tiros), 46 con 404 | 4 intentadas: 4 con 404 |

El error es el partido 10438805 de 2022: SofaScore responde posiciones medias con las listas de jugadores vacías y ScraperFC no las soporta (`KeyError: 'player'`); queda como `error` en el registro y se reintenta solo en la próxima corrida (solo los `vacio` se omiten). En la práctica son hojas que no existen en origen: **los huecos de 2022-2023 que quedan no se pueden llenar scrapeando.**

**Segundo defecto del pipeline: se perdían las hojas scrapeadas en 2022-2023.** Esas temporadas no traen workbooks propios: cada corrida completa los **reconstruye desde los archivos por hoja del repo Legacy** (`write_legacy_split_workbooks`) y borraba cualquier hoja que ese repo no tuviera. Así se perdieron, en el primer reproceso, el mapa de tiros de 2022 y la estadística de equipo de 2023 recién descargados (el registro decía `ok` y el bundle no cambió; se detectó porque los conteos no se movieron). Ahora la reconstrucción conserva las hojas que el Legacy no trae (el Legacy sigue mandando en las suyas; sin duplicar alias como `TeamStats` y `Team Stats`), con 3 pruebas en `tests/test_processing_pipeline.py`. Las 2 hojas se volvieron a pedir (2 llamadas) y se reprocesó de nuevo.

**Estado de cada partido (`matches.status`).** El maestro de 2022-2023 ahora lleva `status` con el tipo de evento de SofaScore (`finished`, `postponed`, `canceled`) y llega al bundle. Un partido con marcador y estado `postponed` o `canceled` es un **resultado administrativo** (los 6 de la fecha 3 del Apertura 2023): suma puntos en la tabla, pero no tiene tiros ni estadísticas ni mueve ratings. `gronestats/analysis/match_status.py` define la regla; `title_race` y `xg_model` la usan. En 2024-2026 `status` queda vacío (todos los partidos se jugaron); `data_loader_unprep` lo trae desde ahora en cada refresco del maestro.

**Coordenadas de sede de SofaScore: no son confiables.** 4 de las 21 sedes de 2022-2023 llegan con latitud y longitud invertidas (Hugo Sotil Yerén, Nacional de Lima, Unión Tarma y Municipal De Bernal) y Hugo Sotil Yerén quedaba a 67 km y 3.666 m de su ubicación real (152 m). Las 4 sedes que no estaban en la tabla de altitud se midieron con OpenStreetMap y el modelo de terreno; `altitud_estadios_medida.csv` tiene ahora **33 sedes que cubren los 657 partidos de 2022-2023 con estadio**.

**Correcciones al ejecutor** (`sofascore_batches.py`, 29 pruebas): `details` ya no vuelve a pedir ni **borra** un workbook que existe pero está incompleto (con 2026 no pasó porque los 129 no tenían archivo); no pide los partidos que el listado no marca `finished`; el listado de la temporada se invalida si un bloqueo lo interrumpe a la mitad (ScraperFC lo habría tomado por el final y guardado una temporada truncada); y el corte por «tres fallos seguidos» no cuenta los 404 del momentum.

