# xG propio de GroneStats

Estado al **2026-11-26**. Módulo `gronestats/analysis/xg_model.py` (pruebas en `tests/test_xg_model.py`) que lee el bundle publicado; los resultados se escriben en `datos-de-apoyo/xg-prototipo/`. El prototipo original (`prototipos/xg_proto.py`) queda como referencia histórica. **No está integrado al pipeline**: dónde vive el xG (pipeline o API) es una decisión del spec.

Para recalcular: `py -3.11 -m gronestats.analysis.xg_model --out docs/recursos-dashboard/datos-de-apoyo/xg-prototipo`.

## Qué es y qué no es
xG **por tiro** calculado con la geometría del tiro, la parte del cuerpo y la situación de juego. Se rotula **«xG GroneStats (modelo propio)»**.
- **Excluye a propósito** lo posterior al disparo (`goal_mouth_*`, `block_coordinates`): sería xGOT y filtraría el resultado.
- **No usa** presión defensiva ni tipo de pase previo: los datos no los traen.
- Penales: constante (la conversión histórica de las demás temporadas, ≈ 76 %). Autogoles: 0. Tandas de penales: 0 y se excluyen de las tablas por jugador (10 tiros).

## Qué se puede reutilizar del repo que pasaste

El repo `eddwebster/football_analytics` es un **índice** de recursos (README de 3.400 líneas, 1,1 GB) y **no tiene licencia**: no se puede copiar su código. Sus enlaces de xG llevan a otros repos; esto dicen sus licencias:

| Repo | Licencia | ¿Copiar código? | Qué aporta |
|---|---|---|---|
| `ML-KULeuven/soccer_xg` | Apache-2.0 | Sí, con atribución | Variables, calibración (`calibration.py`) y métricas (`metrics.py`); requiere SPADL y sklearn |
| `andrewRowlinson/expected-goals-thesis` | MIT | Sí | Modelos, SHAP, **tiros sintéticos** para anclar los extremos, simulación de partidos desde xG |
| `christiangilson/xGils` | MIT | Sí | `xG.py`: variables geométricas, calibración y métricas (usa sklearn y statsmodels) |
| `mcavs/Decomposition-of-Expected-Goal-Models` | MIT | Sí (es R) | Análisis de modelos |
| `JanVanHaaren/how-to-expected-goals`, `iandragulet/xG_Model_Workflow`, `KubaMichalczyk/Expected-Goals-Model`, `Dato-Futbol/xg-model`, `devinpleuler/research`, `CleKraus/soccer_analytics` | **Sin licencia** | **No** | Solo como lectura |

**Decisión:** no se copió código. Todos los reutilizables dependen de sklearn, statsmodels o socceraction (no instalados) y están pensados para StatsBomb o Wyscout, con muchas más variables que las tuyas. Se **implementó con numpy y scipy**, tomando la metodología (variables geométricas, calibración, validación por temporada). Si más adelante se instala scikit-learn o LightGBM, la tesis de Rowlinson (MIT) es el mejor punto de partida para un modelo de árboles.

## Datos
**41.386 tiros** de 2022 a 2026 (8.012, 8.485, 7.862, 8.532 y 8.495). Desde el arreglo de `build_shot_events_curated` el bundle ya trae `x`, `y` y jugador en el **100 %** de los tiros; el prototipo todavía los rescataba de `staging` y ahora el módulo lee `shot_events.parquet` directo. Los goles del mapa de tiros coinciden con el marcador en el 100 % de los partidos con mapa y sin autogoles en 2023-2026 y en el 99,6 % en 2022 (302 de 348 partidos tienen mapa; los otros 46 no lo tienen en origen: se volvió a pedir y SofaScore respondió 404).

## Modelo
Regresión logística con regularización L2. Variables: distancia y ángulo a portería (con los postes de la cancha Opta), distancia al cuadrado y logarítmica, cabeza (y su interacción con la distancia), «otra parte del cuerpo» y la situación (jugada con asistencia como base; córner, jugada a balón parado, tiro libre —con su interacción con la distancia—, jugada de saque de banda y jugada sin asistencia, `regular`). **Validación dejando una temporada fuera**: cada temporada se predice con un modelo que no la vio, y el xG de cada tiro sale de ese modelo.

**`fast-break` quedó fuera el 2026-11-26.** SofaScore amplió la etiqueta en 2025: pasó de 2-3 % de los tiros (2022-2024, unos 200 por temporada) a 7,1 % en 2025 y 8,8 % en 2026 (590 y 733 tiros), y su tasa de gol cayó de 20-29 % a 13 % con las mismas distancias. Con la variable, el modelo trataba como contraataque peligroso a tiros que antes eran «jugada con asistencia» y el xG de 2025 y 2026 salía un 7 % por encima de los goles. Quitarla estrecha el sesgo (xG sobre goles por temporada: de 0,94-1,08 a 0,96-1,04) y mejora la pérdida de 2025 y 2026 a cambio de unas milésimas en 2022-2024 (0,001 a 0,003).

## Resultados (fuera de muestra)

| Temporada | Tiros del modelo | Pérdida logarítmica: modelo | solo distancia | constante | AUC | xG total | Goles |
|---|---|---|---|---|---|---|---|
| 2022 | 7.870 | 0,250 | 0,262 | 0,303 | 0,798 | 683 | 711 |
| 2023 | 8.350 | 0,249 | 0,260 | 0,298 | 0,791 | 741 | 736 |
| 2024 | 7.710 | 0,244 | 0,255 | 0,300 | 0,801 | 661 | 684 |
| 2025 | 8.361 | 0,253 | 0,264 | 0,300 | 0,784 | 775 | 743 |
| 2026 | 8.344 | 0,253 | 0,265 | 0,302 | 0,791 | 763 | 748 |

- **Calibración:** por deciles de xG (4.061 tiros cada uno), el xG medio y la tasa real de gol quedan cerca. Decil más bajo: 0,011 contra 0,013; decil más alto: 0,346 contra 0,339. Las mayores diferencias son 0,012 (octavo decil: 0,109 contra 0,121) y 0,011 (quinto: 0,047 contra 0,036, el modelo da de más); el resto está dentro de 0,007.
- **Contra el xG de equipo del proveedor** (suma de xG de los tiros por equipo y partido): correlación **0,88 en 2023, 0,90 en 2024 y 2025 y 0,91 en 2026**. El xG propio es entre un 1 % y un 8 % menor que el del proveedor (cociente 0,94, 0,94, 0,99 y 0,92); 2022 no tiene xG de proveedor.
- Los tiros de partidos administrativos (estado `postponed` o `canceled` en `matches.status`) se descartan al cargar; hoy no hay ninguno porque esos partidos no tienen mapa de tiros.
- Los números de 2022-2025 casi no se movieron al sumar 2026 (por ejemplo 2024: 0,241 antes y 0,244 ahora, tras quitar `fast-break`).

## Por jugador
- `xg_jugador_temporada.csv`: partidos, tiros, xG, xG sin penales, goles, xG por tiro y goles − xG (489, 475, 472, 504 y 497 jugadores por temporada).
- `xg_jugador_partido.csv`: lo mismo por partido.
- `xg_tiros.parquet`: xG de cada tiro y su origen (modelo, penal, autogol, tanda).
- `xg_validacion.csv`: la tabla de arriba.

Ejemplos de 2026 (jugadores con 40 o más tiros): Eryc Castillo (Alianza Lima) 23 goles con 15,9 de xG (**+7,1**), Carlos Garcés (Cienciano) 18 con 13,8 (+4,2), Raúl Ruidíaz (Grau) 3 con 8,3 (−5,3). Con estas muestras el goles − xG de una temporada es ruidoso: mostrar siempre el número de tiros.

## Límites y siguientes pasos
- **Sin presión ni asistencia:** el modelo no distingue un tiro con el portero solo de uno cerrado por un defensa.
- **Las etiquetas de SofaScore cambian entre temporadas** (`fast-break` fue el caso). Antes de usar otra variable categórica, comparar su frecuencia y su tasa de gol por temporada.
- **Pendiente:** tiros sintéticos para anclar extremos (Rowlinson) y probar árboles de decisión con LightGBM.
- **Integración:** el xG por tiro y las tablas por jugador están listos para publicarse en el bundle. Queda decidir en el spec si el cálculo vive en el pipeline (recomendado: el modelo es chico y la validación por temporada exige ver todas) o en la API.
