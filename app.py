#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import streamlit as st
import pandas as pd
from scraper import descargar_estaciones

st.set_page_config(
    page_title="Monitor Hidrológico DGA SAT",
    page_icon="💧",
    layout="wide"
)


@st.cache_data
def cargar_catalogo():
    ruta = "data/catalogo_completo_dga.csv"
    if not os.path.exists(ruta):
        st.error(f"No se encontró el archivo {ruta}. Verifica que esté en la carpeta data/ de tu repositorio.")
        return pd.DataFrame()

    df = pd.read_csv(ruta, dtype={"codigo_bna": str})
    
    # Normalización segura de encabezados compatible con todas las versiones de Pandas
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Formatear etiqueta descriptiva
    cod = df["codigo_bna"].fillna("").astype(str)
    nom = df["nombre"].fillna("").astype(str)
    df["etiqueta"] = cod + " - " + nom
    return df


df_cat = cargar_catalogo()

st.title("💧 Monitor Hidrológico DGA SAT (Chile)")
st.caption("Extracción en tiempo real de caudales, niveles freáticos y meteorología desde snia.mop.gob.cl")

if df_cat.empty:
    st.stop()

# --- BARRA LATERAL: FILTROS Y CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Filtros de Consulta")

    # 1. Filtro por Región
    regiones_disponibles = sorted([r for r in df_cat["region"].dropna().unique() if str(r).strip() and str(r).lower() != "nan"])
    region_sel = st.selectbox("1. Seleccione Región:", ["TODAS"] + regiones_disponibles)

    df_filtrado = df_cat if region_sel == "TODAS" else df_cat[df_cat["region"] == region_sel]

    # 2. Filtro por Tipo de Estación
    todos_tipos = set()
    for item in df_filtrado["tipo_estacion"].dropna():
        partes = [p.strip() for p in str(item).split("-")]
        todos_tipos.update(partes)

    tipos_ordenados = sorted(list(todos_tipos))
    tipo_sel = st.selectbox("2. Tipo de Estación:", ["TODOS"] + tipos_ordenados)

    if tipo_sel != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["tipo_estacion"].str.contains(tipo_sel, case=False, na=False)]

    st.write(f"**Estaciones disponibles:** {len(df_filtrado)}")

    # 3. Selección de Estaciones (Máximo 3)
    opciones_estaciones = df_filtrado["etiqueta"].tolist()
    estaciones_sel = st.multiselect(
        "3. Estaciones a consultar (Máx. 3):",
        options=opciones_estaciones,
        max_selections=3,
        help="El portal DGA SAT admite hasta 3 puntos simultáneos por lote."
    )

    # 4. Rango Temporal
    periodos = {
        "Últimas 24 horas": 1,
        "Últimos 7 días": 7,
        "Últimos 30 días": 30,
        "Últimos 90 días": 90
    }
    periodo_texto = st.radio("4. Período de datos:", list(periodos.keys()), index=1)
    dias_consulta = periodos[periodo_texto]

    btn_consultar = st.button("🚀 Consultar y Graficar", type="primary", use_container_width=True)

# --- ÁREA PRINCIPAL ---
if btn_consultar:
    if not estaciones_sel:
        st.warning("⚠️ Debes seleccionar al menos una estación antes de consultar.")
    else:
        codigos_consulta = [e.split(" - ")[0].strip() for e in estaciones_sel]

        with st.spinner(f"Descargando mediciones desde la DGA ({len(codigos_consulta)} estación(es), {dias_consulta} días)..."):
            df_mediciones = descargar_estaciones(codigos_consulta, dias=dias_consulta)

        if df_mediciones.empty:
            st.warning("No se encontraron registros de transmisión recientes para las estaciones seleccionadas en este intervalo.")
        else:
            df_mediciones = df_mediciones.merge(
                df_cat[["codigo_bna", "nombre"]],
                on="codigo_bna",
                how="left"
            )
            df_mediciones["serie"] = df_mediciones["codigo_bna"] + " (" + df_mediciones["variable"] + ")"

            st.success(f"Se obtuvieron **{len(df_mediciones):,}** lecturas exitosamente.")

            # Tarjetas de última medición
            cols_metricas = st.columns(len(codigos_consulta))
            for i, cod in enumerate(codigos_consulta):
                df_sub = df_mediciones[df_mediciones["codigo_bna"] == cod]
                with cols_metricas[i]:
                    if not df_sub.empty:
                        ult_reg = df_sub.iloc[-1]
                        fecha_str = ult_reg["fecha_hora"].strftime("%d/%m %H:%M") if hasattr(ult_reg["fecha_hora"], "strftime") else str(ult_reg["fecha_hora"])
                        st.metric(
                            label=f"{ult_reg.get('nombre', cod)}",
                            value=f"{ult_reg['valor']} {ult_reg['variable']}",
                            delta=f"Última: {fecha_str}"
                        )

            # Gráfico de series temporales
            st.subheader("📈 Series de Tiempo")
            df_pivot = df_mediciones.pivot_table(
                index="fecha_hora",
                columns="serie",
                values="valor"
            )
            st.line_chart(df_pivot, use_container_width=True)

            # Exportación de datos
            with st.expander("📄 Ver y descargar tabla de datos detallada"):
                st.dataframe(df_mediciones[["codigo_bna", "nombre", "variable", "fecha_hora", "valor"]], use_container_width=True)
                csv_bytes = df_mediciones.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label="📥 Descargar datos consolidados (CSV)",
                    data=csv_bytes,
                    file_name=f"dga_mediciones_{periodo_texto.replace(' ', '_').lower()}.csv",
                    mime="text/csv"
                )

# Mapa geográfico
if not df_filtrado.empty and "latitud" in df_filtrado.columns and "longitud" in df_filtrado.columns:
    df_mapa = df_filtrado.dropna(subset=["latitud", "longitud"]).copy()
    if not df_mapa.empty:
        with st.expander(f"🗺️ Ver ubicación de estaciones disponibles ({len(df_mapa)} en mapa)", expanded=False):
            st.map(df_mapa, latitude="latitud", longitude="longitud", size=20)
