# Verificación de las tablas finales contra otra fuente (2026-11-26)

Se comparó, equipo por equipo, la tabla de **Apertura**, la de **Clausura** y la **acumulada** de 2022 a 2026 calculadas desde el bundle contra las de Wikipedia (inglés), que publica las tres con partidos, ganados, empatados, perdidos, goles y puntos. Las diferencias se contrastaron con crónicas de los partidos (ESPN, El Comercio, Infobae, Perú21, América TV, Trome). Archivos: `datos-de-apoyo/verificacion-tablas/` (`wikipedia_tablas.txt`, `mis_tablas.csv`, `comparacion_tablas.csv` y `comparar_tablas.py`).

Fuentes: [2022](https://en.wikipedia.org/wiki/2022_Liga_1_(Peru)) · [2023](https://en.wikipedia.org/wiki/2023_Liga_1_(Peru)) · [2024](https://en.wikipedia.org/wiki/2024_Liga_1_(Peru)) · [2025](https://en.wikipedia.org/wiki/2025_Liga_1_(Peru)) · [2026](https://en.wikipedia.org/wiki/2026_Liga_1_(Peru)). Wikipedia es una fuente secundaria: lo que sigue son contrastes, no una auditoría oficial.

## Resultado
**No hay errores en los resultados ni en los goles de los partidos jugados.** Las tablas de Apertura coinciden fila por fila en las cinco temporadas, salvo una sanción de puntos en 2026. Todas las diferencias caen en cuatro causas, ninguna es un partido mal leído.

| Tabla | Equipos | Filas idénticas (partidos, goles y puntos) | Partidos y goles idénticos | Causa de las filas distintas |
|---|---|---|---|---|
| Apertura 2022 | 19 | 19 | 19 | — |
| Clausura 2022 | 19 | 19 | 19 | — |
| Acumulada 2022 | 19 | 13 | 19 | sanciones de puntos (B) |
| Apertura 2023 | 19 | 19 | 19 | — |
| Clausura 2023 | 19 | 15 | 16 | partidos adjudicados (C) y sanción (B) |
| Acumulada 2023 | 19 | 14 | 16 | C y B |
| Apertura 2024 | 18 | 18 | 18 | — |
| Clausura 2024 | 18 | 16 | 16 | un gol en un partido (D) |
| Acumulada 2024 | 18 | 18 | 18 | — |
| Apertura 2025 | 19 | 19 | 19 | — |
| Clausura 2025 | 18 (+ Binacional) | 11 | 11 | partidos anulados y adjudicado (C) |
| Acumulada 2025 | 19 | 11 | 11 | C |
| Apertura 2026 | 18 | 17 | 18 | sanción a UTC (B) |
| Clausura 2026 | 18 | 15 | 16 | sanción a UTC (B) y un gol (D) |
| Acumulada 2026 | 18 | 14 | 18 | sanciones (B) |

El campeón y sus puntos coinciden en los 10 torneos (Apertura 2022 Melgar 41 … Clausura 2026 Sport Huancayo 37).

## Las diferencias, por causa

### B. Sanciones de puntos por deudas (no son resultados de partido)
La tabla oficial las resta; la mía solo suma lo ganado en la cancha.
- **2022 (acumulada):** Universidad César Vallejo −2, Municipal −4, Sport Boys −7 y Carlos Stein −2; Alianza Lima +2 y Ayacucho +1 por el torneo de Promoción y Reserva.
- **2023:** Garcilaso −1 (Clausura y acumulada), Sport Boys −4 y Municipal −5 (acumulada).
- **2026:** UTC −5 en el Apertura y −5 en el Clausura (−10 acumulada), Sport Boys −4, ADT −1 y Cajamarca −2 (acumulada).

### C. Partidos que la federación anuló o adjudicó
- **Clausura 2023 · Municipal:** la tabla oficial cuenta los dos cruces de Municipal como **3-0 adjudicados** a Mannucci y a Grau ([Wikipedia](https://en.wikipedia.org/wiki/2023_Liga_1_(Peru)): «its matches against Carlos A. Mannucci and Atlético Grau were cancelled and awarded to those clubs»). En mi tabla están excluidos, así que Grau figura con 15 puntos (18.º) en lugar de 18 (14.º), Mannucci con 17 en lugar de 20 y Municipal con 16 partidos en lugar de 18. El campeón no cambia.
- **Clausura 2025 · Binacional:** la federación lo descalificó el 19-08-2025 y **anuló sus resultados del Clausura**. Mi tabla los cuenta: 5 partidos (jornadas 2 a 6) contra UTC, Cusco, Alianza Atlético, Juan Pablo II y Sporting Cristal, que figuran con un partido de más. En la oficial todos los equipos tienen 17. Binacional aparece con 18 puntos (solo Apertura) en la acumulada oficial y con 23 en la mía.
- **Clausura 2025 · Ayacucho – Comerciantes Unidos:** el partido se suspendió con 1-0 para Ayacucho y el 20-11-2025 la federación lo adjudicó 3-0 a Comerciantes. Yo tengo el 1-0 jugado: Ayacucho +3 puntos y Comerciantes −3 contra la oficial.
- **Apertura 2023:** los 6 resultados administrativos (3-0) sí coinciden, porque ya estaban en el maestro.

### D. Un gol de diferencia en dos partidos
- **Clausura 2024, Alianza Lima 1-2 Cusco (3-11-2024):** la tabla de Wikipedia da a Alianza un gol menos y a Cusco uno más. El partido se jugó 1-2 según ESPN, El Comercio, Infobae, Perú21 y América TV (goles de Colitto 79', Ramos 81' y Cabellos 88'), y **la acumulada de la propia Wikipedia coincide con mis goles** (Alianza 57 a favor = 32 + 25). Es un desliz en su tabla del Clausura, no en mis datos.
- **Clausura 2026, Alianza Lima 2-0 ADT (18-09-2026):** misma situación. América TV y Trome dan el 2-0 y la acumulada de Wikipedia (59 goles de Alianza = 30 + 29) coincide con mi cuenta.

## Consecuencias
1. **Mis tablas de partidos son correctas; mis tablas de posiciones no son las oficiales** en cuatro torneos (Clausura 2023, Clausura 2025, Apertura y Clausura 2026 por UTC) y en las tres acumuladas con sanciones. Para el título no cambia nada: ningún campeón cambia y los puntos del campeón coinciden.
2. **Corrección a lo que dije antes:** el Clausura 2025 de Binacional no es «un torneo que no jugó». Jugó 5 partidos y la federación los anuló; sus datos están en el bundle y cuentan como puntos en mis tablas y en la probabilidad de ese torneo.
3. **Municipal 2023:** la nota de Infobae (2023-08-09) hablaba de una posibilidad de dar los tres puntos al rival; Wikipedia indica que se otorgaron.

## Alineado con la tabla oficial (hecho el 2026-11-26)
Alvaro aprobó alinear. Quedó así:
- `gronestats/data/Liga 1 Peru/resultados_oficiales.csv`: los 5 partidos de Binacional del Clausura 2025 como `annulled` y Ayacucho – Comerciantes como `awarded` con el 3-0 oficial. El pipeline lo aplica al maestro limpio de cada corrida (`extract-master`), nunca a la fuente, y llega a `matches.status`.
- `gronestats/data/Liga 1 Peru/ajustes_tabla.csv`: sanciones de puntos y los dos adjudicados de Municipal en el Clausura 2023, que la tabla oficial cuenta como partido y 3 puntos **sin goles** (por eso no son partidos del bundle).
- `gronestats/analysis/standings.py`: tablas de Apertura, Clausura y acumulada con esos ajustes; `title_race` las usa para el campeón y escribe `title-race/tablas_oficiales.csv`.

**Resultado de la comparación después del alineado:** 13 de las 15 tablas son idénticas a Wikipedia en todas las filas (partidos, goles, puntos y posición), incluidas las tres acumuladas con sanciones. Las 2 restantes (Clausura 2024 y Clausura 2026) difieren solo por el gol de las tablas de Wikipedia que ya se explicó en la sección D.

Pendiente: recalcular las probabilidades del Clausura 2025 (ya sin los 5 partidos de Binacional en el calendario) y regenerar la maqueta con las tablas oficiales; el código de ambas ya lee el estado.
