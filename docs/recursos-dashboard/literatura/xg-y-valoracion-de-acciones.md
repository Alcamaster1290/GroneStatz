# xG y valoración de acciones

Fuente: football-docs (índice local, 2026-11-27), proveedores `statsbomb`, `opta`, `sportmonks`, `free-sources` (Understat) y `socceraction`. Ver [`README.md`](README.md) para procedencia y límites. Nuestro modelo: [`../xg-modelo.md`](../xg-modelo.md).

## xG de cada proveedor

| | StatsBomb | Opta | Understat | FBref (básico) |
|---|---|---|---|---|
| Ubicación del tiro | sí | sí | sí | sí |
| Parte del cuerpo | sí | sí | sí | sí |
| Tipo o técnica del tiro | sí | sí | parcial | parcial |
| Estado del partido | sí | sí | sí | no |
| Posición del arquero (*freeze frame*) | sí | no | no | no |
| Posición de los defensas (*freeze frame*) | sí | no | no | no |
| Contexto del evento previo | sí | parcial | no | no |
| Valores accesibles | solo datos abiertos | con licencia | gratis en la web | gratis en la web (viene de Opta) |

La documentación señala que el *freeze frame* es la ventaja metodológica de StatsBomb: la investigación académica ha encontrado de forma consistente que la posición del arquero y de los defensas está entre lo que más predice la conversión de un tiro.

**StatsBomb** entrega `statsbomb_xg` en cada evento de tiro (de 0 a 1). Entradas del modelo que devolvió el índice: ubicación (distancia al centro del arco, ángulo visible del arco, coordenadas) y contexto del tiro (juego abierto, tiro libre, córner, penal, saque inicial, tras un regate, mano a mano, arco abierto). Penales: valor fijo cercano a **0,76**, porque convierten entre el 76 % y el 77 %. También hay **xGOT** (xG después del remate, que considera dónde fue al arco), solo en la API comercial y algunos conjuntos derivados. El modelo se actualiza de forma periódica y la versión no figura en los datos: los valores históricos pueden cambiar al reprocesar. El xG de un partido es la suma de `statsbomb_xg` de los tiros de cada equipo.

**Opta** ofrece por partido el recurso `/matchexpectedgoals/{token}?fx={matchId}` (unos 154 KB) con xG y xGOT por tiro.

**SportMonks** lo da según el plan contratado: tipo de estadística 580 (xG) y 581 (xA).

**Understat** (Big 5 europeas y liga rusa, desde 2014/15, con modelo propio):
- Por tiro: `minute`, `result` (Goal, SavedShot, MissedShots, BlockedShot, ShotOnPost), `X` e `Y` normalizados de 0 a 1 (X atacando de izquierda a derecha), `xG`, `player`, `h_a`, `situation` (OpenPlay, FromCorner, SetPiece, DirectFreekick, Penalty), `shotType` (RightFoot, LeftFoot, Head), `player_assisted` y `lastAction`.
- Por jugador y temporada: `games`, `time`, `goals`, `xG`, `assists`, `xA`, `shots`, `key_passes`, `npg`, `npxG`, `xGChain` y `xGBuildup` (xG de las posesiones en que participó, y esa cifra sin tiros ni pases clave).
- Por equipo y temporada, a favor y en contra: `xG`/`xGA`, `npxG`, `deep` (pases completados a menos de 20 m del arco), `xpts`, `npxGD` y los componentes de PPDA (intensidad de presión).

## xT, VAEP y SPADL (socceraction)

Modelos de valoración de acciones del laboratorio DTAI de KU Leuven, implementados en `socceraction`:
- **SPADL**: formato estándar de acciones que convierte los eventos de cada proveedor (StatsBomb, Wyscout, Opta o cualquiera que lea kloppy) a una representación común. **Atomic-SPADL** parte cada acción compuesta en inicio y final: un pase pasa a ser «pase» (del pasador) más «recepción» (del receptor), con 11 atributos y deltas dx y dy.
- **xT** (*Expected Threat*): cuánto aumenta una acción de movimiento del balón la probabilidad de gol. Basado en zonas de una cuadrícula.
- **VAEP**: valora toda acción con balón por cómo cambia la probabilidad de marcar menos la de recibir gol. **Atomic-VAEP** acredita por separado a quien pasa y a quien recibe, y sirve para evaluar movimiento sin balón.

| Modelo | Entradas | Valora | Fortaleza |
|---|---|---|---|
| xT | zonas de una cuadrícula | solo movimientos del balón | simple, interpretable y rápido |
| VAEP | rasgos de la secuencia de acciones | todas las acciones con balón | más preciso, entiende el contexto |
| xG | ubicación del tiro y contexto | solo tiros | estándar para la calidad de una ocasión |

kloppy aclara que **xT y VAEP no los entrega ninguna fuente cruda**: hay que calcularlos con modelos de terceros a partir de secuencias de eventos.

## Contraste con GroneStats

- **Penales:** nuestro modelo usa una constante cercana al 76 % (la conversión histórica de nuestras temporadas), coherente con el ≈ 0,76 de StatsBomb. **Autogoles:** xG 0 y fuera del entrenamiento.
- **Qué nos falta frente a StatsBomb:** no hay *freeze frame* en SofaScore. Es la limitación estructural de cualquier xG construido con estos datos; nuestro modelo se apoya en ubicación, parte del cuerpo y situación, y se valida dejando una temporada fuera (AUC de 0,78 a 0,80).
- **Idea por verificar (no probada):** SofaScore da la ubicación del tiro en la boca del arco (`goal_mouth_location`), lo que permitiría un xGOT propio para arqueros y definidores. Solo si esa columna está completa; no lo hemos medido.
- **xT y VAEP** exigen eventos con pases y conducciones con coordenadas, que el scraper de SofaScore no trae (ver `../plan-datos-faltantes.md`, sección «Eventos con coordenadas»). Para scouting, lo más cercano que sí tenemos son conducciones y progresión por jugador (`Player Stats`), descritas en [`estadisticas-para-scouting.md`](estadisticas-para-scouting.md).
