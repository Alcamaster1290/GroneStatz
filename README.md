# ⚽ GroneStatz

**GroneStatz** es la base técnica de análisis y datos para el fútbol peruano (Liga 1), con foco en Alianza Lima. Incluye scraping, procesamiento, visualización y la app Fantasy Liga 1 2026.

## ✅ Qué incluye
- Pipeline de datos (SofaScore + parquets) y procesamiento.
- Scripts de análisis y visualizaciones.
- Estructura reutilizable para dashboards y reportes.
- App Fantasy completa en `FantasyL1-2026/` (API + PWA).

## 🎮 Fantasy Liga 1 2026
La app vive en `FantasyL1-2026/`.

- Guía local/test: `FantasyL1-2026/README.md`
- Deploy prod (VPS + TLS): `FantasyL1-2026/DEPLOYMENT_PROD.md`

## 🧰 Instalación rápida (core GroneStatz)
```bash
git clone https://github.com/tu_usuario/GroneStatz.git
cd GroneStatz
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/macOS
pip install -e .
```

Opcional (dependencias adicionales):
```bash
pip install -r requirements.txt
```

## 🧪 Tests
```bash
pytest -v tests/
```

## 📁 Estructura (resumen)
```
GroneStatz/
|-- gronestats/               # Código fuente (ETL, análisis, utilidades)
|-- FantasyL1-2026/            # App Fantasy (FastAPI + Next.js)
|-- scripts/                   # Scripts varios
|-- tests/                     # Pruebas pytest
|-- logs/
|-- notebooks/
|-- README.md
```

## 🔍 Datos y fuentes
El pipeline usa información pública y scrapers open-source. Créditos:
- ScraperFC: https://github.com/oseymour/ScraperFC
- LanusStats: https://github.com/federicorabanos/LanusStats
- football_analytics: https://github.com/eddwebster/football_analytics

## 🤝 Contribuciones
1) Fork
2) Nueva rama
3) PR con descripción clara

## 📣 Contacto
- YouTube: https://www.youtube.com/@Gronestats
- X (Twitter): https://twitter.com/Gronestats

## 📄 Licencia
MIT.

**Hecho en Perú 🇵🇪 con datos, fútbol y pasión.**
