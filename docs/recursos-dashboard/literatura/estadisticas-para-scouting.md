# Estadísticas para scouting y para la capa de televisión

Fuente: football-docs (índice local, 2026-11-27), proveedores `free-sources` (FBref y Understat), `soccerdata`, `mplsoccer` y `kloppy`. Ver [`README.md`](README.md) para procedencia y límites. Cruzado con lo que trae nuestro `Player Stats` de SofaScore (64 columnas de estadística por jugador y partido, algunas son etiquetas como `statisticsType` y `teamName`; revisadas en un libro de 2026).

## Dos capas, como pidió Alvaro (2026-11-27)

| Capa | Qué es | Datos que ya tenemos |
|---|---|---|
| **Comercial o de televisión** | Lo que se ve en una transmisión: xG, tiros, tiros al arco, posesión, córners, atajadas, faltas, tarjetas, pases, mapa de tiros, barras comparativas del partido, tabla de liga con promedios | `team_stats` (50 métricas en 7 grupos, 306 de 306 partidos en 2026), `shot_events` con xG propio |
| **Scouting** | Cuánto aporta un jugador y a quién se parece: per-90, percentiles por rol, progresión, defensa, duelos, jugadores parecidos, comparador, filtros por edad y minutos | `Player Stats`, `heatmap_points`, `average_positions`, edad y altura |

La capa de televisión es la entrada sencilla; la de scouting vive debajo, sin quitarle protagonismo a la primera.

## Catálogo de FBref y qué cubrimos

FBref (datos de Opta, con xG de StatsBomb; no calcula el suyo) agrupa sus estadísticas así. La tercera columna es nuestra cobertura con SofaScore.

| Categoría de FBref | Ejemplos | Con nuestros datos |
|---|---|---|
| Estándar | goles, asistencias, xG, xAG, pases y conducciones progresivas | goles, asistencias y xG propio sí; xAG no; conducciones progresivas sí (`progressiveBallCarriesCount`); pases progresivos no verificados |
| Disparo | tiros, tiros al arco, distancia del tiro, tiros libres, penales | sí: `totalShots`, `onTargetScoringAttempt`, `shotOffTarget`, `blockedScoringAttempt`, `hitWoodwork`; distancia desde las coordenadas del tiro; situación en `situation` |
| Pases | totales, cortos, medios y largos, pases clave, tercio final | totales, largos (`totalLongBalls`), por mitad de cancha, `keyPass` y centros sí; el corte corto/medio/largo no |
| Tipos de pase | en juego, a balón parado, en profundidad, cambios de orientación, centros | no |
| Creación de tiros y de goles (SCA, GCA) | tipos: juego, balón parado, regate, tiro, falta, defensa | no: exige secuencias de eventos |
| Defensa | entradas, intercepciones, bloqueos, despejes, errores | `totalTackle`, `wonTackle`, `interceptionWon`, `totalClearance`, `outfielderBlock`, `ballRecovery`, `lastManTackle`; errores no |
| Posesión | toques por zona, regates, conducciones, conducciones progresivas, recepciones | `touches`, `ballCarriesCount`, distancia de conducción, `totalContest` y `wonContest` (regates), `dispossessed`; toques por zona se podrían aproximar con `heatmap_points` |
| Arquero | % de paradas, PSxG, centros detenidos, acciones de barredor | `saves`, `keeperSaveValue`, `goodHighClaim`, `punches`, `totalKeeperSweeper`; % de paradas se calcula con los tiros al arco recibidos; PSxG no |

## Qué trae nuestro `Player Stats` (SofaScore)

64 estadísticas por jugador y partido, más identidad (nombre, posición, dorsal, altura, país, fecha de nacimiento y columnas de valor de mercado). Agrupadas:

- **Resumen:** `minutesPlayed`, `rating`, `goals`, `goalAssist`, `captain`, `substitute`.
- **Disparo y creación:** `totalShots`, `onTargetScoringAttempt`, `shotOffTarget`, `blockedScoringAttempt`, `hitWoodwork`, `bigChanceCreated`, `bigChanceMissed`, `keyPass`, `totalCross`, `accurateCross`.
- **Pases:** `totalPass`, `accuratePass`, `totalLongBalls`, `accurateLongBalls`, `totalOwnHalfPasses`, `accurateOwnHalfPasses`, `totalOppositionHalfPasses`, `accurateOppositionHalfPasses`.
- **Conducción y posesión:** `touches`, `ballCarriesCount`, `totalBallCarriesDistance`, `bestBallCarryProgression`, `progressiveBallCarriesCount`, `totalProgressiveBallCarriesDistance`, `totalProgression`, `totalContest`, `wonContest`, `possessionLostCtrl`, `unsuccessfulTouch`, `dispossessed`.
- **Defensa y duelos:** `totalTackle`, `wonTackle`, `interceptionWon`, `totalClearance`, `ballRecovery`, `outfielderBlock`, `lastManTackle`, `duelWon`, `duelLost`, `aerialWon`, `aerialLost`, `challengeLost`, `fouls`, `wasFouled`, `totalOffside`.
- **Arquero:** `saves`, `keeperSaveValue`, `goodHighClaim`, `punches`, `totalKeeperSweeper`, `accurateKeeperSweeper`.
- **Valores normalizados de SofaScore:** `passValueNormalized`, `dribbleValueNormalized`, `defensiveValueNormalized`, `shotValueNormalized`, `goalkeeperValueNormalized` (por su nombre parecen los componentes de su rating; el índice no los documenta).
- **No trae tarjetas.** Ver `../plan-datos-faltantes.md`, sección 12.

Para scouting alcanza para: per-90 de casi todo, percentiles por posición, perfiles de progresión y de defensa, y un índice de similitud. Edad, altura, país y valor de mercado están como columnas del libro; no se verificó cuán completas vienen por temporada.

## Fuentes y herramientas del ecosistema

| Herramienta | Qué hace | Nota |
|---|---|---|
| `soccerdata` | un lector Python por fuente: FBref, Understat, WhoScored, Sofascore, ESPN, ClubElo, SoFIFA, MatchHistory | según el índice, el lector de **Sofascore** expone ligas, temporadas, tabla de posiciones y calendario; no menciona el detalle por jugador |
| ClubElo | Elo de todos los clubes europeos, de 1939 a hoy | no cubre Perú: nuestro Elo es propio |
| FBref | estadísticas agregadas por temporada | límite de unas 10 peticiones por minuto; sin eventos por jugada; el índice local no menciona la Liga 1 |
| Understat | xG por tiro y agregados | solo Big 5 y liga rusa |
| `kloppy` | modelo de datos unificado para eventos y tracking de varios proveedores | en sus calificadores, una tarjeta es `FIRST_YELLOW`, `SECOND_YELLOW` o `RED`: las tarjetas por jugador son eventos, no una estadística de resumen |
| `mplsoccer` | canchas y gráficos; tipo de cancha `opta`, que usa también SofaScore | los gráficos de radar y *pizza* citados en `../README.md` no aparecieron en el índice local |

Esto encaja con que las tarjetas por jugador no estén en `Player Stats`: en kloppy son un calificador de un evento del partido, y en SofaScore harían falta los incidentes (`/event/{id}/incidents`), que no hemos pedido.
