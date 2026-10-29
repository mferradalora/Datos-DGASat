# 💧 Datos-DGASat: Monitor e Inventario de Estaciones DGA Chile

Plataforma integral de cartografía interactiva, almacenamiento en base de datos local y extracción automatizada de series de tiempo de la red hidrométrica, meteorológica y subterránea de la **Dirección General de Aguas (DGA)** del Ministerio de Obras Públicas de Chile (plataformas SNIA / DGASat).

---

## 🗺️ Enlaces del Proyecto en Producción

* **Mapa Interactivo Nacional (GitHub Pages):**  
  👉 **[https://mferradalora.github.io/Datos-DGASat/](https://mferradalora.github.io/Datos-DGASat/)**
* **Servicio Backend y Visor de Series (Render):**  
  👉 **[https://datos-dgasat.onrender.com](https://datos-dgasat.onrender.com)**

---

## ⚙️ ¿Cómo Funciona el Proyecto?

El sistema opera bajo una arquitectura desacoplada y eficiente diseñada para evitar la saturación y los tiempos de espera (*timeouts*) del servidor oficial de la DGA:

```text
[ Mapa en GitHub Pages ] (index.html)
           │
           │  Clic en "Descargar datos (Últimos 3 meses)"
           ▼  (Envía código BNA, nombre y período por URL)
[ Backend FastAPI en Render ] (main.py)
           │
           ├── ¿Existen mediciones recientes en la base de datos?
           │        ├── SÍ ──> Retorna datos al instante (< 0.1 s).
           │        └── NO ──> scraper.py consulta a la DGA, guarda en SQLite y retorna.
           ▼
[ Visor Ultraliviano ] (visor.html)
     ├── Gráfico interactivo Chart.js (Eje temporal en formato DD-MM-YYYY).
     ├── Encabezado con Código BNA y Nombre oficial de la estación.
     └── Exportación directa a CSV: [codigo_bna, nombre, variable, fecha_hora, valor].

---

## 📂 Estructura del Repositorio

```text
Datos-DGASat/
├── data/
│   ├── catalogo_completo_dga.csv    # Catálogo unificado (código BNA, nombre, coordenadas, tipo)
│   ├── Regiones_Chile.geojson       # Geometrías vectoriales de límites regionales
│   ├── Provincias_Chile.geojson     # Geometrías provinciales
│   ├── Comunas_Chile.geojson        # Geometrías comunales
│   ├── Cuencas_Chile.geojson        # Delimitación de cuencas hidrográficas
│   └── SHAC_Chile.geojson           # Sectores Hidrogeológicos de Aprovechamiento Común
├── database.py                      # Capa SQL: inicialización, almacenamiento y caché SQLite
├── main.py                          # Backend FastAPI: API REST y renderizado del visor
├── scraper.py                       # Motor de extracción de series de tiempo desde DGASat
├── visor.html                       # Frontend web ligero para graficar y descargar CSV
├── mapa.py                          # Generador del mapa interactivo con Folium nativo
├── index.html                       # Mapa web nacional desplegado en GitHub Pages
├── app.py                           # Aplicación complementaria en Streamlit
├── requirements.txt                 # Dependencias del servidor y de extracción
└── README.md                        # Documentación general del proyecto
