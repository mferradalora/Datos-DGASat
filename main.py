#!/usr/bin/env python
# -*- coding: utf-8 -*-
from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import HTMLResponse
import pandas as pd
from database import inicializar_db, guardar_mediciones, consultar_datos_locales, verificar_necesidad_scraping
from scraper import descargar_estaciones

inicializar_db()
app = FastAPI(title="Servicio de Series DGA")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


@app.get("/api/datos")
def obtener_series(codigo: str = Query(..., description="Código BNA"), dias: int = Query(90)):
    codigo = codigo.strip()

    # Si los datos no están o están desactualizados, consultar a la DGA
    if verificar_necesidad_scraping(codigo, dias):
        try:
            df_nuevo = descargar_estaciones([codigo], dias=dias)
            if not df_nuevo.empty:
                guardar_mediciones(df_nuevo)
        except Exception as e:
            print(f"Aviso: Fallo scraping en vivo ({e}). Se usarán datos en caché si existen.")

    df_res = consultar_datos_locales(codigo, dias=dias)
    if df_res.empty:
        raise HTTPException(status_code=404, detail="No se encontraron registros en el período solicitado.")

    df_res["fecha_str"] = df_res["fecha_hora"].dt.strftime("%d-%m-%Y %H:%M")
    return df_res[["codigo_bna", "variable", "fecha_str", "valor"]].to_dict(orient="records")


@app.get("/api/descargar_csv")
def descargar_csv(codigo: str = Query(...), dias: int = Query(90)):
    df_res = consultar_datos_locales(codigo.strip(), dias=dias)
    if df_res.empty:
        raise HTTPException(status_code=404, detail="Sin datos")

    csv_data = df_res.to_csv(index=False, encoding="utf-8-sig")
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=DGA_{codigo}_{dias}dias.csv"}
    )


@app.get("/visor", response_class=HTMLResponse)
def servir_visor(codigo: str = "", dias: int = 90):
    with open("visor.html", "r", encoding="utf-8") as f:
        html = f.read()
    return html.replace("{{CODIGO}}", codigo).replace("{{DIAS}}", str(dias))
