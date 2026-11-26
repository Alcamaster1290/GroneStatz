# Importancia de los partidos y probabilidad de campeonar

Recalculado el **2026-11-26** con el calendario completo de 2026 y con fechas reales en las cinco temporadas. Módulo `gronestats/analysis/title_race.py` (pruebas en `tests/test_title_race.py`); salidas en `datos-de-apoyo/title-race/`. Sustituye a los prototipos `elo_title.py` y `champ_state.py`, que quedan como referencia.

Para recalcular:
```
py -3.11 -m gronestats.analysis.title_race --altitude-table docs/recursos-dashboard/datos-de-apoyo/altitud_estadios_medida.csv --out docs/recursos-dashboard/datos-de-apoyo/title-race
```

## Qué cambió respecto al primer cálculo
1. **2026 completo:** 306 partidos, 17 jornadas por torneo hasta el 2026-11-22. Antes solo había 8 jornadas del Apertura.
2. **Fechas reales en 2022 y 2023** (obtenidas del listado de SofaScore). Antes se ordenaba por jornada, y un partido aplazado contaba en su jornada aunque se jugara semanas después.
3. **«Partidos que le quedan» = los programados de ese equipo, según el calendario oficial.** En el Clausura 2025 los 5 partidos de Binacional los anuló la federación (`status = annulled`): no puntúan ni cuentan en el calendario de nadie y los demás equipos tienen 17; Deportivo Municipal en el Clausura 2023 tiene 16 (sus dos cruces adjudicados no son partidos del bundle; la tabla oficial los cuenta aparte, en `ajustes_tabla.csv`). Con «equipos − 1» todo esto salía mal.
4. **La probabilidad se calcula tras cada partido de cada equipo** (`k` = partidos que ese equipo lleva jugados), no por jornada. El estado del torneo es el de la fecha en que terminó ese partido.
5. **Resultados administrativos** (los 6 partidos 3-0 de la fecha 3 del Apertura 2023, sin partido jugado) suman puntos pero no mueven los ratings. Se reconocen por `matches.status` del bundle (`postponed` o `canceled` con marcador); da exactamente los mismos resultados que leerlos del listado de SofaScore.
6. **Altitud en metros** (diferencia entre el estadio y la sede habitual del visitante, con la tabla medida de 33 sedes) en lugar de un sí/no.

## Puntos del campeón
Los puntos que salen de los datos coinciden con tu imagen en **los 9 torneos que trae** (2022 a Apertura 2026), incluido el Apertura 2026 que antes no se podía verificar.

| Torneo | Campeón | Puntos |
|---|---|---|
| Apertura 2022 | Melgar | 41 |
| Clausura 2022 | Alianza Lima | 42 |
| Apertura 2023 | Alianza Lima | 42 |
| Clausura 2023 | Universitario | 39 |
| Apertura 2024 | Universitario | 40 |
| Clausura 2024 | Universitario | 37 |
| Apertura 2025 | Universitario | 39 |
| Clausura 2025 | Universitario | 40 |
| Apertura 2026 | Alianza Lima | 40 |
| **Clausura 2026** | **Sport Huancayo** | **37** (Sporting Cristal 35 con mejor diferencia de gol) |

El Clausura 2026 no está en la imagen; sale de los datos. Con él, la media de los 10 torneos sigue en 39,7 y el rango es 37-42.

## Importancia (derrotas permitidas)
`derrotas permitidas = ⌊(3 × partidos que le quedan − puntos que le faltan para el umbral) ÷ 3⌋`. Los partidos que le quedan incluyen el que está por jugar. Umbral de referencia: **40**.

**«Fuera de alcance» solo si no llega ni a 37 puntos** (el campeón más bajo observado: Clausura 2024 y Clausura 2026). Si con 40 ya no llega pero con 37 sí, el partido se clasifica con el umbral 37 y lleva un asterisco (`threshold_used = 37`). Es la regla que aprobaste el 2026-11-26; la motivó Sport Huancayo, que ganó el Clausura 2026 con 37 y con umbral 40 aparecía «Fuera de alcance» en sus últimos 3 partidos (28 puntos con 3 por jugar), cuando con 37 era «Crítica» y ganó los tres.

3.236 partidos de equipo (10 torneos). Con umbral 40 y piso 37: Baja 617, Media 368, Alta 368, **Crítica 723**, **Fuera de alcance 1.158** y Asegurado 2. El piso rescató **336** partidos de «Fuera de alcance»: todos pasan a Crítica, porque con 40 les faltaban hasta 3 puntos más de los que podían sumar y con 37 les sobran entre 0 y 2 (Crítica: de 387 a 723).

Sensibilidad al umbral **sin piso** (partidos de equipo por banda), para ver cuánto pesa la elección:

| Banda | Umbral 37 | Umbral 40 | Umbral 42 |
|---|---|---|---|
| Asegurado | 13 | 2 | 0 |
| Baja (3 o más) | 985 | 617 | 479 |
| Media (2) | 365 | 368 | 309 |
| Alta (1) | 379 | 368 | 348 |
| Crítica (0) | 336 | 387 | 335 |
| Fuera de alcance | 1.158 | 1.494 | 1.765 |

Las bandas Baja, Media y Alta casi no cambian con el piso; el efecto está en «Fuera de alcance» (1.494 contra 1.158) y en Crítica (387 contra 723).

Ejemplo (Alianza Lima, Apertura 2026, umbral 40, partido a partido): Baja ×7, Media ×2, Alta ×5 y Crítica ×3 en las últimas tres jornadas; terminó con 40.

## Probabilidad de campeonar
Elo partido a partido en orden de fecha y simulación Monte Carlo (3.000 simulaciones) del resto del torneo desde cada estado, con incertidumbre de rating σ = 120. El desempate es diferencia de gol.

Parámetros ajustados con 2023-2025 (2022 solo calienta los ratings): **K = 20, ventaja de local = 70, altitud = 60 puntos Elo por cada 1.000 m, regresión a la media = 0, empate máximo = 0,32**. Un partido con 3.300 m de diferencia (Cusco contra un equipo de costa) suma unos 200 puntos Elo a los 70 de local.

**Fuera de muestra (pérdida logarítmica del resultado 1X2, más baja es mejor):**

| Temporada evaluada | Elo con altitud | Elo sin altitud (reajustado) | Frecuencias sin ratings | Mejora de la altitud | Mejora sobre las frecuencias |
|---|---|---|---|---|---|
| 2025 (ajuste 2023-24) | 0,979 | 0,989 | 1,053 | +1,09 % | +7,1 % |
| 2026 (ajuste 2023-25) | 0,976 | 0,995 | 1,028 | +1,90 % | +5,1 % |

- **La altitud ahora sí aporta.** En el primer cálculo, un efecto binario de +80 no mejoraba fuera de muestra. Con los metros reales mejora en las dos temporadas evaluadas. El ajuste tiene su mínimo dentro de la rejilla (con 80 puntos por 1.000 m o más, el ajuste empeora). Cautela: 60 puntos por 1.000 m es un efecto grande y se ajustó con tres temporadas; los 33 partidos de local de ADT Tarma (sin sede en SofaScore) no reciben efecto de altitud.
- El modelo sin altitud necesita una ventaja de local de 130 para compensar; con altitud baja a 70.

**Probabilidad asignada al campeón real tras su partido k:**

| Torneo | Campeón | k = 0 | k = 6 | k = 9 | k = 12 | k = 15 |
|---|---|---|---|---|---|---|
| Apertura 2022 | Melgar | 6 % | 4 % | 2 % | 15 % | 59 % |
| Clausura 2022 | Alianza Lima | 9 % | 32 % | 8 % | 23 % | 26 % |
| Apertura 2023 | Alianza Lima | 13 % | 29 % | 67 % | 89 % | 99 % |
| Clausura 2023 | Universitario | 10 % | 22 % | 26 % | 19 % | 36 % |
| Apertura 2024 | Universitario | 15 % | 38 % | 41 % | 40 % | 74 % |
| Clausura 2024 | Universitario | 21 % | 21 % | 23 % | 47 % | 66 % |
| Apertura 2025 | Universitario | 25 % | 27 % | 63 % | 24 % | 63 % |
| Clausura 2025 | Universitario | 23 % | 27 % | 42 % | 91 % | 100 % |
| Apertura 2026 | Alianza Lima | 14 % | 42 % | 31 % | 61 % | 97 % |
| **Clausura 2026** | **Sport Huancayo** | **1 %** | **0 %** | **2 %** | **11 %** | **12 %** |

El favorito del modelo es el campeón real tras el partido 6 en 4 de 10 torneos, tras el 9 en 3 de 10, tras el 12 en 4 de 10 y tras el 15 en 8 de 10. El **Clausura 2026 es el torneo más sorprendente de los diez**: el campeón nunca superó el 12 % y llegó a 0 % tras seis partidos.

## Archivos (`datos-de-apoyo/title-race/`)
- `importancia_equipo_partido.csv` y `.parquet`: una fila por equipo y partido (estado justo antes del partido): puntos, partidos que le quedan, puntos que le faltan, derrotas permitidas y banda.
- `probabilidad_titulo.csv` y `.parquet`: una fila por equipo tras cada uno de sus partidos (`k`, puntos, rating y `p_title`), más la fila `k = 0` antes del primer partido (`match_id` vacío).
- `umbral_campeon_medido.csv`: campeón y puntos de cada torneo, contra la imagen.
- `parametros_elo.json`: parámetros, pérdidas dentro y fuera de muestra.

## Límites
- σ = 120 se calibró con pocos torneos (10); sin ella el modelo era sobreconfiado.
- No ve lesiones, plantillas ni suspensiones.
- Todos los equipos nuevos arrancan en 1450; 2022 es calentamiento, así que sus primeras probabilidades son poco informativas.
- Los torneos con partidos sin jugar (Clausura 2023: dos cruces de Municipal) se simulan con el calendario que existe, no con uno inventado.
- La maqueta `mockups/pantalla-liga.html` se regeneró con estos números (v4, `prototipos/mock_liga_v4.py`): Liga 1 2026, ambos torneos.
