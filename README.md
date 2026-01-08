# ⚽ GroneStatz

**GroneStatz** es la versión más estable y completa del sistema de análisis de datos para el fútbol peruano. Este proyecto está enfocado principalmente en Alianza Lima y la Liga 1, y constituye la base técnica del canal de YouTube y cuenta de X (Twitter) **GroneStats** o **GroneStatistics**, especializados en visualización de estadísticas, alineaciones, tiros, momentos de partido, mapas de calor, y mucho más.

---

## 📊 ¿Qué ofrece este proyecto?

Este repositorio contiene:

- Scripts de scraping con `SofaScore` para recolectar datos relevantes de cada partido.
- Análisis de alineaciones, mapas de calor y momentum.
- Exportación de visualizaciones y datos en múltiples formatos.
- Integración con `Streamlit` (próximamente) para apps interactivas.
- Datos estructurados que permiten la reutilización para informes, modelos o dashboards.
- Soporte para automatización de análisis pre y post partido.

---

## 🔍 Origen de los datos

Utiliza `ScraperFC`, un scraper open-source que extrae información de SofaScore.

### Créditos

Este proyecto se apoya en herramientas y trabajos open-source que han sido fundamentales para el desarrollo del ecosistema GroneStats:

- ⚙️ `ScraperFC` — Librería para extracción de datos futbolísticos (Sofascore, Transfermarkt, etc).  
  https://github.com/oseymour/ScraperFC

- 🧠 `LanusStats` — Scraper open-source para datos de SofaScore.  
  https://github.com/federicorabanos/LanusStats

- 📐 `football_analytics` — Trabajo de referencia en fundamentos de análisis futbolístico, desarrollado por Edd Webster.  
  https://github.com/eddwebster/football_analytics


---

## 🚀 Instalación

1. Clona el repositorio:

```bash
git clone https://github.com/tu_usuario/GroneStatz.git
cd GroneStatz
```

2. Crea un entorno virtual e instálalo como editable:

```bash
python -m venv venv
venv\Scripts\activate  # en Windows
source venv/bin/activate  # en Linux/macOS

pip install -e .
```

3. Instala dependencias adicionales si lo necesitas:

```bash
pip install -r requirements.txt
```

---

## 🧪 Tests

Este proyecto incluye tests con `pytest` para asegurar el funcionamiento del scraping y la consistencia de datos.

Ejecuta los tests así:

```bash
pytest -v tests/
```

---

## Estructura del proyecto

```
GroneStatz/
|-- gronestats/                 # Codigo fuente principal
|   |-- analysis/               # Analisis y apps (Streamlit)
|   |-- data/                   # Datos locales (xlsx, parquet, etc)
|   |-- images/                 # Imagenes y recursos
|   |-- processing/             # Procesamiento y ETL
|   |-- results/                # Salidas generadas
|   |-- stats/                  # Estadisticas y calculos
|   |-- utils/                  # Utilidades compartidas
|   |-- visualization/          # Visualizaciones
|   |-- app_config.py           # Configuracion de la app
|   |-- requirements.txt        # Dependencias del paquete gronestats
|   `-- __init__.py
|-- logs/                       # Logs locales
|-- notebooks/                  # Notebooks de exploracion
|-- scripts/                    # Scripts varios
|-- tests/                      # Pruebas con pytest
|-- LICENSE
|-- README.md
|-- pyproject.toml
|-- requirements.txt
`-- setup.py
```

---


## 🤝 Contribuciones

Este proyecto está en constante evolución. Si deseas colaborar:

1. Haz un fork del proyecto.
2. Crea una nueva rama para tus cambios.
3. Haz un PR con una buena descripción.

---

## 📣 Contacto y redes

Forma parte del proyecto **GroneStats** en redes sociales:

- YouTube: [GroneStats](https://www.youtube.com/@Gronestats)
- X (Twitter): [@GroneStats](https://twitter.com/Gronestats)

---

## 📄 Licencia

Este proyecto se encuentra bajo la licencia MIT. Puedes hacer uso, copia o adaptación libre del código, siempre que se brinde el debido crédito a los autores originales y librerías utilizadas.

---

**Hecho en Perú 🇵🇪 con datos, fútbol y pasión.**
