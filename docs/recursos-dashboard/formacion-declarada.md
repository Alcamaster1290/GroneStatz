# Formación declarada y cruce con los titulares

Hecho el **2026-11-26** a pedido de Alvaro: la formación de cada equipo y partido es la **declarada por SofaScore**, y se cruza con la posición de los 11 titulares para comprobar que cumplan esa distribución. Módulo `gronestats/analysis/formations.py` (pruebas en `tests/test_formations.py`); datos crudos en `<temporada>/raw/lineups.jsonl`; salidas en `datos-de-apoyo/formaciones/`.

## Cómo se obtuvo
Una llamada por partido a `/event/{id}/lineups` con `sofascore_batches lineups` (tandas de 20, parada ante el primer bloqueo). **1.629 partidos en las cinco temporadas, sin bloqueos.** Los 6 partidos administrativos de 2023 no tienen alineaciones y quedan como «vacío» en el registro. De cada lado se guarda la formación declarada y los 11 titulares con su letra (G, D, M o F) en ese partido.

## El cruce
De la formación se deduce la distribución esperada: el primer número son los defensas, el último los delanteros y los intermedios suman medios (`4-2-3-1` = D4 M5 F1). Se compara con las letras de los 11 titulares en dos niveles:
- **Completo:** defensas, medios y delanteros coinciden.
- **Solo defensas:** el número de defensas coincide. Es lo que delataría una inconsistencia real, porque medios y delanteros se confunden entre extremos y segundas puntas.

La formación declarada **siempre manda**; el cruce solo marca el partido con su razón. **Regla decidida (2026-11-26, Alvaro): el ⚠ se muestra solo cuando no coincide el número de defensas** (22 de 3.258 equipos-partido; ninguno en 2026). El conteo completo se conserva en los datos para validar, pero no se muestra.

| Temporada | Equipos-partido | Distribución completa | Solo defensas |
|---|---|---|---|
| 2022 | 696 | 643 (92,4 %) | 694 (99,7 %) |
| 2023 | 672 | 623 (92,7 %) | 672 (100 %) |
| 2024 | 612 | 573 (93,6 %) | 612 (100 %) |
| 2025 | 666 | 571 (85,7 %) | 646 (97,0 %) |
| 2026 | 612 | 567 (92,6 %) | 612 (100 %) |
| **Total** | **3.258** | **2.977 (91,4 %)** | **3.236 (99,3 %)** |

## Qué dicen las diferencias
- **No son errores de datos: son sistemáticas por formación.** SofaScore pone la letra F a la línea que va detrás del delantero en cuatro formaciones, y por eso nunca cumplen la distribución estricta: `3-4-2-1` (91 de 91 partidos, siempre M−2 F+2), `3-4-1-2` (81 de 81, M−1 F+1), `3-2-4-1` (38, M−2 F+2) y `4-4-1-1` (37, M−1 F+1). Las demás formaciones cumplen al 99 % o más: `4-2-3-1` en 1.282 de 1.285, `4-3-3` en 415 de 418, `4-1-4-1` en 286 de 287, y `5-3-2`, `5-4-1`, `3-5-2` y `3-4-3` en el 100 %.
- **Regla del producto:** usar la formación declarada y mostrar ⚠ solo cuando **no coincide el número de defensas** (99,3 % coincide). El conteo completo sirve para validar, no para descartar. La tabla guarda ambos indicadores (`defenders_ok` y `consistent`), así que cambiar la regla no obliga a reprocesar.
- **20 casos «no son 11 titulares» (todos en 2025):** SofaScore lista 10 titulares para el equipo en 16 partidos de Deportivo Garcilaso y 4 de Alianza Lima. La formación declarada se conserva; es la causa de que 2025 baje en «solo defensas».

## Reproducir
```
py -3.11 -m gronestats.processing.sofascore_batches lineups --season 2026
py -3.11 -m gronestats.analysis.formations --out docs/recursos-dashboard/datos-de-apoyo/formaciones
```
Salidas: `formaciones_equipo_partido.csv` y `.parquet` (una fila por equipo y partido: formación, esperado, contado, diferencia y razón) y los resúmenes por temporada, por formación y de las diferencias más frecuentes.

## Pendiente
La maqueta ya lee esta tabla y aplica la regla del ⚠. Falta fijar en el spec dónde vive: propuesta en `DECISIONES.md` (se calcula en el pipeline y la API solo la sirve).
