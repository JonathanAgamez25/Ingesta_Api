"""
ingestion.py — EA1 Proyecto integrador: Ingestión de Datos desde un API
-------------------------------------------------------------------------
Fuente: CoinGecko API (https://www.coingecko.com/api/documentation)
Endpoint público /coins/markets — no requiere API key.

Flujo (así se explica en la sustentación si lo preguntan):
  1. extraer_datos_api()     -> pega al API, devuelve la lista cruda (JSON)
  2. crear_esquema()         -> crea las tablas en SQLite si no existen
  3. insertar_datos()        -> guarda el snapshot de esta corrida
  4. generar_muestra_pandas()-> exporta una muestra a Excel con Pandas
  5. generar_auditoria()     -> compara API vs BD y deja un .txt
  6. main()                  -> orquesta todo, con un run_id único por corrida

Por qué hay DOS tablas (coins_market + ingestion_runs) y no una sola:
  - ingestion_runs: un renglón por CADA VEZ que se ejecuta el script
    (metadatos: cuándo, cuántos registros, si hubo error). Es la
    "bitácora" del proceso de ingesta.
  - coins_market: un renglón por moneda POR CADA CORRIDA (snapshot).
    Como el run_id queda guardado en cada fila, si este script corre
    todos los días (vía GitHub Actions con `schedule`), la tabla se
    convierte sola en una serie de tiempo de precios — que es
    exactamente lo que se necesita para las etapas futuras de
    enriquecimiento y modelado del proyecto integrador.
"""

import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Configuración y rutas
# ---------------------------------------------------------------------------
API_URL = "https://api.coingecko.com/api/v3/coins/markets"
API_PARAMS = {
    "vs_currency": "usd",
    "order": "market_cap_desc",
    "per_page": 100,
    "page": 1,
    "sparkline": "false",
    "price_change_percentage": "24h",
}

BASE_DIR = Path(__file__).resolve().parent.parent  # raíz del repo
DB_PATH = BASE_DIR / "src" / "db" / "ingestion.db"
XLSX_PATH = BASE_DIR / "src" / "xlsx" / "ingestion.xlsx"
AUDIT_PATH = BASE_DIR / "src" / "static" / "auditoria" / "ingestion.txt"

# Columnas del API que efectivamente guardamos (el API trae más campos de
# los que necesitamos — seleccionar explícitamente evita arrastrar basura
# a la base de datos). El campo "id" del API se renombra a "coin_id" en la
# tabla porque "id" es ambiguo (SQLite ya usa esa palabra para sus propios
# rowids); el mapeo va (campo_api, columna_en_bd).
CAMPOS_A_GUARDAR = [
    ("id", "coin_id"), ("symbol", "symbol"), ("name", "name"),
    ("current_price", "current_price"), ("market_cap", "market_cap"),
    ("market_cap_rank", "market_cap_rank"), ("total_volume", "total_volume"),
    ("high_24h", "high_24h"), ("low_24h", "low_24h"),
    ("price_change_24h", "price_change_24h"),
    ("price_change_percentage_24h", "price_change_percentage_24h"),
    ("circulating_supply", "circulating_supply"),
    ("total_supply", "total_supply"), ("ath", "ath"),
    ("ath_date", "ath_date"), ("last_updated", "last_updated"),
]


# ---------------------------------------------------------------------------
# 1. Extracción
# ---------------------------------------------------------------------------
def extraer_datos_api(timeout: int = 30) -> list[dict]:
    """Consulta el API de CoinGecko y devuelve la lista cruda de monedas."""
    respuesta = requests.get(API_URL, params=API_PARAMS, timeout=timeout)
    respuesta.raise_for_status()  # lanza excepción si el status no es 2xx
    datos = respuesta.json()
    if not isinstance(datos, list):
        raise ValueError(f"Respuesta inesperada del API: {datos}")
    return datos


# ---------------------------------------------------------------------------
# 2. Esquema
# ---------------------------------------------------------------------------
def crear_esquema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id              TEXT PRIMARY KEY,
            executed_at         TEXT NOT NULL,
            source_url          TEXT NOT NULL,
            records_extracted   INTEGER NOT NULL,
            records_inserted    INTEGER NOT NULL,
            status              TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS coins_market (
            run_id                          TEXT NOT NULL,
            coin_id                         TEXT NOT NULL,
            symbol                          TEXT,
            name                            TEXT,
            current_price                   REAL,
            market_cap                      REAL,
            market_cap_rank                 INTEGER,
            total_volume                    REAL,
            high_24h                        REAL,
            low_24h                         REAL,
            price_change_24h                REAL,
            price_change_percentage_24h     REAL,
            circulating_supply              REAL,
            total_supply                    REAL,
            ath                             REAL,
            ath_date                        TEXT,
            last_updated                    TEXT,
            PRIMARY KEY (run_id, coin_id),
            FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id)
        );
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 3. Inserción
# ---------------------------------------------------------------------------
def insertar_datos(conn: sqlite3.Connection, run_id: str, registros: list[dict]) -> int:
    """Inserta el snapshot de esta corrida. Devuelve cuántas filas insertó."""
    filas = []
    for r in registros:
        fila = tuple([run_id] + [r.get(campo_api) for campo_api, _ in CAMPOS_A_GUARDAR])
        filas.append(fila)

    placeholders = ", ".join(["?"] * (len(CAMPOS_A_GUARDAR) + 1))
    columnas = ", ".join(["run_id"] + [col_bd for _, col_bd in CAMPOS_A_GUARDAR])
    conn.executemany(
        f"INSERT INTO coins_market ({columnas}) VALUES ({placeholders})", filas
    )
    conn.commit()
    return len(filas)


def registrar_corrida(conn: sqlite3.Connection, run_id: str, extraidos: int,
                       insertados: int, status: str) -> None:
    conn.execute(
        """INSERT INTO ingestion_runs
           (run_id, executed_at, source_url, records_extracted, records_inserted, status)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (run_id, datetime.now(timezone.utc).isoformat(), API_URL, extraidos, insertados, status),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 4. Evidencia: muestra con Pandas
# ---------------------------------------------------------------------------
def generar_muestra_pandas(conn: sqlite3.Connection, run_id: str, n: int = 20) -> None:
    """Exporta a Excel una muestra representativa: el top-N por capitalización
    de mercado de la corrida actual, tal como pide el enunciado."""
    df = pd.read_sql_query(
        "SELECT * FROM coins_market WHERE run_id = ? ORDER BY market_cap_rank ASC LIMIT ?",
        conn, params=(run_id, n),
    )
    XLSX_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(XLSX_PATH, index=False, sheet_name="muestra_ingestion")


# ---------------------------------------------------------------------------
# 5. Evidencia: auditoría
# ---------------------------------------------------------------------------
def generar_auditoria(conn: sqlite3.Connection, run_id: str, registros_api: list[dict]) -> None:
    """Compara lo extraído del API contra lo efectivamente guardado en la
    base de datos, y deja un reporte de texto plano con el resultado."""
    df_bd = pd.read_sql_query(
        "SELECT * FROM coins_market WHERE run_id = ?", conn, params=(run_id,)
    )

    ids_api = {r["id"] for r in registros_api}
    ids_bd = set(df_bd["coin_id"])
    faltantes_en_bd = ids_api - ids_bd
    sobrantes_en_bd = ids_bd - ids_api

    # Verificación de integridad en un campo clave: current_price
    diferencias_precio = []
    precio_por_id_api = {r["id"]: r.get("current_price") for r in registros_api}
    for _, fila in df_bd.iterrows():
        precio_api = precio_por_id_api.get(fila["coin_id"])
        if precio_api is not None and fila["current_price"] != precio_api:
            diferencias_precio.append((fila["coin_id"], precio_api, fila["current_price"]))

    integridad_ok = (
        len(faltantes_en_bd) == 0
        and len(sobrantes_en_bd) == 0
        and len(diferencias_precio) == 0
    )

    lineas = [
        "AUDITORÍA DE INGESTA — EA1 Proyecto integrador",
        "=" * 60,
        f"run_id:              {run_id}",
        f"ejecutado:           {datetime.now(timezone.utc).isoformat()}",
        f"fuente:              {API_URL}",
        "",
        "CONTEO DE REGISTROS",
        "-" * 60,
        f"Registros extraídos del API:      {len(registros_api)}",
        f"Registros almacenados en SQLite:  {len(df_bd)}",
        "",
        "VERIFICACIÓN DE INTEGRIDAD",
        "-" * 60,
        f"IDs en API pero NO en BD:         {len(faltantes_en_bd)} {sorted(faltantes_en_bd) if faltantes_en_bd else ''}",
        f"IDs en BD pero NO en API:         {len(sobrantes_en_bd)} {sorted(sobrantes_en_bd) if sobrantes_en_bd else ''}",
        f"Diferencias en current_price:     {len(diferencias_precio)}",
    ]
    if diferencias_precio:
        lineas.append("  Detalle (coin_id, precio_api, precio_bd):")
        for d in diferencias_precio[:10]:
            lineas.append(f"    {d}")

    lineas += [
        "",
        "RESULTADO",
        "-" * 60,
        f"Integridad confirmada: {'SÍ' if integridad_ok else 'NO'}",
    ]

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text("\n".join(lineas), encoding="utf-8")


# ---------------------------------------------------------------------------
# 6. Orquestación
# ---------------------------------------------------------------------------
def main() -> int:
    run_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        crear_esquema(conn)

        print(f"[{run_id}] Extrayendo datos de {API_URL} ...")
        registros = extraer_datos_api()
        print(f"[{run_id}] {len(registros)} registros extraídos.")

        insertados = insertar_datos(conn, run_id, registros)
        registrar_corrida(conn, run_id, len(registros), insertados, status="OK")
        print(f"[{run_id}] {insertados} registros insertados en {DB_PATH}")

        generar_muestra_pandas(conn, run_id)
        print(f"[{run_id}] Muestra generada en {XLSX_PATH}")

        generar_auditoria(conn, run_id, registros)
        print(f"[{run_id}] Auditoría generada en {AUDIT_PATH}")

        return 0

    except Exception as exc:  # noqa: BLE001 — se registra y se re-lanza
        print(f"[{run_id}] ERROR: {exc}", file=sys.stderr)
        try:
            registrar_corrida(conn, run_id, 0, 0, status=f"ERROR: {exc}")
        except Exception:
            pass
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
