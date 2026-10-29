# 💧 Datos-DGASatel

Plataforma integral de cartografía interactiva, almacenamiento en base de datos local, visualización y descarga de series de tiempo de los datos de la red de estaciones DGASatel de la **Dirección General de Aguas (DGA)** del Ministerio de Obras Públicas de Chile.
La información presentada es extraída directamente de los servicios **Hidrolínea (Mapa en línea) [https://www.mop.gob.cl/serviciosmop/hidrolinea-mapa-en-linea/](https://www.mop.gob.cl/serviciosmop/hidrolinea-mapa-en-linea/ )** y **DGASatel [https://www.mop.gob.cl/serviciosmop/dgasatel/](https://www.mop.gob.cl/serviciosmop/dgasatel/)** de la DGA.

---

## 🗺️ Enlaces del Proyecto

* **Mapa Interactivo Nacional (GitHub Pages):**  
  👉 **[https://mferradalora.github.io/Datos-DGASat/](https://mferradalora.github.io/Datos-DGASat/)**
* **Servicio Backend y Visor de Series (Render):**  
  👉 **[https://datos-dgasat.onrender.com](https://datos-dgasat.onrender.com)**

---

## ⚙️ ¿Cómo Funciona el Proyecto?

El sistema opera bajo una arquitectura desacoplada diseñada para evitar la saturación y los tiempos de espera (*timeouts*) del servidor oficial de la DGA:

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
```

  👉 **Visor Cartográfico (Frontend estático):** Alojado en GitHub Pages, permite explorar todo el inventario georreferenciado del país filtrando dinámicamente por región. Cada estación cuenta en su popup con un botón que enlaza directamente al visor de series de tiempo.

  👉 **Capa de Caché SQL (SQLite):** Gestionada por database.py, almacena de forma estructurada cada lectura obtenida, garantizando que consultas repetidas sobre una misma estación carguen de inmediato sin sobrecargar la red ministerial.

  👉 **Motor de Extracción Resiliente:** Implementado en scraper.py, realiza el handshake de sesión y la extracción de mediciones horarias/instantáneas mediante reintentos automáticos y correspondencia flexible de sensores.

  👉 **Exportación y Visualización:** Desplegado mediante visor.html, renderiza las curvas hidrológicas con Chart.js y permite descargar el archivo CSV consolidado con el nombre oficial de la estación y sus variables asociadas.

---

## 📌 Tipos de Estaciones Integradas

* Fluviométricas: Monitoreo de caudal ($m^3/s$) y nivel de agua en ríos, canales y esteros.
* Pozos de Monitoreo Subterráneo: Control del nivel freático ($m$) en acuíferos y Sectores Hidrogeológicos de Aprovechamiento Común (SHAC).
* Meteorológicas: Registro de precipitación acumulada, temperatura, humedad y variables climáticas.
* Glaciares y Nivométricas: Sensores de alta montaña para balance de masa y equivalente en agua de nieve.
* Lagos y Embalses: Monitoreo de cotas y volúmenes de almacenamiento superficial.3

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
