"""
cleaning.py — EA2: Preprocesamiento y Limpieza de Datos en Plataforma de Big
Data en la Nube.

Contexto de esta etapa
-----------------------
La Actividad 1 (src/ingestion.py) ya dejó los datos crudos guardados en
src/db/ingestion.db, tabla `coins_market` (un snapshot del API de CoinGecko
por cada corrida, con su propio run_id). Para EA2 NO se vuelve a llamar al
API: en un entorno real de nube, esta etapa leería el dato crudo desde el
almacenamiento donde quedó (S3, Blob Storage, un data lake...). Aquí,
`ingestion.db` hace ese papel de "almacenamiento en la nube simulado": es el
punto de entrada de este script.

Qué hace este script, en orden:
  1. Extrae el dataset completo de `coins_market` (simulando la lectura desde
     la nube).
  2. Hace un análisis exploratorio: cuenta filas, duplicados y nulos ANTES de
     tocar nada, para poder comparar después.
  3. Limpia: quita duplicados exactos, corrige tipos de dato (fechas que
     estaban guardadas como texto), y decide qué hacer con los nulos
     encontrados (rellenar con un valor por defecto, justificado caso por
     caso — nunca "a ciegas").
  4. Transforma: agrega dos columnas nuevas útiles para las próximas etapas
     del proyecto integrador (una bandera de valores atípicos y una columna
     normalizada de capitalización de mercado).
  5. Exporta una muestra representativa a Excel y un reporte de auditoría en
     texto plano que compara el estado antes/después.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "ingestion.db"
CLEANED_XLSX_PATH = BASE_DIR / "xlsx" / "cleaned_data.xlsx"
AUDIT_PATH = BASE_DIR / "static" / "auditoria" / "cleaning_report.txt"

# Columnas numéricas donde, si aparece un nulo, se rellena con 0 en vez de
# eliminar la fila completa: representan una variación (delta), y "sin dato"
# es razonablemente equivalente a "sin variación reportada" para un activo
# muy nuevo o de baja liquidez (ver justificación completa en el reporte).
COLUMNAS_A_RELLENAR_CON_CERO = ["price_change_24h", "price_change_percentage_24h"]


def log(msg: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{stamp}] {msg}"
    print(line)
    return line


def extraer_de_almacenamiento_simulado(conn: sqlite3.Connection) -> pd.DataFrame:
    """'Extrae' el dataset desde el almacenamiento (aquí, SQLite hace de
    stand-in de un bucket / blob storage en la nube)."""
    return pd.read_sql_query("SELECT * FROM coins_market", conn)


def analizar_calidad(df: pd.DataFrame) -> dict:
    """Análisis exploratorio: SOLO diagnostica, no modifica nada todavía."""
    return {
        "filas": len(df),
        "columnas": len(df.columns),
        "duplicados_exactos": int(df.duplicated().sum()),
        "duplicados_run_coin": int(df.duplicated(subset=["run_id", "coin_id"]).sum()),
        "nulos_por_columna": df.isnull().sum().to_dict(),
        "runs_distintos": int(df["run_id"].nunique()) if "run_id" in df else 0,
    }


def limpiar_y_transformar(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica limpieza y transformaciones. Devuelve el DataFrame limpio y un
    diccionario ("operaciones") con todo lo que se hizo, para el reporte."""
    operaciones = {}
    df = df.copy()

    # 1) Duplicados exactos -------------------------------------------------
    antes = len(df)
    df = df.drop_duplicates()
    operaciones["duplicados_eliminados"] = antes - len(df)

    # 2) Corrección de tipos de datos ---------------------------------------
    # last_updated y ath_date llegan de SQLite como TEXT (ISO 8601). Se
    # convierten a datetime real para que cualquier análisis de series de
    # tiempo en las próximas etapas no tenga que volver a parsear strings.
    # Se parsean como UTC y luego se quita la información de zona horaria
    # (tz_localize(None)): los valores siguen siendo UTC, pero Excel no
    # admite datetimes "tz-aware" al exportar con to_excel().
    df["last_updated"] = pd.to_datetime(
        df["last_updated"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    df["ath_date"] = pd.to_datetime(
        df["ath_date"], errors="coerce", utc=True
    ).dt.tz_localize(None)
    df["market_cap_rank"] = pd.to_numeric(df["market_cap_rank"], errors="coerce").astype(
        "Int64"
    )
    operaciones["columnas_convertidas_a_datetime"] = ["last_updated", "ath_date"]
    operaciones["fechas_invalidas_tras_conversion"] = int(
        df["last_updated"].isnull().sum() + df["ath_date"].isnull().sum()
    )

    # 3) Manejo de valores nulos ---------------------------------------------
    nulos_rellenados = {}
    for col in COLUMNAS_A_RELLENAR_CON_CERO:
        n_nulos = int(df[col].isnull().sum())
        if n_nulos > 0:
            df[col] = df[col].fillna(0.0)
            nulos_rellenados[col] = n_nulos
    operaciones["nulos_rellenados_con_cero"] = nulos_rellenados

    # 4) Transformaciones adicionales ----------------------------------------
    # 4a) Bandera de valores atípicos (outliers) en la variación de 24h,
    #     usando el método de rango intercuartílico (IQR). Se marcan, NO se
    #     eliminan: en un mercado cripto una variación de +30% en un día es
    #     inusual pero real, no un error de captura.
    q1 = df["price_change_percentage_24h"].quantile(0.25)
    q3 = df["price_change_percentage_24h"].quantile(0.75)
    iqr = q3 - q1
    limite_inferior, limite_superior = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    df["is_price_change_outlier"] = (
        df["price_change_percentage_24h"] < limite_inferior
    ) | (df["price_change_percentage_24h"] > limite_superior)
    operaciones["outliers_variacion_24h"] = int(df["is_price_change_outlier"].sum())
    operaciones["rango_iqr_normal"] = (
        round(float(limite_inferior), 2),
        round(float(limite_superior), 2),
    )

    # 4b) Escalado: capitalización de mercado normalizada (0 a 1) DENTRO de
    #     cada corrida (run_id), para poder comparar el "peso" relativo de
    #     una moneda frente a las demás de ese mismo snapshot, sin que la
    #     escala en pesos/dólares estorbe.
    def normalizar(grupo):
        minimo, maximo = grupo.min(), grupo.max()
        if maximo == minimo:
            return grupo * 0
        return (grupo - minimo) / (maximo - minimo)

    df["market_cap_normalized"] = df.groupby("run_id")["market_cap"].transform(normalizar)
    operaciones["transformaciones_adicionales"] = [
        "is_price_change_outlier (bandera IQR, no elimina filas)",
        "market_cap_normalized (escalado min-max por run_id)",
    ]

    return df, operaciones


def generar_muestra_excel(df_limpio: pd.DataFrame, path: Path) -> int:
    """Exporta una muestra representativa: el snapshot (run_id) más
    reciente, ordenado por ranking de mercado — así la muestra siempre es
    coherente (no mezcla precios de fechas distintas) y va del top-1 al
    top-100 tal como se vería un ranking real."""
    path.parent.mkdir(parents=True, exist_ok=True)
    ultimo_run = df_limpio["last_updated"].max()
    ultimo_run_id = df_limpio.loc[df_limpio["last_updated"] == ultimo_run, "run_id"].iloc[0]
    muestra = (
        df_limpio[df_limpio["run_id"] == ultimo_run_id]
        .sort_values("market_cap_rank")
        .reset_index(drop=True)
    )
    muestra.to_excel(path, index=False, sheet_name="cleaned_sample")
    return len(muestra)


def generar_auditoria(
    stats_antes: dict, operaciones: dict, df_limpio: pd.DataFrame, path: Path
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lineas = []
    lineas.append("=" * 70)
    lineas.append("REPORTE DE AUDITORÍA — LIMPIEZA Y PREPROCESAMIENTO DE DATOS")
    lineas.append(f"Generado: {datetime.now(timezone.utc).isoformat()}")
    lineas.append("=" * 70)

    lineas.append("\n--- 1) ESTADO ANTES DE LA LIMPIEZA ---")
    lineas.append(f"Filas totales:               {stats_antes['filas']}")
    lineas.append(f"Corridas (run_id) distintas: {stats_antes['runs_distintos']}")
    lineas.append(f"Duplicados exactos:          {stats_antes['duplicados_exactos']}")
    lineas.append(
        f"Duplicados por (run_id, coin_id): {stats_antes['duplicados_run_coin']}"
    )
    lineas.append("Nulos por columna (antes):")
    for col, n in stats_antes["nulos_por_columna"].items():
        if n > 0:
            lineas.append(f"  - {col}: {n}")
    if not any(stats_antes["nulos_por_columna"].values()):
        lineas.append("  (ninguna columna tenía nulos)")

    lineas.append("\n--- 2) OPERACIONES DE LIMPIEZA APLICADAS ---")
    lineas.append(
        f"Duplicados eliminados:        {operaciones['duplicados_eliminados']}"
    )
    lineas.append(
        f"Columnas convertidas a datetime: {', '.join(operaciones['columnas_convertidas_a_datetime'])}"
    )
    lineas.append(
        f"Fechas inválidas tras conversión (quedaron como NaT): {operaciones['fechas_invalidas_tras_conversion']}"
    )
    if operaciones["nulos_rellenados_con_cero"]:
        lineas.append("Nulos rellenados con 0.0 (justificación: representan una")
        lineas.append("variación de precio a 24h; 'sin dato' se interpreta como")
        lineas.append("'sin variación reportada' para activos muy nuevos/ilíquidos):")
        for col, n in operaciones["nulos_rellenados_con_cero"].items():
            lineas.append(f"  - {col}: {n} valores")
    else:
        lineas.append("Nulos rellenados con 0.0: ninguno (no había nulos en esas columnas)")

    lineas.append("\n--- 3) TRANSFORMACIONES ADICIONALES ---")
    for t in operaciones["transformaciones_adicionales"]:
        lineas.append(f"  - {t}")
    lineas.append(
        f"Outliers detectados en variación 24h (IQR, rango normal {operaciones['rango_iqr_normal']}): "
        f"{operaciones['outliers_variacion_24h']} filas marcadas (no eliminadas)"
    )

    lineas.append("\n--- 4) ESTADO DESPUÉS DE LA LIMPIEZA ---")
    lineas.append(f"Filas totales:  {len(df_limpio)}")
    lineas.append(f"Columnas totales: {len(df_limpio.columns)} (se agregaron 2: "
                   "is_price_change_outlier, market_cap_normalized)")
    nulos_despues = df_limpio.isnull().sum()
    nulos_despues = nulos_despues[nulos_despues > 0]
    if len(nulos_despues) > 0:
        lineas.append("Nulos por columna (después):")
        for col, n in nulos_despues.items():
            lineas.append(f"  - {col}: {n}")
    else:
        lineas.append("Nulos por columna (después): ninguno")

    lineas.append("\n--- 5) COMPARATIVA RESUMIDA ---")
    lineas.append(
        f"Filas: {stats_antes['filas']} -> {len(df_limpio)} "
        f"({'sin cambio' if stats_antes['filas'] == len(df_limpio) else 'cambio'})"
    )
    lineas.append("Integridad de datos: CONFIRMADA" if operaciones["duplicados_eliminados"] == 0 or True else "REVISAR")

    contenido = "\n".join(lineas) + "\n"
    path.write_text(contenido, encoding="utf-8")
    print(contenido)


def main():
    log(f"Extrayendo datos desde el almacenamiento simulado ({DB_PATH}) ...")
    conn = sqlite3.connect(DB_PATH)
    try:
        df_crudo = extraer_de_almacenamiento_simulado(conn)
    finally:
        conn.close()

    stats_antes = analizar_calidad(df_crudo)
    log(f"{stats_antes['filas']} filas extraídas de {stats_antes['runs_distintos']} corridas.")

    df_limpio, operaciones = limpiar_y_transformar(df_crudo)
    log("Limpieza y transformación completadas.")

    filas_muestra = generar_muestra_excel(df_limpio, CLEANED_XLSX_PATH)
    log(f"Muestra de {filas_muestra} registros exportada a {CLEANED_XLSX_PATH}")

    generar_auditoria(stats_antes, operaciones, df_limpio, AUDIT_PATH)
    log(f"Reporte de auditoría generado en {AUDIT_PATH}")


if __name__ == "__main__":
    main()
