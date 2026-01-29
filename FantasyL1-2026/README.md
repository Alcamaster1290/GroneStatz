# Fantasy Liga 1 2026

App Fantasy (FastAPI + Next.js) basada en el pipeline de parquets.
Flujo: Parquets → DuckDB → Postgres → API → PWA.

## Requisitos
- Docker Desktop
- Python 3.11+
- Node 18+

## Setup rápido (local/test)
1) Entra al proyecto:
```
cd FantasyL1-2026
```
Si tu ruta tiene espacios, usa comillas en PowerShell.

2) Variables de entorno:
- Edita `.env`, `.env.test`, `.env.prod` según el entorno.
- Frontend: parte de `frontend/.env.local.example` y crea `frontend/.env.local`.

3) Levanta todo (local):
```
.\scripts\start_all.ps1 -Env local -SkipWatch
```
Test:
```
.\scripts\start_all.ps1 -Env test -SkipWatch
```
Rebuild completo (parquets + imágenes + caches):
```
.\scripts\start_all.ps1 -Env test -SkipWatch -Rebuild
```

## Entornos
- `local`: usa `.env` y `frontend/.env.local`.
- `test`: usa `.env.test` (ngrok / QA).
- `prod`: usa `.env.prod` (base dedicada).

El backend lee `APP_ENV` o `ENV_FILE`.
Migraciones por entorno:
```
$env:ENV_FILE=".env.test"
python -m alembic -c backend\alembic.ini upgrade head
```

## Parquets
Ruta esperada (datos base):
`gronestats/data/Liga 1 Peru/2025/parquets/normalized/`

Parquets usados:
- matches.parquet
- teams.parquet
- players.parquet
- players_fantasy.parquet
- player_match.parquet
- player_totals.parquet
- player_team.parquet
- player_transfer.parquet
- team_stats.parquet

**Importante:** la app usa `players_fantasy.parquet` como catálogo. Fixtures 2026 se cargan desde Admin (no desde matches 2025).

## Scripts clave
- `scripts/ingest_to_duckdb.py`: carga parquets a DuckDB.
- `scripts/sync_duckdb_to_postgres.py`: sincroniza a Postgres.
- `scripts/watch_parquets.py`: watcher para re-sync automático.
- `scripts/recalc_round.py`: recalcula puntos y precios.
- `scripts/convert_images_to_png.py`: convierte a PNG con fondo transparente.

## Admin API
Header requerido: `X-Admin-Token: <ADMIN_TOKEN>`

Endpoints comunes:
- `POST /admin/rebuild_catalog`
- `POST /admin/fixtures` (crear/actualizar partido)
- `PUT /admin/fixtures/{id}`
- `POST /admin/player-stats`
- `POST /admin/recalc_round?round_number=1`

## Login / Reset password
En prod el reset está deshabilitado por defecto.
Para habilitarlo en web:
```
NEXT_PUBLIC_ENABLE_PASSWORD_RESET=true
```

## Deploy PROD (VPS)
Usa el compose raíz y Traefik (TLS):
- `../docker-compose.prod.yml`
- `DEPLOYMENT_PROD.md`

Comando:
```
docker compose -f ../docker-compose.prod.yml --env-file ../.env.prod up -d --build
```

## Troubleshooting rápido
- `ModuleNotFoundError: app`: corre alembic desde la raíz del proyecto con `.venv` activo.
- `fixtures.status does not exist`: migra y luego `sync_duckdb_to_postgres.py`.
- `no_players_available`: verifica `players_fantasy.parquet` y re-sync.

---

Si estás en VPS y necesitas refrescar catálogo/imagenes desde parquets:
```
docker run --rm --network gronestatz_internal \
  -e DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}" \
  -e PARQUET_DIR="/data/parquets" \
  -e DUCKDB_PATH="/data/fantasy.duckdb" \
  -e PYTHONPATH=/app \
  -v "/opt/GroneStatz/gronestats/data/Liga 1 Peru/2025/parquets/normalized:/data/parquets" \
  -v "/opt/GroneStatz/FantasyL1-2026:/repo" \
  gronestatz-api sh -lc "python /repo/scripts/ingest_to_duckdb.py && python /repo/scripts/sync_duckdb_to_postgres.py"
```
