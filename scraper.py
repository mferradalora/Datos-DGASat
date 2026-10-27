#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import time
from datetime import datetime, timedelta
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://snia.mop.gob.cl/dgasat/pages/dgasat_param/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}
DATE_REGEX = re.compile(r"\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}")
DATE_FMT = "%d/%m/%Y"
TIMEOUT_CONFIG = (15, 60)  # 15s para conectar, 60s para recibir respuesta


def nueva_sesion():
    """Genera una sesión HTTP con reintentos automáticos y soporte para el servidor DGA."""
    s = requests.Session()
    s.verify = False
    s.headers.update(HEADERS)

    # Reintentos con retroceso exponencial ante inestabilidad del servidor
    reintentos = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=[500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=reintentos)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    # Handshake inicial para adquirir la cookie JSESSIONID
    s.get(BASE_URL + "dgasat_param.jsp?param=1", timeout=TIMEOUT_CONFIG)
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
    r1 = sesion.post(BASE_URL + "dgasat_param_1.jsp", data=base_data, timeout=TIMEOUT_CONFIG)
    if r1.status_code != 200:
        return []

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

    data_tablas = list(base_data.items()) + [("parametros", v) for v, _, _ in sensores]
    r2 = sesion.post(BASE_URL + "dgasat_param_tablas.jsp", data=data_tablas, timeout=TIMEOUT_CONFIG)

    rx = sesion.get(
        BASE_URL + "dgasat_param_tablas_instantaneos.jsp?pag=0",
        timeout=TIMEOUT_CONFIG,
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
    """Descarga mediciones capturando fallas de red de manera segura."""
    hasta = datetime.now()
    desde = hasta - timedelta(days=dias)

    try:
        sesion = nueva_sesion()
    except requests.exceptions.Timeout:
        raise TimeoutError("El servidor de la DGA (snia.mop.gob.cl) tardó demasiado en responder (Timeout).")
    except requests.exceptions.RequestException as e:
        raise ConnectionError(f"Error al conectar con la DGA: {e}")

    todos = []
    for i in range(0, len(codigos), 3):
        lote = codigos[i:i + 3]
        try:
            regs = consultar_lote_dgasat(sesion, lote, desde, hasta)
            todos.extend(regs)
        except requests.exceptions.RequestException:
            time.sleep(2)
            try:
                sesion = nueva_sesion()
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
