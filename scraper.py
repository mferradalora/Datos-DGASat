#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://snia.mop.gob.cl/dgasat/pages/dgasat_param/"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
DATE_REGEX = re.compile(r"\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}")
DATE_FMT = "%d/%m/%Y"


def nueva_sesion():
    s = requests.Session()
    s.verify = False
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,*/*",
        "Accept-Language": "es-CL,es;q=0.9"
    })
    s.get(BASE_URL + "dgasat_param.jsp?param=1", timeout=30)
    return s


def _payload_form(codigos, desde, hasta):
    c = list(codigos) + ["-1"] * (3 - len(codigos))
    return {
        "estacion1": c[0], "estacion2": c[1], "estacion3": c[2],
        "accion": "refresca", "param": "1", "tipo": "ANO",
        "fechaFinGrafico": hasta.strftime(DATE_FMT), "hora_fin": "0",
        "tiporep": "I", "period": "rango",
        "fechaInicioTabla": desde.strftime(DATE_FMT),
        "fechaFinTabla": hasta.strftime(DATE_FMT),
        "UserID": "nobody", "EsDL1": "0", "EsDL2": "0", "EsDL3": "0"
    }


def consultar_lote_dgasat(sesion, codigos, desde, hasta):
    base_data = _payload_form(codigos, desde, hasta)
    r1 = sesion.post(BASE_URL + "dgasat_param_1.jsp", data=base_data, timeout=40)
    if r1.status_code != 200:
        return []

    # Extraer sensores disponibles para las estaciones consultadas
    disponibles = re.findall(r'name="parametros"\s+[^>]*value="([^"]+)"', r1.text)
    sensores = []

    for valor in disponibles:
        m = re.match(r"([\dKkx\-]+)_(\d+)_(.+)$", valor)
        if not m:
            continue
        codigo, _, nombre_var = m.group(1), m.group(2), m.group(3).strip()

        if codigo in codigos:
            sensores.append((valor, codigo, nombre_var))

    if not sensores:
        return []

    # Solicitar tabla de datos
    data_tablas = list(base_data.items()) + [("parametros", v) for v, _, _ in sensores]
    r2 = sesion.post(BASE_URL + "dgasat_param_tablas.jsp", data=data_tablas, timeout=120)

    # Descargar HTML con mediciones
    rx = sesion.get(
        BASE_URL + "dgasat_param_tablas_instantaneos.jsp?pag=0",
        timeout=120,
        headers={"Referer": r2.url}
    )

    if rx.status_code != 200 or "<table" not in rx.text.lower():
        return []

    mediciones = []
    filas = re.findall(r"<tr[^>]*>(.*?)</tr>", rx.text, re.S | re.I)

    for tr in filas:
        celdas = [
            re.sub(r"<[^>]+>", "", c).replace("&nbsp;", " ").strip()
            for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)
        ]
        for idx, celda in enumerate(celdas):
            if DATE_REGEX.match(celda):
                fecha_str = re.sub(r"\s+", " ", celda)
                for k, (_, cod_bna, var_nombre) in enumerate(sensores):
                    val_str = celdas[idx + 1 + k] if idx + 1 + k < len(celdas) else ""
                    if val_str:
                        try:
                            valor_num = float(val_str.replace(",", "."))
                            dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
                            mediciones.append({
                                "codigo_bna": cod_bna,
                                "variable": var_nombre,
                                "fecha_hora": dt,
                                "valor": valor_num
                            })
                        except ValueError:
                            continue
                break
    return mediciones


def descargar_estaciones(codigos, dias=7):
    hasta = datetime.now()
    desde = hasta - timedelta(days=dias)
    sesion = nueva_sesion()
    todos = []

    # Máximo 3 estaciones por request (límite arquitectónico del portal DGA)
    for i in range(0, len(codigos), 3):
        lote = codigos[i:i + 3]
        try:
            regs = consultar_lote_dgasat(sesion, lote, desde, hasta)
            todos.extend(regs)
        except requests.RequestException:
            time.sleep(2)
            sesion = nueva_sesion()
            try:
                regs = consultar_lote_dgasat(sesion, lote, desde, hasta)
                todos.extend(regs)
            except Exception:
                pass
        time.sleep(0.5)

    if not todos:
        return pd.DataFrame()

    df = pd.DataFrame(todos)
    df = df.sort_values(by="fecha_hora").reset_index(drop=True)
    return df
