# 💧 Datos-DGASat: Monitor e Inventario de Estaciones DGA Chile

Plataforma de procesamiento, cartografía y extracción automatizada de datos de la red de monitoreo hidrológico, meteorológico y subterráneo de la **Dirección General de Aguas (DGA)** del Ministerio de Obras Públicas de Chile (plataformas SNIA / DGASat).

---

## 🗺️ Acceso al Mapa Interactivo

Explora la ubicación, características técnicas y cobertura de todas las estaciones y pozos de monitoreo a nivel nacional:

👉 **[https://mferradalora.github.io/Datos-DGASat/](https://mferradalora.github.io/Datos-DGASat/)**

---

## 📌 Descripción del Proyecto

Este repositorio consolida el catálogo oficial georreferenciado de estaciones hidrométricas de Chile y automatiza la extracción de series de tiempo directas desde el portal DGASat sin intermediación de reCAPTCHA ni sesiones manuales.

### Tipos de estaciones integradas:
* **Fluviométricas:** Monitoreo de caudal ($m^3/s$) y nivel de agua en ríos y esteros.
* **Pozos de Monitoreo Subterráneo:** Control del nivel freático ($m$) en acuíferos y sectores hidrogeológicos de aprovechamiento común (SHAC).
* **Meteorológicas:** Registro de precipitación acumulada, temperatura, humedad y viento.
* **Glaciares y Nivométricas:** Sensores de alta montaña para balance de masa y equivalente en agua de nieve.
* **Lagos y Embalses:** Monitoreo de cotas y volúmenes de almacenamiento.

---

## 📂 Estructura del Repositorio

```text
Datos-DGASat/
├── data/
│   ├── catalogo_completo_dga.csv    # Catálogo unificado con código BNA, coordenadas y tipología
│   ├── Regiones_Chile.geojson       # Geometrías oficiales de límites regionales
│   ├── Provincias_Chile.geojson     # Geometrías oficiales de provincias
│   ├── Comunas_Chile.geojson        # Geometrías comunales
│   ├── Cuencas_Chile.geojson        # Delimitación de cuencas hidrográficas
│   └── SHAC_Chile.geojson           # Sectores Hidrogeológicos de Aprovechamiento Común
├── index.html                       # Visor cartográfico web desplegado en GitHub Pages
├── mapa.py                          # Generador del mapa interactivo con Folium nativo
├── scraper.py                       # Motor de consulta y extracción de series de tiempo
├── app.py                           # Aplicación web interactiva (Streamlit)
└── requirements.txt                 # Dependencias del proyecto
