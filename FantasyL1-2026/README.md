# Fantasy Liga 1 2026 v1.0 (Localhost)

Fantasy Liga 1 2026 100% localhost. Flujo: Parquets -> DuckDB local -> Postgres local -> API FastAPI -> Next.js PWA.

## Requisitos
- Docker Desktop
- Python 3.11+ (recomendado para wheels de DuckDB)
- Node 18+

## Setup rapido
1) Entra al proyecto:
```
cd FantasyL1-2026
```

2) Configura variables:
```
copy .env.example .env
copy frontend\.env.local.example frontend\.env.local
```

3) Levanta Postgres:
```
docker-compose up -d
```

4) Backend (FastAPI):
```
py -3.11 -m venv .venv
.venv\Scripts\activate
pip install -r backend\requirements.txt
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

5) Ingesta y cache (en otra terminal, desde FantasyL1-2026):
```
python scripts\ingest_to_duckdb.py
python scripts\sync_duckdb_to_postgres.py
```

6) Frontend (Next.js):
```
cd frontend
npm install
npm run dev
```

Abre `http://localhost:3000`.

## Entornos
- `local`: usa `.env` y `frontend/.env.local` (default).
- `test`: usa `.env.test` para pruebas con ngrok.
- `prod`: crea `.env.prod` a partir de `.env.prod.example` y define credenciales reales.

El backend lee `APP_ENV` o `ENV_FILE` para elegir el archivo de entorno.

### Test (ngrok)
```
.\scripts\start_all.ps1 -Env test -SkipWatch
```
En otra terminal:
```
ngrok http 3000
```

### Prod (plantilla)
```
copy .env.prod.example .env.prod
.\scripts\start_all.ps1 -Env prod -SkipWatch
```
En prod real debes usar un backend aislado, DB dedicada y secretos fuertes.

### Abrir navegador automáticamente
El script abre `http://localhost:3000` al finalizar. Para evitarlo:
```
.\scripts\start_all.ps1 -Env local -SkipWatch -NoBrowser
```

### Rebuild de parquets (DuckDB + Postgres)
Si modificaste parquets y quieres re-ingestar todo:
```
.\scripts\start_all.ps1 -Env test -SkipWatch -Rebuild
```
El `-Rebuild` tambien convierte imagenes (jpg/jpeg/webp) a PNG con fondo transparente.

## Datos de parquets
Ruta esperada:
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

## Scripts
- `scripts/ingest_to_duckdb.py`: carga parquets en `data/fantasy.duckdb`.
- `scripts/sync_duckdb_to_postgres.py`: puebla `teams`, `players_catalog`, `fixtures`.
- `scripts/watch_parquets.py`: observa cambios en parquets y re-sincroniza DuckDB + Postgres.
- `scripts/recalc_round.py`: stub v1.0.
- `scripts/convert_images_to_png.py`: convierte imagenes a PNG con fondo transparente.

## Admin API (token dev)
Header requerido: `X-Admin-Token: <ADMIN_TOKEN>`
- `POST /admin/rebuild_catalog`
- `POST /admin/apply_prices?round_number=1&refresh_from_duckdb=true`
- `POST /admin/seed_season_rounds?rounds=34`

## Notas
- La API solo lee Postgres. No lee parquets en requests.
- `players_fantasy.parquet` debe tener: `player_id`, `name`, `position`, `team_id`, `price`.
