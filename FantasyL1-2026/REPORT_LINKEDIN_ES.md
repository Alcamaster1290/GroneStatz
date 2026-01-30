# Fantasy Liga 1 Peru 2026 — Reporte de producto y desarrollo

> Proposito del documento  
> Este reporte resume, en formato listo para LinkedIn y con anexo tecnico, el estado actual del app Fantasy Liga 1 Peru 2026, construido con soporte de un agente con acceso al repositorio GroneStatz. Incluye funcionalidades, diseno, flujo de usuario, backend y despliegue.

---

## 1) Resumen ejecutivo (para LinkedIn)

En las ultimas semanas levantamos un Fantasy de Liga 1 Peru desde cero, con foco en experiencia mobile-first, pipeline de datos con parquets y despliegue productivo con Docker + Traefik + TLS.  
El resultado es una app que permite: crear equipo, armar XI, manejar mercado, visualizar rondas, ranking publico y ligas privadas, administrar catalogo y cerrar rondas, ademas de un motor de puntos y precios dinamicos.

Lo mas interesante: el proceso se hizo en modo Agente, con acceso completo al repo, permitiendo iterar rapido en UI, API, BD y despliegue sin perder contexto.  
La colaboracion humano-agente fue clave para ajustar reglas de negocio, iterar UX y solucionar problemas reales de prod (CORS, build, rutas, migraciones, etc).

---

## 2) Funcionalidades principales (vista de producto)

### Onboarding y autenticacion
- Login/Registro con validaciones de password.
- Welcome Slideshow con 5 slides y CTA a "Nombrar mi equipo".
- Naming del equipo antes de ingresar a las pantallas principales.
- Mensajeria de errores amigable y coherente con mobile.

### Tab Equipo (core de la experiencia)
- XI titular + 4 suplentes con drag & drop, seleccion desde pop-up y persistencia al navegar tabs.
- Capitan y Vicecapitan con iconos diferenciados y validacion de que ambos esten en el XI.
- Mensajes y aviso cuando se guarda en ronda cerrada (se asigna a la siguiente ronda activa).
- Vista de ronda actual con fechas, estado Pendiente/Cerrada y datos contextuales.

### Tab Mercado
- Busqueda por nombre, filtros por posicion y precio (con controles +/-).
- Filtro por equipo (solo equipos con jugadores activos y con imagen).
- Regla "maximo 3 jugadores por club" con feedback en vivo.
- Equipo aleatorio independiente de filtros activos.
- Visualizacion de jugador + club (imagen del jugador a la izquierda).

### Tab Rondas
- Lista por dia (orden cronologico).
- Equipos con imagen, fecha y hora (formato hh:mm).
- Sin datos irrelevantes en UI (no se muestra match_id).

### Tab Estadisticas
- Tabla con porcentaje de seleccion, precios y metricas relevantes.
- Indicadores visuales de tarjetas (amarilla/roja).
- Ordenamiento por porcentaje de eleccion y luego por precio.
- Muestra cantidad de equipos donde aparece cada jugador.

### Ranking
- Ranking general (liga publica) y ligas privadas.
- Vista del XI de otros equipos (click en el nombre del equipo).

### Admin
- Carga de rondas y fixtures manuales.
- Control de activar/cerrar ronda.
- Gestion de jugadores (incluye estado Lesionado).
- Registro de logs de ligas/stats y pipeline de datos.

---

## 3) Motor de puntos y precios (logica clave)

Puntos por accion
- Gol +4
- Bonus por 3 goles +3
- Asistencia +3
- Amarillas -3
- Roja -5

Minutos y faltas
- 45 min +1
- 90 min +1 adicional (max +2 por partido)
- Cada 5 faltas: -1

Porteria en cero
- Solo D/M/GK: +3

Goles recibidos
- Solo GK: -1 por gol recibido

Precios dinamicos
- Subida: +0.1 cada multiplo de 3 puntos en una jornada.
- Bajada: -0.2 si termina con 0 o negativo, y -0.1 por cada multiplo de 2 puntos negativos adicionales.
- Rango controlado: minimo 4.0, maximo 12.0.
- Jugadores lesionados no cambian precio en recalculo de ronda.

---

## 4) Datos y pipeline

El sistema se alimenta desde parquets normalizados (temporada base 2025) usados como estructura, pero con data actualizada manualmente por admin para 2026.  
Flujo principal:

1. st_parquets_updater.py para actualizar/curar catalogos y precios.  
2. Conversion de imagenes a PNG.  
3. Ingesta a DuckDB.  
4. Sincronizacion a Postgres con scripts (ingest_to_duckdb.py, sync_duckdb_to_postgres.py).

Nota clave: se evita re-agregar jugadores eliminados del fantasy.  
Se valida duplicados y solo se recalcula precio sobre el catalogo ya filtrado.

---

## 5) Arquitectura tecnica

Backend
- FastAPI + SQLAlchemy + Alembic
- Postgres 15
- Psycopg3 (no psycopg2)
- Endpoints REST para catalogo, fantasy, admin, ranking, ligas, stats.

Frontend
- Next.js 14 (App Router)
- Zustand store (estado global)
- Diseno mobile-first (cards, paneles, overlays, modales).

Infra / DevOps
- Docker Compose PROD con Traefik + Let's Encrypt
- Reverse proxy con TLS automatico
- Postgres sin exposicion publica
- Variables de entorno separadas entre test/prod

---

## 6) Diseno y UX

La UI esta pensada para movil:
- Slideshow de bienvenida para explicar reglas y dinamica del juego.
- Cards e iconos grandes, con feedback de estados (lesionado, cap/vice).
- Tab layout ordenado: Equipo, Mercado, Estadisticas, Ranking, Rondas, Ajustes.
- Indicadores simples con colores (alertas por reglas, tarjetas, estados).

---

## 7) Flujo del usuario (end-to-end)

1) Registro/Login  
2) Welcome Slideshow  
3) Nombrar equipo  
4) Elegir 15 jugadores en Mercado  
5) Armar XI titular + 4 suplentes  
6) Definir capitan y vicecapitan  
7) Guardar XI  
8) Ver rondas, fixture y desempeno  
9) Comparar ranking general y ligas privadas

---

## 8) Admin y operaciones

Admin permite:
- Cargar rondas, fixtures y stats por partido
- Activar/cerrar rondas
- Control de lesionados
- Gestion de usuarios/equipos
- Logs de ligas y stats

Reglas especiales en ronda cerrada:
Si un usuario guarda XI con ronda cerrada, no da error; se guarda automaticamente para la siguiente ronda abierta.

---

## 9) Estado actual (limitaciones conocidas)

Funcional
- Password reset se desactiva en prod si no hay servicio de correo.
- Admin requiere token por header.
- Algunos datos 2026 se insertan manualmente desde admin (fixtures/stats).

Tecnico
- Pipeline depende de parquets 2025 (estructura) + datos 2026 manuales.
- La ingesta requiere rutas correctas en servidor (parquets/imagenes).

---

## 10) Que sigue (mejoras sugeridas)

1) Automatizar ingesta de parquets y stats por fecha.
2) Migrar puntos y price engine a jobs programados (scheduler real).
3) Enviar notificaciones sobre cierre de rondas y precios.
4) Expandir metricas avanzadas (xG, xA, KPIs fantasy).

---

## 11) LinkedIn Post (texto listo para publicar)

Titulo sugerido:  
Lanzamos Fantasy Liga 1 Peru 2026 con un Agente que trabajo directo en el repo

Texto:
Durante las ultimas semanas armamos un Fantasy de Liga 1 Peru 2026 desde cero.  
Lo mas interesante: el desarrollo se hizo con un agente con acceso completo al repositorio, lo que nos permitio iterar rapido en producto, UI, backend y DevOps.

App mobile-first  
Mercado con reglas y filtros  
XI titular + suplentes  
Capitan/Vice, precio dinamico  
Ranking general + ligas privadas  
Admin con cierre de rondas  
Despliegue en Docker + Traefik + TLS  

Este proyecto demuestra como los agentes pueden acelerar el desarrollo full-stack sin perder control de negocio ni calidad de producto.

Si quieres ver el proceso completo o necesitas algo similar, me escribes.

---

## 12) Descarga

Este reporte esta guardado en el repo para que puedas compartirlo:  
FantasyL1-2026/REPORT_LINKEDIN_ES.md
