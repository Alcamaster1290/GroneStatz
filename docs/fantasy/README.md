# Fantasy Data Contract

`FantasyL1-2026` ya no debe consumir `parquets/normalized`. La fuente publicada es:

- `gronestats/data/Liga 1 Peru/<season>/fantasy/current`

Tablas requeridas:

- `matches.parquet`
- `teams.parquet`
- `players.parquet`
- `players_fantasy.parquet`
- `player_match.parquet`
- `player_totals.parquet`
- `player_team.parquet`
- `player_transfer.parquet`
- `team_stats.parquet`

Comandos útiles:

```powershell
py -3.11 -m gronestats.processing.pipeline run --league "Liga 1 Peru" --season 2026 --publish-target fantasy
py -3.11 -m gronestats.processing.pipeline validate --league "Liga 1 Peru" --season 2026 --target fantasy
```

La app Fantasy sigue cargando fixtures y stats oficiales vía Admin. El bundle fantasy sirve como catálogo base publicado y como snapshot estable para DuckDB/Postgres.
