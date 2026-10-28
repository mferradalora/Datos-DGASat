#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generador de Mapa Interactivo Nacional DGA SAT.
Filtro exclusivo por Región y polígonos no interactivos (sin sombreado hover).
Salida: index.html (Optimizado para GitHub Pages).
"""

import json
import re
import unicodedata
from pathlib import Path
from branca.element import Element
import geopandas as gpd
import pandas as pd
import folium

carpeta_data = Path("data")
path_csv = carpeta_data / "catalogo_completo_dga.csv"
path_regiones = carpeta_data / "Regiones_Chile.geojson"

# Lista de Regiones de Norte a Sur y sus palabras clave para mapeo
REGIONES_CHILE = {
    "Arica y Parinacota": ["arica", "parinacota"],
    "Tarapacá": ["tarapaca"],
    "Antofagasta": ["antofagasta"],
    "Atacama": ["atacama"],
    "Coquimbo": ["coquimbo"],
    "Valparaíso": ["valparaiso"],
    "Metropolitana": ["metropolitana", "santiago"],
    "O'Higgins": ["higgins"],
    "Maule": ["maule"],
    "Ñuble": ["nuble"],
    "Biobío": ["biobio", "bio bio"],
    "La Araucanía": ["araucania"],
    "Los Ríos": ["los rios", "valdivia"],
    "Los Lagos": ["los lagos", "llanquihue"],
    "Aysén": ["aysen", "aisen"],
    "Magallanes": ["magallanes"]
}


def normalizar_texto(texto):
    if pd.isna(texto):
        return ""
    s = str(texto).lower()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return ' '.join(s.split())


def filtrar_poligono_region(gdf, palabras_clave):
    if gdf.empty:
        return gdf.iloc[0:0]
    for col in gdf.columns:
        if col != gdf.geometry.name:
            col_norm = gdf[col].astype(str).apply(normalizar_texto)
            for palabra in palabras_clave:
                p_norm = normalizar_texto(palabra)
                coincidencias = gdf[col_norm.str.contains(p_norm, na=False, regex=False)]
                if not coincidencias.empty:
                    return coincidencias
    return gdf.iloc[0:0]


print("🔄 1. Cargando catálogos y límites regionales...")
df_csv = pd.read_csv(path_csv, dtype={"codigo_bna": str})
df_csv.columns = [str(c).strip().lower() for c in df_csv.columns]

# Limpieza de coordenadas geográficas
df_csv["latitud"] = pd.to_numeric(df_csv["latitud"], errors="coerce")
df_csv["longitud"] = pd.to_numeric(df_csv["longitud"], errors="coerce")
df_csv = df_csv.dropna(subset=["latitud", "longitud"]).copy()
df_csv = df_csv[(df_csv["latitud"] != 0) & (df_csv["longitud"] != 0)]
df_csv["region_norm"] = df_csv["region"].astype(str).apply(normalizar_texto)

gdf_regiones_raw = gpd.read_file(path_regiones)
if gdf_regiones_raw.crs is None:
    gdf_regiones_raw = gdf_regiones_raw.set_crs(epsg=4326)
elif gdf_regiones_raw.crs.to_epsg() != 4326:
    gdf_regiones_raw = gdf_regiones_raw.to_crs(epsg=4326)


def obtener_color_tipo(tipo_str):
    t = str(tipo_str).lower()
    if "fluvio" in t:
        return {"color": "#0284c7", "fillColor": "#38bdf8", "etiqueta": "Fluviométrica (Caudal)"}
    elif "pozo" in t:
        return {"color": "#d97706", "fillColor": "#fbbf24", "etiqueta": "Control Nivel Pozo"}
    elif "glaciar" in t:
        return {"color": "#0891b2", "fillColor": "#67e8f9", "etiqueta": "Glaciares y Nieve"}
    elif "lago" in t or "embalse" in t:
        return {"color": "#7c3aed", "fillColor": "#c084fc", "etiqueta": "Lagos y Embalses"}
    else:
        return {"color": "#059669", "fillColor": "#34d399", "etiqueta": "Meteorológica"}


print("🗺️ 2. Inicializando mapa base...")
mapa_web = folium.Map(location=[-35.6751, -71.5430], zoom_start=4, tiles=None)
folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap", overlay=False, control=True, show=True).add_to(mapa_web)
folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Híbrido", overlay=False, control=True, show=False).add_to(mapa_web)
folium.TileLayer(tiles="CartoDB positron", name="CartoDB Claro", overlay=False, control=True, show=False).add_to(mapa_web)

region_dict_js = {}
options_html = ""

print("🛠️ 3. Agrupando estaciones y límites por Región...")

for region_nom, claves in REGIONES_CHILE.items():
    reg_key = normalizar_texto(region_nom).replace(' ', '_')
    capa_reg = filtrar_poligono_region(gdf_regiones_raw, claves)

    # Filtrar estaciones del CSV que pertenezcan a esta región
    patron_claves = "|".join([normalizar_texto(k) for k in claves])
    df_reg = df_csv[df_csv["region_norm"].str.contains(patron_claves, na=False, regex=True)].copy()

    if capa_reg.empty and df_reg.empty:
        continue

    # Calcular encuadre geográfico (bounds)
    if not capa_reg.empty:
        xmin, ymin, xmax, ymax = capa_reg.total_bounds
        bounds_reg = [[ymin, xmin], [ymax, xmax]]
    else:
        bounds_reg = [[df_reg["latitud"].min(), df_reg["longitud"].min()],
                      [df_reg["latitud"].max(), df_reg["longitud"].max()]]

    # FeatureGroup único para la región (contiene polígono y marcadores)
    fg_region = folium.FeatureGroup(name=f"Región {region_nom}", overlay=True, show=True, control=False)

    # 1. Polígono del límite regional
    # interactive=False desactiva el sombreado hover y eventos del mouse al pasar por encima
    if not capa_reg.empty:
        folium.GeoJson(
            capa_reg,
            name=f"Límite {region_nom}",
            interactive=False,
            style_function=lambda x: {
                "color": "#1e293b",
                "fillOpacity": 0,
                "weight": 2.0,
                "interactive": False
            }
        ).add_to(fg_region)

    # 2. Marcadores de estaciones de la región
    for _, row in df_reg.iterrows():
        estilo = obtener_color_tipo(row.get("tipo_estacion", ""))
        
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 210px;">
            <b style="color: {estilo['color']}; font-size: 13px;">{row.get('nombre', '')}</b><br>
            <b>Código BNA:</b> {row.get('codigo_bna', '')}<br>
            <b>Tipo:</b> {row.get('tipo_estacion', '')}<br>
            <b>Región:</b> {row.get('region', '')}<br>
            <b>Transmisión:</b> {row.get('fuente', '')}<br>
            <b>Altitud:</b> {row.get('altitud', '')} msnm<br>
            <b>Coordenadas:</b> {row.get('latitud', ''):.4f}, {row.get('longitud', ''):.4f}
            
            <div style="margin-top: 10px; padding-top: 8px; border-top: 1px solid #e2e8f0; text-align: center;">
                <a href="https://datos-dgasat.streamlit.app/?codigo={row.get('codigo_bna', '')}&dias=90" 
                   target="_blank" 
                   style="display: block; background-color: #0284c7; color: white; padding: 7px 10px; font-size: 11px; font-weight: bold; text-decoration: none; border-radius: 4px; box-shadow: 0 1px 2px rgba(0,0,0,0.15);">
                    📥 Descargar datos (Últimos 3 meses)
                </a>
            </div>
        </div>
        """
        folium.CircleMarker(
            location=[row["latitud"], row["longitud"]],
            radius=5.5,
            color=estilo["color"],
            fill=True,
            fill_color=estilo["fillColor"],
            fill_opacity=0.85,
            weight=1.5,
            tooltip=f"<b>{row.get('codigo_bna', '')}</b> - {row.get('nombre', '')}",
            popup=folium.Popup(popup_html, max_width=320)
        ).add_to(fg_region)

    fg_region.add_to(mapa_web)

    region_dict_js[reg_key] = {
        "name": region_nom,
        "var": fg_region.get_name(),
        "bounds": bounds_reg,
        "total_estaciones": len(df_reg)
    }
    options_html += f'<option value="{reg_key}">{region_nom} ({len(df_reg)})</option>\n'

# 4. Inyección del selector exclusivo por Región
menu_control_html = f"""
<div style="position: fixed; top: 14px; left: 60px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; min-width: 250px;">
    <div style="font-weight: bold; font-size: 14px; color: #0284c7; margin-bottom: 8px;">💧 Red DGASat Chile</div>
    <label for="regionSelect" style="font-weight: 600; font-size: 12px; color: #334155;">Seleccionar Región:</label><br>
    <select id="regionSelect" onchange="cambiarRegion(this.value)" style="margin-top: 6px; padding: 6px 10px; font-size: 12px; border-radius: 4px; border: 1px solid #cbd5e1; width: 100%; cursor: pointer;">
        <option value="">-- Todo el País --</option>
        {options_html}
    </select>
</div>

<script>
var regionDict = {json.dumps(region_dict_js)};

function cambiarRegion(regKey) {{
    var map = {mapa_web.get_name()};

    if (regKey === "") {{
        for (var r in regionDict) {{
            var fg = window[regionDict[r].var];
            if (fg && !map.hasLayer(fg)) {{
                map.addLayer(fg);
            }}
        }}
        map.setView([-35.6751, -71.5430], 4);
    }} else {{
        for (var r in regionDict) {{
            var fg = window[regionDict[r].var];
            if (fg) {{
                if (r === regKey) {{
                    if (!map.hasLayer(fg)) map.addLayer(fg);
                }} else {{
                    if (map.hasLayer(fg)) map.removeLayer(fg);
                }}
            }}
        }}
        map.fitBounds(regionDict[regKey].bounds);
    }}
}}
</script>
"""

# 5. Inyección de Leyenda Temática
leyenda_html = """
<div style="position: fixed; bottom: 25px; right: 12px; z-index: 1000; background: white; padding: 10px 14px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.25); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 11px;">
    <div style="font-weight: bold; font-size: 12px; color: #1e293b; margin-bottom: 6px;">Simbología DGA</div>
    <div style="display: flex; align-items: center; margin-bottom: 4px;">
        <span style="height: 10px; width: 10px; background-color: #38bdf8; border: 1.5px solid #0284c7; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
        <span>Fluviométrica (Caudal)</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 4px;">
        <span style="height: 10px; width: 10px; background-color: #fbbf24; border: 1.5px solid #d97706; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
        <span>Control Nivel Pozo</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 4px;">
        <span style="height: 10px; width: 10px; background-color: #34d399; border: 1.5px solid #059669; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
        <span>Meteorológica</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 4px;">
        <span style="height: 10px; width: 10px; background-color: #67e8f9; border: 1.5px solid #0891b2; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
        <span>Glaciares y Nieve</span>
    </div>
    <div style="display: flex; align-items: center; margin-bottom: 6px;">
        <span style="height: 10px; width: 10px; background-color: #c084fc; border: 1.5px solid #7c3aed; border-radius: 50%; display: inline-block; margin-right: 6px;"></span>
        <span>Lagos y Embalses</span>
    </div>
    <hr style="margin: 4px 0 4px 0; border: 0; border-top: 1px solid #e2e8f0;">
    <div style="color: #64748b; font-size: 10px;">Portal Satelital DGA Chile</div>
</div>
"""

mapa_web.get_root().html.add_child(Element(menu_control_html))
mapa_web.get_root().html.add_child(Element(leyenda_html))
folium.LayerControl(collapsed=True).add_to(mapa_web)

archivo_salida = "index.html"
mapa_web.save(archivo_salida)
print(f"\n🚀 ¡Éxito! Mapa generado en '{archivo_salida}'.")
