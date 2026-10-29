import os
import urllib.parse
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
import pandas as pd
from database import consultar_datos_locales, guardar_mediciones, inicializar_db, verificar_necesidad_scraping
from scraper import descargar_estaciones

inicializar_db()
app = FastAPI(title="Servicio de Series DGA")

# 1. FUNCIÓN PARA OBTENER EL NOMBRE DESDE EL CATÁLOGO
CATALOGO_PATH = "data/catalogo_completo_dga.csv"


def obtener_nombre_estacion(codigo_bna: str) -> str:
    """Busca el nombre oficial de la estación en el catálogo CSV por código BNA."""
    if os.path.exists(CATALOGO_PATH):
        try:
            df_cat = pd.read_csv(CATALOGO_PATH, dtype={"codigo_bna": str})
            df_cat.columns = [str(c).strip().lower() for c in df_cat.columns]
            cod_limpio = codigo_bna.strip().upper()
            coincidencia = df_cat[df_cat["codigo_bna"].str.strip().str.upper() == cod_limpio]
            if not coincidencia.empty:
                return str(coincidencia.iloc[0]["nombre"]).strip()
        except Exception as e:
            print(f"Aviso al consultar catálogo: {e}", flush=True)
    return "ESTACION SIN NOMBRE"


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)


# 2. ENDPOINT /api/datos (INCLUYE COLUMNA 'nombre')
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
        raise HTTPException(status_code=404, detail="No se encontraron mediciones disponibles.")

    df_res["nombre"] = nombre
    df_res["fecha_str"] = df_res["fecha_hora"].dt.strftime("%d-%m-%Y %H:%M")
    return df_res[["codigo_bna", "nombre", "variable", "fecha_str", "valor"]].to_dict(orient="records")


# 3. ENDPOINT /api/descargar_csv (INCLUYE COLUMNA 'nombre')
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
    # Estructura: codigo_bna, nombre, variable, fecha_hora, valor
    df_salida = df_res[["codigo_bna", "nombre", "variable", "fecha_hora", "valor"]]
    csv_data = df_salida.to_csv(index=False, encoding="utf-8-sig")
    
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=DGA_{codigo}_{dias}dias.csv"}
    )


# 4. RENDERIZACIÓN DE VISOR CON {{NOMBRE}}
@app.get("/visor", response_class=HTMLResponse)
def servir_visor(codigo: str = "", dias: int = 90, nombre: str = ""):
    codigo = codigo.strip()
    if not nombre or nombre.strip() == "":
        nombre = obtener_nombre_estacion(codigo)

    with open("visor.html", "r", encoding="utf-8") as f:
        html = f.read()

    return (
        html.replace("{{CODIGO}}", codigo)
            .replace("{{NOMBRE}}", nombre)
            .replace("{{DIAS}}", str(dias))
    )
