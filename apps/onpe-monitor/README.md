# ONPE 2026 Monitor

Módulo standalone en React + Vite para monitoreo electoral ONPE 2026.

## Qué incluye

- UI operativa y limpia para presidencial, Senado y Diputados.
- Centro de alertas con reglas estructuradas.
- Modelo de datos explícito con `vote_basis` obligatorio.
- Carpeta de imágenes lista para logos de partidos y assets UI.
- Branding partidario centralizado en `src/config/partyBranding.js`.

## Importante sobre colores y logos

Los colores incluidos en `partyBranding.js` están preparados como referencia de branding para la app y centralizan la paleta usada por el dashboard. Deben contrastarse con los logos/SVG oficiales finales antes de salir a producción. Los `logoPath` ya están listos para reemplazar placeholders por archivos reales.

## Estructura

```text
apps/onpe-monitor/
  public/images/parties/
  public/images/ui/
  src/components/
  src/config/
  src/data/
```

## Comandos

```bash
npm install
npm run dev
npm run build
npm run preview
```
