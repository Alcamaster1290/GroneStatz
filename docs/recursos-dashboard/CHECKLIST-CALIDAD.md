# Lista de comprobación de calidad del dashboard

Criterios para que el dashboard sea limpio y profesional. Salen de lo que fuimos descubriendo; no son normas externas. Marca cada punto antes de dar una pantalla por terminada.

## Honestidad con los datos
- [ ] Toda cifra derivada muestra **su muestra (n)**; con menos de 6 partidos se atenúa y se marca ⚠.
- [ ] Lo estimado dice que es estimado: **xG GroneStats (modelo propio)**, **probabilidad de campeonar (simulación)**, **formación (conteo D-M-F: composición del once, no dibujo táctico)**.
- [ ] Los cambios entre torneos o jornadas dicen **«no concluyente»** cuando la prueba estadística no lo respalda; con varias pruebas a la vez se corrige por comparaciones múltiples.
- [ ] La sinergia entre compañeros se presenta como **descriptiva, no causal** (no corrige rival, localía ni momento de la temporada).
- [ ] Un torneo con partidos faltantes se muestra **«sin datos completos»** y no se calcula (ej.: Clausura 2023 trae 169 de 171). Antes de marcarlo, comprobar que no sea un torneo en el que un equipo salió, como Binacional en el Clausura 2025.
- [ ] Nunca se imprime `nan`, `None` ni un hueco sin explicar: se usa «—» o una explicación.
- [ ] Unidades siempre visibles (m, %, pts, min).

## Presentación
- [ ] **Texto antes que color**: el color refuerza, nunca es el único canal (el nivel del rival va escrito: Candidato, Competitivo, Promedio, Descenso).
- [ ] Contraste y teclado según WCAG 2.2; cada gráfica tiene texto alternativo y una tabla equivalente.
- [ ] El mouse-over tiene **equivalente táctil y de teclado** (en móvil no existe el hover).
- [ ] Móvil primero: la cuadrícula de escritorio de las referencias se apila en una columna; los mapas de cancha en carrusel.
- [ ] Los equipos usan su color (`teams.team_colors`) como acento, pero comprobando el contraste en claro y oscuro.

## Escudos y fotos
- [ ] **Nunca se amplía** una imagen: los derivados salen siempre reduciendo desde el original, en 1x/2x/3x por tamaño de uso.
- [ ] Los escudos actuales son de 150 px: sin pérdida solo hasta ~75 px CSS a 2x. Para tamaños mayores hacen falta fuentes en mayor resolución o vectoriales.
- [ ] Todo jugador tiene **avatar de respaldo** (iniciales y color del club) cuando no hay foto: nunca una imagen rota.
- [ ] Un manifiesto (`player_photos`, `team_crests`) registra archivo, tamaño, transparencia y estado; la cobertura es una métrica del monitor de datos.
- [ ] Una sola fuente de imágenes (hoy están duplicadas en `gronestats/images` y `FantasyL1-2026/frontend/public/images`, 22 MB cada copia dentro de git).

## Datos y pipeline
- [ ] Una sola definición por concepto (ej.: **altura**: hoy dos fuentes discrepan en Melgar y Comerciantes Unidos).
- [ ] **Partidos que le quedan a un equipo = sus partidos programados en el calendario**, no rondas ni «equipos − 1» (con 19 equipos hay 19 rondas pero 18 partidos; en el Clausura 2025 Binacional salió y a 13 equipos les quedaron 17).
- [ ] Fechas de partido disponibles en todas las temporadas (2022 y 2023 hoy no traen fecha en el bundle).
- [ ] Tests de contrato del bundle, de checksums y del manifiesto; fixtures pequeños con partidos reales.
- [ ] Cada gráfica tiene una prueba con datos fijos (visual) y los percentiles se prueban con valores conocidos.

## Rendimiento, seguridad y entrega
- [ ] Presupuesto de rendimiento definido (referencia: «bueno» en Core Web Vitals = LCP ≤ 2,5 s) y vigilado en CI.
- [ ] Consultas con **parámetros enlazados** y lista blanca de nombres de métrica (el repo ya tuvo un fix de inyección en DuckDB).
- [ ] Secretos fuera de git (hoy `.env.qa` y `.env.test` están versionados en un repo público: rotar).
- [ ] CI en GitHub Actions: pruebas, tipos, lint, accesibilidad y presupuesto de rendimiento.
- [ ] Despliegue reproducible: Docker Compose + Caddy, `current` por symlink atómico, rollback = reapuntar.
