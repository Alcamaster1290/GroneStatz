# Fantasy Liga 1 2026 v1.0 (Localhost)

Fantasy Liga 1 2026.

Flujo: Parquets -> DuckDB local -> Postgres local -> API FastAPI -> Next.js PWA.

## Requisitos
- Docker Desktop
- Python 3.11+
- Node 18+

## Setup rapido
1) Entra al proyecto:
```
cd FantasyL1-2026
```
Si tu ruta tiene espacios, usa comillas en PowerShell (ejemplo):
```
cd "ruta con espacios\FantasyL1-2026"
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

4) Backend deps (venv en el proyecto):
```
py -3.11 -m venv .venv
.\.venv\Scripts\activate
pip install -r backend\requirements.txt
```

5) Migraciones (desde la raiz del proyecto):
```
$env:ENV_FILE=".env"
python -m alembic -c backend\alembic.ini upgrade head
```

6) Backend (FastAPI):
```
cd backend
uvicorn app.main:app --reload --port 8000
```

7) Ingesta y cache (en otra terminal, desde FantasyL1-2026):
```
python scripts\ingest_to_duckdb.py
python scripts\sync_duckdb_to_postgres.py
```

8) Frontend (Next.js):
```
cd frontend
npm install
npm run dev
```

Abre `http://localhost:3000`.

## Entornos
- `local`: usa `.env` y `frontend/.env.local` (default).
- `test`: usa `.env.test` para pruebas con ngrok.
- `prod`: usa `.env.prod` con base dedicada `fantasy_prod`.

El backend lee `APP_ENV` o `ENV_FILE` para elegir el archivo de entorno.
Para migraciones, define `ENV_FILE` segun el entorno:
```
$env:ENV_FILE=".env.test"
python -m alembic -c backend\alembic.ini upgrade head
```

Notas para prod (conexiones):
- Si frontend y backend corren en el **mismo host**, puedes dejar `NEXT_PUBLIC_API_URL=/api`.
- Si el backend va en **otro dominio**, ajusta `NEXT_PUBLIC_API_URL` y `CORS_ORIGINS` en `.env.prod`.

### Diferencia rapida (local vs test vs prod)
- `local`: trabajo diario. Base `fantasy`.
- `test`: QA + ngrok. Base `fantasy_test`.
- `prod`: entorno oficial local. Base `fantasy_prod` (separa datos).

### Comandos rapidos
- Local:
```
.\scripts\start_all.ps1 -Env local -SkipWatch
```
- Test:
```
.\scripts\start_test.ps1 -SkipWatch
```
- Prod:
```
.\scripts\start_prod.ps1 -SkipWatch
```
Para exponer test con ngrok:
```
ngrok http 3000
```

### Aliases directos (recomendados)
- Test con rebuild:
```
.\scripts\start_test.ps1 -SkipWatch -Rebuild
```
- Prod (sin rebuild):
```
.\scripts\start_prod.ps1 -SkipWatch
```

### Rebuild en test (parquets + imagenes + caches)
```
.\scripts\start_all.ps1 -Env test -SkipWatch -Rebuild
```

### Migraciones en prod (solo una vez o cuando cambie el schema)
```
$env:ENV_FILE=".env.prod"
python -m alembic -c backend\alembic.ini upgrade head
```

### Migraciones en local/test
Local:
```
$env:ENV_FILE=".env"
python -m alembic -c backend\alembic.ini upgrade head
```
Test:
```
$env:ENV_FILE=".env.test"
python -m alembic -c backend\alembic.ini upgrade head
```

### Test (ngrok)
```
.\scripts\start_all.ps1 -Env test -SkipWatch
```
En otra terminal:
```
ngrok http 3000
```

### Prod (local)
```
.\scripts\start_all.ps1 -Env prod -SkipWatch
```
Si es la primera vez con `fantasy_prod`, crea la base y corre migraciones:
```
docker exec -it fantasy_l1_postgres psql -U fantasy -d postgres -c "CREATE DATABASE fantasy_prod"
$env:ENV_FILE=".env.prod"
python -m alembic -c backend\alembic.ini upgrade head
```
Luego puedes hacer ingest/caches:
```
python scripts\ingest_to_duckdb.py
python scripts\sync_duckdb_to_postgres.py
```
Nota: `start_all.ps1` no ejecuta migraciones automaticamente.

### Abrir navegador automaticamente
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
El frontend carga solo PNG, asi que tambien puedes ejecutar:
```
python scripts\convert_images_to_png.py
```
Si cambiaste el schema (migraciones) y ves errores de columnas nuevas en fixtures, ejecuta:
```
$env:ENV_FILE=".env.test"
python -m alembic -c backend\alembic.ini upgrade head
python scripts\sync_duckdb_to_postgres.py
```

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
- `scripts/recalc_round.py`: recalcula puntos por ronda y actualiza precios + `price_movements`.
- `scripts/convert_images_to_png.py`: convierte imagenes a PNG con fondo transparente.
- `scripts/validate_league_flow.py`: smoke test de ligas privadas + ranking (usa `.env.test`).
- `scripts/run_manual_admin_tests.ps1`: corre migraciones + tests admin (test/prod).

## Admin API (token dev)
Header requerido: `X-Admin-Token: <ADMIN_TOKEN>`
- `POST /admin/rebuild_catalog`
- `POST /admin/apply_prices?round_number=1&refresh_from_duckdb=true`
- `POST /admin/seed_season_rounds?rounds=34`
- `GET /admin/fixtures?round_number=1`
- `POST /admin/fixtures` (crear/actualizar partido por match_id)
- `PUT /admin/fixtures/{id}` (editar partido, estado y marcador)
- `POST /admin/player-stats` (carga stats por partido: player_id, match_id, goles, asistencias, minutos, saves, fouls, amarillas, rojas, clean_sheet, goles_concedidos)
- `GET /admin/player-stats?round_number=1`
- `POST /admin/recalc_round?round_number=1` (recalcula puntos y precios)
- `GET /admin/price-movements?round_number=1`

## Ligas y Ranking (API)
- `POST /leagues` (crear liga privada, retorna codigo)
- `POST /leagues/join` (unirse por codigo)
- `GET /leagues/me` (liga actual del equipo)
- `POST /leagues/leave` (salir de la liga)
- `DELETE /leagues/members/{fantasy_team_id}` (admin: expulsar miembro)
- `GET /ranking/league` (tabla privada)
- `GET /ranking/general` (tabla global)

## Troubleshooting rapido
- `ModuleNotFoundError: app` al correr alembic: usa `python -m alembic -c backend\alembic.ini ...` desde la raiz con `.venv` activo.
- `fixtures.status does not exist`: corre migraciones y luego `python scripts\sync_duckdb_to_postgres.py`.
- `no_players_available`: asegura `sync_duckdb_to_postgres.py` y que `players_fantasy.parquet` tenga `player_id`, `name`, `position`, `team_id`, `price`.
- `StringDataRightTruncation` en `alembic_version`: ensancha la columna y reintenta migracion:
```
@'
from pathlib import Path
import sys
from sqlalchemy import create_engine, text
sys.path.append(str(Path.cwd() / "backend"))
from app.core.config import get_settings
engine = create_engine(get_settings().DATABASE_URL)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))
print("alembic_version widened")
'@ | python -
python -m alembic -c backend\alembic.ini upgrade head
```
- Error en `docker ps`: abre Docker Desktop (daemon apagado).

## Checklist prod (antes de exponer)
- Configura `JWT_SECRET` y `ADMIN_TOKEN` fuertes en `.env.prod`.
- Ajusta `CORS_ORIGINS` y `NEXT_PUBLIC_API_URL` al dominio real (no localhost/ngrok).
- Define proveedor real de email para reset de contraseña (en prod no se devuelve `reset_code`).
- Decide si el scheduler queda activo (`SCHEDULER_ENABLED`) y el intervalo.
- Asegura backups de la base `fantasy_prod`.

## Notas
- La API solo lee Postgres. No lee parquets en requests.
- `players_fantasy.parquet` debe tener: `player_id`, `name`, `position`, `team_id`, `price`.
