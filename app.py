#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import altair as alt
import pandas as pd
import streamlit as st
from scraper import descargar_estaciones

# Habilitar el renderizado de grandes volúmenes de datos en Altair
alt.data_transformers.disable_max_rows()

st.set_page_config(
    page_title="Monitor de Datos DGASat",
    page_icon="💧",
    layout="wide"
)


@st.cache_data
def cargar_catalogo():
    ruta = "data/catalogo_completo_dga.csv"
    if not os.path.exists(ruta):
        st.error(f"No se encontró el archivo {ruta}.")
        return pd.DataFrame()

    df = pd.read_csv(ruta, dtype={"codigo_bna": str})
    df.columns = [str(c).strip().lower() for c in df.columns]
    cod = df["codigo_bna"].fillna("").astype(str)
    nom = df["nombre"].fillna("").astype(str)
    df["etiqueta"] = cod + " - " + nom
    return df


df_cat = cargar_catalogo()

st.title("💧 Monitor Hidrológico DGA SAT (Chile)")
st.caption("Extracción en tiempo real desde snia.mop.gob.cl")

if df_cat.empty:
    st.stop()

# --- LECTURA DE PARÁMETROS DEL MAPA (DEEP LINKING) ---
params = st.query_params
codigo_url = params.get("codigo", None)
dias_url = int(params.get("dias", 7))

estacion_inicial = []
region_default_idx = 0

if codigo_url:
    match_est = df_cat[df_cat["codigo_bna"] == codigo_url]
    if not match_est.empty:
        estacion_inicial = [match_est.iloc[0]["etiqueta"]]
        reg_estacion = match_est.iloc[0]["region"]
        regiones_disponibles = sorted([
            r for r in df_cat["region"].dropna().unique()
            if str(r).strip() and str(r).lower() != "nan"
        ])
        if reg_estacion in regiones_disponibles:
            region_default_idx = regiones_disponibles.index(reg_estacion) + 1
else:
    regiones_disponibles = sorted([
        r for r in df_cat["region"].dropna().unique()
        if str(r).strip() and str(r).lower() != "nan"
    ])

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("⚙️ Filtros de Consulta")

    region_sel = st.selectbox(
        "1. Seleccione Región:",
        ["TODAS"] + regiones_disponibles,
        index=region_default_idx
    )

    df_filtrado = df_cat if region_sel == "TODAS" else df_cat[df_cat["region"] == region_sel]

    todos_tipos = set()
    for item in df_filtrado["tipo_estacion"].dropna():
        partes = [p.strip() for p in str(item).split("-")]
        todos_tipos.update(partes)

    tipos_ordenados = sorted(list(todos_tipos))
    tipo_sel = st.selectbox("2. Tipo de Estación:", ["TODOS"] + tipos_ordenados)

    if tipo_sel != "TODOS":
        df_filtrado = df_filtrado[df_filtrado["tipo_estacion"].str.contains(tipo_sel, case=False, na=False)]

    opciones_estaciones = df_filtrado["etiqueta"].tolist()
    for est in estacion_inicial:
        if est not in opciones_estaciones:
            opciones_estaciones.append(est)

    estaciones_sel = st.multiselect(
        "3. Estaciones a consultar (Máx. 3):",
        options=opciones_estaciones,
        default=estacion_inicial,
        max_selections=3
    )

    periodos = {
        "Últimas 24 horas": 1,
        "Últimos 7 días": 7,
        "Últimos 30 días": 30,
        "Últimos 90 días": 90
    }

    idx_periodo = 3 if dias_url == 90 else (2 if dias_url == 30 else (0 if dias_url == 1 else 1))
    periodo_texto = st.radio("4. Período de datos:", list(periodos.keys()), index=idx_periodo)
    dias_consulta = periodos[periodo_texto]

    btn_consultar = st.button("🚀 Consultar y Graficar", type="primary", width="stretch")

debe_ejecutar = btn_consultar or (bool(codigo_url) and "auto_ejecutado" not in st.session_state)

# --- ÁREA PRINCIPAL ---
if debe_ejecutar:
    if codigo_url:
        st.session_state["auto_ejecutado"] = True

    if not estaciones_sel:
        st.warning("⚠️ Debes seleccionar al menos una estación.")
    else:
        codigos_consulta = [e.split(" - ")[0].strip() for e in estaciones_sel]

        df_mediciones = pd.DataFrame()
        with st.spinner(f"Descargando mediciones desde la DGA ({len(codigos_consulta)} estación(es), {dias_consulta} días)..."):
            try:
                df_mediciones = descargar_estaciones(codigos_consulta, dias=dias_consulta)
            except TimeoutError:
                st.error("⏱️ Tiempo de espera agotado al conectar con la DGA. Intente nuevamente.")
            except Exception as e:
                st.error(f"⚠️ Error al consultar: {e}")

        if not df_mediciones.empty:
            df_mediciones["fecha_hora"] = pd.to_datetime(df_mediciones["fecha_hora"])
            df_mediciones = df_mediciones.merge(
                df_cat[["codigo_bna", "nombre"]],
                on="codigo_bna",
                how="left"
            )
            df_mediciones["serie"] = df_mediciones["codigo_bna"] + " (" + df_mediciones["variable"] + ")"

            st.success(f"Se obtuvieron **{len(df_mediciones):,}** lecturas exitosamente.")

            # --- GRÁFICO ALTAIR CON EJE X EN FORMATO DD-MM-YYYY ---
            st.subheader("📈 Series de Tiempo")
            chart = (
                alt.Chart(df_mediciones)
                .mark_line()
                .encode(
                    x=alt.X(
                        "fecha_hora:T",
                        title="Fecha",
                        axis=alt.Axis(
                            format="%d-%m-%Y",
                            labelAngle=-45
                        )
                    ),
                    y=alt.Y("valor:Q", title="Valor"),
                    color=alt.Color("serie:N", title="Serie / Variable"),
                    tooltip=[
                        alt.Tooltip("fecha_hora:T", format="%d-%m-%Y %H:%M", title="Fecha y Hora"),
                        alt.Tooltip("serie:N", title="Serie"),
                        alt.Tooltip("valor:Q", title="Valor", format=".2f")
                    ]
                )
                .properties(height=420)
                .interactive()
            )
            st.altair_chart(chart, width="stretch")

            # --- TABLA Y DESCARGA CSV ---
            with st.expander("📄 Ver y descargar tabla de datos detallada", expanded=False):
                st.dataframe(
                    df_mediciones[["codigo_bna", "nombre", "variable", "fecha_hora", "valor"]],
                    width="stretch"
                )
                csv_bytes = df_mediciones.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label="📥 Descargar datos consolidados (CSV)",
                    data=csv_bytes,
                    file_name=f"dga_{codigos_consulta[0]}_{dias_consulta}dias.csv",
                    mime="text/csv",
                    width="stretch"
                )
