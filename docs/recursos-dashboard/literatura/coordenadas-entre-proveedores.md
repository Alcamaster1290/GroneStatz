# Coordenadas entre proveedores

Fuente: football-docs (índice local, 2026-11-27), proveedores `opta`, `statsbomb`, `wyscout`, `mplsoccer` y `kloppy`. Ver [`README.md`](README.md) para procedencia y límites.

## Comparación

| Proveedor | Eje x | Eje y | Origen | Notas |
|---|---|---|---|---|
| Opta | 0 a 100 | 0 a 100 | arco propio, línea de banda derecha | siempre ataca de izquierda a derecha |
| StatsBomb | 0 a 120 | 0 a 80 | arriba a la izquierda | cancha de 120 × 80 yardas; mplsoccer la dibuja con y invertido (80 a 0) |
| Wyscout | 0 a 100 | 0 a 100 | arriba a la izquierda | el eje y está invertido respecto a Opta |
| SportMonks | varía | varía | depende de la fuente | suele heredar del proveedor de origen |

Tipos de cancha de **mplsoccer**: `statsbomb` (0-120 × 80-0), `opta` (0-100 × 0-100, **«también usado por Sofascore y WhoScored»**), `wyscout` (0-100 con y invertido), `uefa` (0-105 × 0-68) y los de tracking (`tracab`, `skillcorner`, `secondspectrum`, `metricasports`, `impect`), que piden largo y ancho. kloppy tiene su propio modelo, de 105 × 68 con origen abajo a la izquierda.

## Opta, en detalle

- Eje x: 0 en la línea de gol propia y 100 en la del rival (dirección de ataque). Eje y: 0 en la banda derecha y 100 en la izquierda, mirando hacia el arco rival.
- Los valores pueden salirse un poco: se observó de -1,7 a 101,7 en x y de -2,0 a 102,0 en y.
- Las coordenadas siempre se normalizan de izquierda a derecha: el equipo que ataca va de x = 0 a x = 100 sin importar el sentido real ni el periodo.
- **Autogoles:** con el calificador 28 sobre un gol (tipo 16), las coordenadas vienen **invertidas**: el evento queda en el arco que defiende (x bajo) y la atribución del evento es del equipo que lo metió en contra, así que hay que cambiarla al rival.
- Zonas aproximadas: tercio defensivo propio 0-33,3; medio 33,3-66,7; ataque 66,7-100; **área grande 83-100 en x y 21-79 en y**; **área chica 94-100 y 37-63**.

## Conversiones

```
Opta -> StatsBomb:  x_sb = x_opta * 1.2     y_sb = y_opta * 0.8
Opta -> Wyscout:    x_w  = x_opta           y_w  = 100 - y_opta
```
kloppy hace todas las transformaciones con `dataset.transform(to_coordinate_system=...)`.

**Boca de gol (Wyscout):** en los tiros, `goalMouthLocation` usa un sistema aparte, independiente de la cancha: `y` de 0 a 100 a lo ancho del arco (poste izquierdo 0, derecho 100) y `z` de 0 a 100 en altura (suelo 0, travesaño 100).

## Contraste con GroneStats

Lo verificado con el código de Streamlit (`../coordenadas-y-orientacion.md`) es compatible con esta documentación y la matiza:

| Dato de SofaScore | Lo que verificamos | Con Opta |
|---|---|---|
| Posiciones medias y heatmap | `x` en dirección de ataque: 0 arco propio, 100 arco rival | igual que Opta |
| **Tiros** | `x` es la **distancia al arco que se ataca** (0 en la línea de gol), igual para local y visita; `y` de 0 a 100 con centro en 50 | **distinto**: en Opta un tiro cerca del arco tiene x cercano a 100 |
| Punto de penal | `x` = 11,5 | consistente con el área de Opta (a 17 unidades de la línea de fondo) |
| Área grande | 17 unidades de fondo, `y` de 21,1 a 78,9 | Opta: 83-100 y 21-79 |
| Área chica | 5,8 unidades, `y` de 36,8 a 63,2 | Opta: 94-100 y 37-63 |
| Postes | `y` = 44,2 y 55,8 | estándar de mplsoccer para `opta` |

Consecuencias prácticas:
- SofaScore usa la cancha `opta` de mplsoccer para posiciones y heatmaps, pero sus **tiros no están en el sistema de dirección de ataque**: al combinarlos con posiciones hay que convertir (`100 - x`), como ya dice la regla del proyecto.
- Los autogoles de SofaScore vienen en su propia marca (`goal_type` «own») y nuestro modelo de xG los excluye del entrenamiento y les da xG 0. La nota de Opta ilustra el riesgo de mezclarlos con los demás tiros: en ese proveedor quedan registrados en el arco que defendía el autor.
- Si más adelante se compara con datos de otro proveedor (StatsBomb, FBref), las conversiones de arriba son el punto de partida.
