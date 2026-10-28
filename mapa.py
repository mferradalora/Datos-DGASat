#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Generador de Mapa Interactivo Nacional DGA SAT con Folium y GeoPandas.
Salida: index.html (Optimizado para despliegue directo en GitHub Pages).
"""

import json
import re
import unicodedata
from pathlib import Path
from branca.element import Element
import geopandas as gpd
import numpy as np
import pandas as pd
import folium

# Rutas de entrada relativas al repositorio
carpeta_data = Path("data")
path_csv = carpeta_data / "catalogo_completo_dga.csv"
path_regiones = carpeta_data / "Regiones_Chile.geojson"
path_provincias = carpeta_data / "Provincias_Chile.geojson"

# 1. Diccionario de Regiones y Provincias Oficiales
regiones_provincias = {
    "Arica y Parinacota": ["Arica", "Parinacota"],
    "Tarapaca": ["Iquique", "Tamarugal"],
    "Antofagasta": ["Tocopilla", "El Loa", "Antofagasta"],
    "Atacama": ["Chañaral", "Copiapó", "Huasco"],
    "Coquimbo": ["Elqui", "Limarí", "Choapa"],
    "Valparaiso": ["Petorca", "Los Andes", "San Felipe", "Quillota", "Valparaíso", "San Antonio", "Isla de Pascua", "Marga Marga"],
    "Metropolitana": ["Chacabuco", "Santiago", "Cordillera", "Maipo", "Melipilla", "Talagante"],
    "O'Higgins": ["Cachapoal", "Colchagua", "Cardenal Caro"],
    "Maule": ["Curicó", "Talca", "Linares", "Cauquenes"],
    "Nuble": ["Diguillín", "Itata", "Punilla"],
    "Bio Bio": ["Bio-Bio", "Concepción", "Arauco"],
    "Araucania": ["Malleco", "Cautín"],
    "Los Rios": ["Valdivia", "Ranco"],
    "Los Lagos": ["Osorno", "Llanquihue", "Chiloé", "Palena"],
    "Aysen": ["Coyhaique", "Aysén", "General Carrera", "Capitán Prat"],
    "Magallanes": ["Última Esperanza", "Magallanes", "Tierra del Fuego", "Antártica Chilena"]
}


def normalizar_texto(texto):
    if pd.isna(texto):
        return ""
    s = str(texto).lower()
    s = ''.join(c for c in unicodedata.normalize('NFKD', s) if unicodedata.category(c) != 'Mn')
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    return ' '.join(s.split())


def filtrar_layer_local(gdf, nombre_busqueda):
    if gdf.empty:
        return gdf.iloc[0:0]
    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4326)
    elif gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)

    target_norm = normalizar_texto(nombre_busqueda)
    for col in gdf.columns:
        if col != gdf.geometry.name:
            col_norm = gdf[col].astype(str).apply(normalizar_texto)
            matches = gdf[col_norm.str.contains(target_norm, na=False, regex=False)]
            if not matches.empty:
                return matches
    return gdf.iloc[0:0]


print("🔄 1. Cargando catálogos y capas geográficas...")
df_csv = pd.read_csv(path_csv, dtype={"codigo_bna": str})
df_csv.columns = [str(c).strip().lower() for c in df_csv.columns]

# Limpiar coordenadas válidas
df_csv["latitud"] = pd.to_numeric(df_csv["latitud"], errors="coerce")
df_csv["longitud"] = pd.to_numeric(df_csv["longitud"], errors="coerce")
df_csv = df_csv.dropna(subset=["latitud", "longitud"]).copy()
df_csv = df_csv[(df_csv["latitud"] != 0) & (df_csv["longitud"] != 0)]

gdf_regiones_raw = gpd.read_file(path_regiones)
gdf_provincias_raw = gpd.read_file(path_provincias)

if gdf_regiones_raw.crs != "EPSG:4326":
    gdf_regiones_raw = gdf_regiones_raw.to_crs(epsg=4326)
if gdf_provincias_raw.crs != "EPSG:4326":
    gdf_provincias_raw = gdf_provincias_raw.to_crs(epsg=4326)

# Convertir estaciones a GeoDataFrame puntual WGS84
gdf_estaciones_nac = gpd.GeoDataFrame(
    df_csv,
    geometry=gpd.points_from_xy(df_csv["longitud"], df_csv["latitud"]),
    crs="EPSG:4326"
)

# Cruce espacial para determinar la Provincia oficial de cada estación
col_prov_nombre = next((c for c in gdf_provincias_raw.columns if "nom" in c.lower() or "prov" in c.lower()), gdf_provincias_raw.columns[0])
gdf_estaciones_nac = gpd.sjoin(
    gdf_estaciones_nac,
    gdf_provincias_raw[[col_prov_nombre, "geometry"]].rename(columns={col_prov_nombre: "provincia_gis"}),
    how="left",
    predicate="within"
)
gdf_estaciones_nac["provincia_gis"] = gdf_estaciones_nac["provincia_gis"].fillna("Sin Provincia")
gdf_estaciones_nac["region_norm"] = gdf_estaciones_nac["region"].astype(str).apply(normalizar_texto)
gdf_estaciones_nac["provincia_norm"] = gdf_estaciones_nac["provincia_gis"].astype(str).apply(normalizar_texto)


# 2. Función de estilo por Tipo de Estación
def obtener_color_tipo(tipo_str):
    t = str(tipo_str).lower()
    if "fluvio" in t:
        return {"color": "#0284c7", "fillColor": "#38bdf8", "tipo_grupo": "Fluviométrica (Caudal)"}
    elif "pozo" in t:
        return {"color": "#d97706", "fillColor": "#fbbf24", "tipo_grupo": "Nivel de Pozo (Subterráneo)"}
    elif "glaciar" in t:
        return {"color": "#0891b2", "fillColor": "#67e8f9", "tipo_grupo": "Glaciares y Nieve"}
    elif "lago" in t or "embalse" in t:
        return {"color": "#7c3aed", "fillColor": "#c084fc", "tipo_grupo": "Lagos y Embalses"}
    else:
        return {"color": "#059669", "fillColor": "#34d399", "tipo_grupo": "Meteorológica"}


print("🗺️ 2. Inicializando mapa base...")
mapa_web = folium.Map(location=[-35.6751, -71.5430], zoom_start=4, tiles=None)
folium.TileLayer(tiles="OpenStreetMap", name="OpenStreetMap", overlay=False, control=True, show=True).add_to(mapa_web)
folium.TileLayer(tiles="https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", attr="Google", name="Google Híbrido", overlay=False, control=True, show=False).add_to(mapa_web)
folium.TileLayer(tiles="CartoDB positron", name="CartoDB Claro", overlay=False, control=True, show=False).add_to(mapa_web)

region_dict_js = {}
prov_dict_js = {}
options_html = ""

print("🛠️ 3. Construyendo capas regionales y marcadores...")

for region_nom, provincias in regiones_provincias.items():
    reg_key = normalizar_texto(region_nom).replace(' ', '_')
    capa_reg = filtrar_layer_local(gdf_regiones_raw, region_nom)

    target_norm_reg = normalizar_texto(region_nom)
    gdf_reg = gdf_estaciones_nac[gdf_estaciones_nac["region_norm"].str.contains(target_norm_reg, na=False)].copy()

    if capa_reg.empty and gdf_reg.empty:
        continue

    if not capa_reg.empty:
        xmin, ymin, xmax, ymax = capa_reg.total_bounds
        bounds_reg = [[ymin, xmin], [ymax, xmax]]
    else:
        bounds_reg = [[gdf_reg["latitud"].min(), gdf_reg["longitud"].min()],
                      [gdf_reg["latitud"].max(), gdf_reg["longitud"].max()]]

    region_dict_js[reg_key] = {
        "name": region_nom,
        "bounds": bounds_reg,
        "provinces": [],
        "border_var": f"fg_border_{reg_key}"
    }
    options_html += f'<option value="{reg_key}">{region_nom}</option>\n'

    # Límite regional
    fg_border = folium.FeatureGroup(name=f"Límite {region_nom}", overlay=True, show=True, control=False)
    if not capa_reg.empty:
        capa_reg.explore(m=fg_border, color="#0f172a", style_kwds={"fillOpacity": 0, "weight": 2.2}, tooltip=False, popup=False)
    fg_border.add_to(mapa_web)

    obras_asignadas_idx = set()

    for prov_nom in provincias:
        prov_key = normalizar_texto(prov_nom).replace(' ', '_') + "_" + reg_key
        capa_prov = filtrar_layer_local(gdf_provincias_raw, prov_nom)

        target_norm_prov = normalizar_texto(prov_nom)
        gdf_prov = gdf_reg[gdf_reg["provincia_norm"].str.contains(target_norm_prov, na=False)].copy()
        obras_asignadas_idx.update(gdf_prov.index)

        fg_prov = folium.FeatureGroup(name=f"Prov. {prov_nom}", overlay=True, show=True, control=False)

        if not capa_prov.empty:
            capa_prov.explore(m=fg_prov, color="#64748b", style_kwds={"fillOpacity": 0.03, "weight": 1.2, "dashArray": "4, 4"}, tooltip=False, popup=False)
            pxmin, pymin, pxmax, pymax = capa_prov.total_bounds
            p_bounds = [[pymin, pxmin], [pymax, pxmax]]
        else:
            p_bounds = bounds_reg

        # Inserción de marcadores
        for _, row in gdf_prov.iterrows():
            estilo = obtener_color_tipo(row.get("tipo_estacion", ""))
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 200px;">
                <b style="color: {estilo['color']}; font-size: 13px;">{row.get('nombre', '')}</b><br>
                <b>Código BNA:</b> {row.get('codigo_bna', '')}<br>
                <b>Tipo:</b> {row.get('tipo_estacion', '')}<br>
                <b>Provincia:</b> {row.get('provincia_gis', '')}<br>
                <b>Región:</b> {row.get('region', '')}<br>
                <b>Transmisión:</b> {row.get('fuente', '')}<br>
                <b>Altitud:</b> {row.get('altitud', '')} msnm<br>
                <b>Coordenadas:</b> {row.get('latitud', ''):.4f}, {row.get('longitud', ''):.4f}
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
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(fg_prov)

        fg_prov.add_to(mapa_web)
        prov_dict_js[prov_key] = {
            "name": prov_nom,
            "var": fg_prov.get_name(),
            "bounds": p_bounds
        }
        region_dict_js[reg_key]["provinces"].append(prov_key)

    # Estaciones sin provincia asignada
    gdf_huerfanas = gdf_reg[~gdf_reg.index.isin(obras_asignadas_idx)]
    if not gdf_huerfanas.empty:
        h_key = "resto_" + reg_key
        fg_huerfana = folium.FeatureGroup(name="Otras Estaciones", overlay=True, show=True, control=False)
        for _, row in gdf_huerfanas.iterrows():
            estilo = obtener_color_tipo(row.get("tipo_estacion", ""))
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; font-size: 12px; min-width: 200px;">
                <b style="color: {estilo['color']}; font-size: 13px;">{row.get('nombre', '')}</b><br>
                <b>Código BNA:</b> {row.get('codigo_bna', '')}<br>
                <b>Tipo:</b> {row.get('tipo_estacion', '')}<br>
                <b>Región:</b> {row.get('region', '')}<br>
                <b>Transmisión:</b> {row.get('fuente', '')}<br>
                <b>Altitud:</b> {row.get('altitud', '')} msnm
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
                popup=folium.Popup(popup_html, max_width=300)
            ).add_to(fg_huerfana)
        fg_huerfana.add_to(mapa_web)
        prov_dict_js[h_key] = {"name": "Otras Estaciones", "var": fg_huerfana.get_name(), "bounds": bounds_reg}
        region_dict_js[reg_key]["provinces"].append(h_key)


# 4. Inyección del Panel de Navegación (JavaScript Nativo)
menu_control_html = f"""
<div style="position: fixed; top: 14px; left: 60px; z-index: 1000; background: white; padding: 12px 16px; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.25); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; min-width: 250px;">
    <div style="font-weight: bold; font-size: 14px; color: #0284c7; margin-bottom: 8px;">💧 Red DGA SAT Chile</div>
    <label for="regionSelect" style="font-weight: 600; font-size: 12px; color: #334155;">Región:</label><br>
    <select id="regionSelect" onchange="cambiarRegion(this.value)" style="margin-top: 4px; margin-bottom: 10px; padding: 6px; font-size: 12px; border-radius: 4px; border: 1px solid #cbd5e1; width: 100%; cursor: pointer;">
        <option value="">-- Todo el País --</option>
        {options_html}
    </select>
    
    <label for="provinciaSelect" style="font-weight: 600; font-size: 12px; color: #334155;">Provincia:</label><br>
    <select id="provinciaSelect" onchange="cambiarProvincia(this.value)" style="margin-top: 4px; padding: 6px; font-size: 12px; border-radius: 4px; border: 1px solid #cbd5e1; width: 100%; cursor: pointer; background-color: #f8fafc;" disabled>
        <option value="">-- Todas las Provincias --</option>
    </select>
</div>

<script>
var regionDict = {json.dumps(region_dict_js)};
var provDict = {json.dumps(prov_dict_js)};

function mostrarTodo() {{
    var map = {mapa_web.get_name()};
    for (var r in regionDict) {{
        var fgBorder = window[regionDict[r].border_var];
        if (fgBorder && !map.hasLayer(fgBorder)) map.addLayer(fgBorder);
        regionDict[r].provinces.forEach(function(pKey) {{
            var fgProv = window[provDict[pKey].var];
            if (fgProv && !map.hasLayer(fgProv)) map.addLayer(fgProv);
        }});
    }}
}}

function ocultarTodo() {{
    var map = {mapa_web.get_name()};
    for (var r in regionDict) {{
        var fgBorder = window[regionDict[r].border_var];
        if (fgBorder && map.hasLayer(fgBorder)) map.removeLayer(fgBorder);
        regionDict[r].provinces.forEach(function(pKey) {{
            var fgProv = window[provDict[pKey].var];
            if (fgProv && map.hasLayer(fgProv)) map.removeLayer(fgProv);
        }});
    }}
}}

function cambiarRegion(regKey) {{
    var map = {mapa_web.get_name()};
    var provSelect = document.getElementById("provinciaSelect");
    provSelect.innerHTML = '<option value="">-- Todas las Provincias --</option>';
    ocultarTodo();

    if (regKey === "") {{
        provSelect.disabled = true;
        provSelect.style.backgroundColor = "#f8fafc";
        mostrarTodo();
        map.setView([-35.6751, -71.5430], 4);
    }} else {{
        provSelect.disabled = false;
        provSelect.style.backgroundColor = "#ffffff";
        var fgBorder = window[regionDict[regKey].border_var];
        if (fgBorder && !map.hasLayer(fgBorder)) map.addLayer(fgBorder);

        regionDict[regKey].provinces.forEach(function(pKey) {{
            var pData = provDict[pKey];
            var fgProv = window[pData.var];
            if (fgProv && !map.hasLayer(fgProv)) map.addLayer(fgProv);
            var opt = document.createElement("option");
            opt.value = pKey;
            opt.text = pData.name;
            provSelect.add(opt);
        }});
        map.fitBounds(regionDict[regKey].bounds);
    }}
}}

function cambiarProvincia(provKey) {{
    var map = {mapa_web.get_name()};
    var regKey = document.getElementById("regionSelect").value;
    if (!regKey) return;
    ocultarTodo();

    var fgBorder = window[regionDict[regKey].border_var];
    if (fgBorder && !map.hasLayer(fgBorder)) map.addLayer(fgBorder);

    if (provKey === "") {{
        regionDict[regKey].provinces.forEach(function(pKey) {{
            var fgProv = window[provDict[pKey].var];
            if (fgProv && !map.hasLayer(fgProv)) map.addLayer(fgProv);
        }});
        map.fitBounds(regionDict[regKey].bounds);
    }} else {{
        var fgProv = window[provDict[provKey].var];
        if (fgProv && !map.hasLayer(fgProv)) map.addLayer(fgProv);
        map.fitBounds(provDict[provKey].bounds);
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
print(f"\n🚀 ¡Mapa interactivo generado exitosamente como '{archivo_salida}'!")
