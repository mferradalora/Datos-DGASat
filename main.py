#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
import pandas as pd
from database import inicializar_db, guardar_mediciones, consultar_datos_locales, verificar_necesidad_scraping
from scraper import descargar_estaciones

inicializar_db()
app = FastAPI(title="Servicio de Series DGA")

CATALOGO_PATH = "data/catalogo_completo_dga.csv"


def obtener_nombre_estacion(codigo_bna: str) -> str:
    """Busca el nombre oficial tolerando diferencias de ceros o formato BNA."""
    if os.path.exists(CATALOGO_PATH):
        try:
            df_cat = pd.read_csv(CATALOGO_PATH, dtype={"codigo_bna": str})
            df_cat.columns = [str(c).strip().lower() for c in df_cat.columns]
            cod_limpio = str(codigo_bna).strip().upper()

            # 1. Coincidencia exacta
            m = df_cat[df_cat["codigo_bna"].astype(str).str.strip().str.upper() == cod_limpio]
            if not m.empty:
                return str(m.iloc[0]["nombre"]).strip()

            # 2. Coincidencia flexible sin ceros a la izquierda
            base_buscado = cod_limpio.split("-")[0].lstrip("0")
            for _, row in df_cat.iterrows():
                bna_row = str(row.get("codigo_bna", "")).strip().upper()
                if bna_row.split("-")[0].lstrip("0") == base_buscado and len(base_buscado) > 0:
                    return str(row.get("nombre", "")).strip()
        except Exception as e:
            print(f"Aviso al consultar catálogo: {e}", flush=True)
    return ""


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/api/info_estacion")
def info_estacion(codigo: str = Query(...)):
    """Retorna el nombre oficial de la estación independientemente de si tiene mediciones."""
    cod = codigo.strip()
    return {"codigo_bna": cod, "nombre": obtener_nombre_estacion(cod)}


@app.get("/api/datos")
def obtener_series(codigo: str = Query(...), dias: int = Query(90)):
    codigo = codigo.strip()
    nombre = obtener_nombre_estacion(codigo)

    if verificar_necesidad_scraping(codigo, dias):
        try:
            df_nuevo = descargar_estaciones([codigo], dias=dias)
            if not df_nuevo.empty:
                guardar_mediciones(df_nuevo)
        except Exception as e:
            print(f"Aviso scraping: {e}", flush=True)

    df_res = consultar_datos_locales(codigo, dias=dias)
    if df_res.empty:
        raise HTTPException(status_code=404, detail="No se encontraron registros para esta estación.")

    df_res["nombre"] = nombre
    df_res["fecha_str"] = df_res["fecha_hora"].dt.strftime("%d-%m-%Y %H:%M")
    return df_res[["codigo_bna", "nombre", "variable", "fecha_str", "valor"]].to_dict(orient="records")


@app.get("/api/descargar_csv")
def descargar_csv(codigo: str = Query(...), dias: int = Query(90)):
    codigo = codigo.strip()
    nombre = obtener_nombre_estacion(codigo)
    df_res = consultar_datos_locales(codigo, dias=dias)

    if df_res.empty:
        try:
            df_nuevo = descargar_estaciones([codigo], dias=dias)
            if not df_nuevo.empty:
                guardar_mediciones(df_nuevo)
                df_res = consultar_datos_locales(codigo, dias=dias)
        except Exception:
            pass

    if df_res.empty:
        raise HTTPException(status_code=404, detail="Sin datos disponibles para exportar.")

    df_res["nombre"] = nombre
    df_salida = df_res[["codigo_bna", "nombre", "variable", "fecha_hora", "valor"]]
    csv_data = df_salida.to_csv(index=False, encoding="utf-8-sig")

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=DGA_{codigo}_{dias}dias.csv"}
    )


@app.get("/visor", response_class=HTMLResponse)
def servir_visor(codigo: str = "", dias: int = 90):
    codigo = codigo.strip()
    nombre = obtener_nombre_estacion(codigo)

    with open("visor.html", "r", encoding="utf-8") as f:
        html = f.read()

    return (
        html.replace("{{CODIGO}}", codigo)
            .replace("{{NOMBRE}}", nombre)
            .replace("{{DIAS}}", str(dias))
    )
