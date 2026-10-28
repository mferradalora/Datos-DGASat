#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
from datetime import datetime, timedelta
import pandas as pd

DB_PATH = "dgasat_cache.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def inicializar_db():
    """Crea las tablas y los índices si no existen."""
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mediciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo_bna TEXT NOT NULL,
                variable TEXT NOT NULL,
                fecha_hora DATETIME NOT NULL,
                valor REAL NOT NULL,
                fecha_ingreso DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(codigo_bna, variable, fecha_hora)
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_bna_fecha 
            ON mediciones(codigo_bna, fecha_hora);
        """)
        conn.commit()


def guardar_mediciones(df: pd.DataFrame):
    """Guarda registros en SQLite ignorando duplicados preexistentes."""
    if df is None or df.empty:
        return 0

    registros = []
    for _, r in df.iterrows():
        f_str = r["fecha_hora"].strftime("%Y-%m-%d %H:%M:%S") if hasattr(r["fecha_hora"], "strftime") else str(r["fecha_hora"])
        registros.append((
            str(r["codigo_bna"]).strip(),
            str(r["variable"]).strip(),
            f_str,
            float(r["valor"])
        ))

    with get_db() as conn:
        cursor = conn.executemany("""
            INSERT OR IGNORE INTO mediciones (codigo_bna, variable, fecha_hora, valor)
            VALUES (?, ?, ?, ?);
        """, registros)
        conn.commit()
        return cursor.rowcount


def consultar_datos_locales(codigo_bna: str, dias: int = 90):
    """Recupera series de tiempo almacenadas en la base de datos."""
    fecha_limite = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as conn:
        query = """
            SELECT codigo_bna, variable, fecha_hora, valor
            FROM mediciones
            WHERE codigo_bna = ? AND fecha_hora >= ?
            ORDER BY fecha_hora ASC;
        """
        df = pd.read_sql_query(query, conn, params=[codigo_bna, fecha_limite])
        if not df.empty:
            df["fecha_hora"] = pd.to_datetime(df["fecha_hora"])
        return df


def verificar_necesidad_scraping(codigo_bna: str, dias: int = 90):
    """Evalúa si los datos locales están ausentes o tienen más de 3 horas de desactualización."""
    with get_db() as conn:
        cur = conn.execute("""
            SELECT MAX(fecha_hora) as ult_fecha, COUNT(*) as total
            FROM mediciones
            WHERE codigo_bna = ?;
        """, [codigo_bna])
        row = cur.fetchone()

        if not row or row["total"] == 0 or row["ult_fecha"] is None:
            return True

        ult_fecha = datetime.strptime(row["ult_fecha"], "%Y-%m-%d %H:%M:%S")
        # Si la última medición tiene más de 3 horas, requiere actualización
        return (datetime.now() - ult_fecha) > timedelta(hours=3)
