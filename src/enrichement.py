# ============================================================
# EA3 — Enriquecimiento de Datos en Plataforma de Big Data en la Nube
# Proyecto integrador: FarmaVida... (caso CoinGecko)
# Lee el dataset limpio generado en la EA2 (cleaned_data.xlsx) y lo
# enriquece cruzándolo con 6 fuentes adicionales en formatos
# distintos: JSON, XLSX, CSV, XML, HTML y TXT.
# ============================================================

import json
import re
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

# ------------------------------------------------------------
# Rutas
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent  # carpeta src/, donde vive este script
CLEANED_DATA_PATH = BASE_DIR / "xlsx" / "cleaned_data.xlsx"
FUENTES_DIR = BASE_DIR / "enrichment_sources"
ENRICHED_XLSX_PATH = BASE_DIR / "xlsx" / "enriched_data.xlsx"
REPORT_PATH = BASE_DIR / "static" / "auditoria" / "enriched_report.txt"

FUENTES_DIR.mkdir(parents=True, exist_ok=True)
REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "xlsx").mkdir(parents=True, exist_ok=True)


def log(mensaje, buffer):
    """Imprime en consola y acumula en el buffer del reporte de auditoría."""
    print(mensaje)
    buffer.append(mensaje)


def cargar_dataset_base(buffer):
    """Carga el dataset limpio generado en la EA2."""
    if not CLEANED_DATA_PATH.exists():
        raise FileNotFoundError(
            f"No se encontró {CLEANED_DATA_PATH}. Corre primero cleaning.py (EA2)."
        )
    df = pd.read_excel(CLEANED_DATA_PATH)
    # Normalizamos el nombre de la columna llave a 'id' en minúsculas, sin espacios
    df.columns = [c.strip() for c in df.columns]
    df = df.rename(columns={"coin_id": "id"}) if "coin_id" in df.columns else df
    if "id" not in df.columns:
        raise KeyError(
            f"El dataset base no tiene columna 'id'. Columnas disponibles: {list(df.columns)}"
        )
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"Dataset base cargado: {len(df):,} registros, {len(df.columns)} columnas.", buffer)
    return df


def leer_json(buffer):
    """Fuente 1 — JSON: categoría y subcategoría de cada criptomoneda."""
    path = FUENTES_DIR / "categorias.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    df = pd.DataFrame.from_dict(data, orient="index").reset_index()
    df = df.rename(columns={"index": "id"})
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"[JSON] categorias.json leído: {len(df):,} registros (categoria, subcategoria).", buffer)
    return df


def leer_xlsx(buffer):
    """Fuente 2 — XLSX: mecanismo de consenso y año de lanzamiento."""
    path = FUENTES_DIR / "consenso.xlsx"
    df = pd.read_excel(path)
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"[XLSX] consenso.xlsx leído: {len(df):,} registros (mecanismo_consenso, anio_lanzamiento).", buffer)
    return df


def leer_csv(buffer):
    """Fuente 3 — CSV: sitio web oficial."""
    path = FUENTES_DIR / "sitios_web.csv"
    df = pd.read_csv(path)
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"[CSV] sitios_web.csv leído: {len(df):,} registros (sitio_web).", buffer)
    return df


def leer_xml(buffer):
    """Fuente 4 — XML: caso de uso principal."""
    path = FUENTES_DIR / "casos_uso.xml"
    df = pd.read_xml(path, xpath=".//moneda", parser="etree")
    df = df.rename(columns={"id": "id", "caso_de_uso": "caso_de_uso"})
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"[XML] casos_uso.xml leído: {len(df):,} registros (caso_de_uso).", buffer)
    return df


def leer_html(buffer):
    """Fuente 5 — HTML: tipo de red (blockchain propia / token sobre otra red)."""
    path = FUENTES_DIR / "tipo_red.html"
    with open(path, "r", encoding="utf-8") as f:
        contenido = f.read()

    filas = re.findall(
        r"<tr><td>(.*?)</td><td>(.*?)</td></tr>",
        contenido,
        re.DOTALL,
    )
    df = pd.DataFrame(filas, columns=["id", "tipo_red"])
    df["id"] = df["id"].astype(str).str.strip().str.lower()
    log(f"[HTML] tipo_red.html leído: {len(df):,} registros (tipo_red).", buffer)
    return df


def leer_txt(buffer):
    """Fuente 6 — TXT: nota descriptiva libre, formato 'id: nota'."""
    path = FUENTES_DIR / "notas.txt"
    filas = []
    with open(path, "r", encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            m = re.match(r"^([a-z0-9\-]+):\s*(.+)$", linea)
            if m:
                filas.append({"id": m.group(1).strip().lower(), "nota": m.group(2).strip()})
    df = pd.DataFrame(filas)
    log(f"[TXT] notas.txt leído: {len(df):,} registros (nota).", buffer)
    return df


def cruzar(df_base, df_fuente, nombre_fuente, buffer):
    """Hace un left join del dataset base contra una fuente adicional por 'id',
    y registra en el reporte cuántos registros hicieron match."""
    antes_cols = set(df_base.columns)
    df_resultado = df_base.merge(df_fuente, on="id", how="left")
    nuevas_cols = [c for c in df_resultado.columns if c not in antes_cols]

    if nuevas_cols:
        coincidencias = df_resultado[nuevas_cols[0]].notna().sum()
    else:
        coincidencias = 0

    total = len(df_base)
    pct = (coincidencias / total * 100) if total else 0
    log(
        f"  → Cruce con {nombre_fuente}: {coincidencias:,}/{total:,} registros coincidentes "
        f"({pct:.1f}%). Columnas agregadas: {nuevas_cols}",
        buffer,
    )
    return df_resultado


def main():
    buffer = []
    log("=" * 60, buffer)
    log("EA3 — Enriquecimiento de datos (CoinGecko)", buffer)
    log(f"Ejecutado: {datetime.now(timezone.utc).isoformat()}", buffer)
    log("=" * 60, buffer)

    df = cargar_dataset_base(buffer)
    registros_base = len(df)

    log("\nLeyendo fuentes adicionales:", buffer)
    fuentes = {
        "categorias.json (JSON)": leer_json(buffer),
        "consenso.xlsx (XLSX)": leer_xlsx(buffer),
        "sitios_web.csv (CSV)": leer_csv(buffer),
        "casos_uso.xml (XML)": leer_xml(buffer),
        "tipo_red.html (HTML)": leer_html(buffer),
        "notas.txt (TXT)": leer_txt(buffer),
    }

    log("\nCruzando cada fuente contra el dataset base (join por 'id'):", buffer)
    for nombre, df_fuente in fuentes.items():
        df = cruzar(df, df_fuente, nombre, buffer)

    registros_enriquecidos = len(df)
    columnas_nuevas = len(df.columns) - (len(df.columns) - 6)  # las 6 columnas agregadas

    log("\n" + "=" * 60, buffer)
    log("RESUMEN DEL ENRIQUECIMIENTO", buffer)
    log("=" * 60, buffer)
    log(f"Registros en el dataset base:         {registros_base:,}", buffer)
    log(f"Registros en el dataset enriquecido:   {registros_enriquecidos:,}", buffer)
    log(f"Columnas nuevas incorporadas:           categoria, subcategoria, "
        f"mecanismo_consenso, anio_lanzamiento, sitio_web, caso_de_uso, tipo_red, nota", buffer)

    log("\nObservaciones por fuente:", buffer)
    log("  - JSON, XLSX, CSV, XML, HTML y TXT cubren la totalidad de las 50 criptomonedas "
        "más conocidas del mercado; el porcentaje de coincidencia real depende de cuáles "
        "de esas monedas aparecen en el snapshot vigente de samples.wanderbricks / CoinGecko.", buffer)
    log("  - Las filas del dataset base cuyo 'id' no aparece en ninguna fuente adicional "
        "quedan con valores nulos (NaN) en las columnas nuevas, sin perder el registro original "
        "(left join, no inner join) — se prefirió no descartar datos por falta de enriquecimiento.", buffer)

    # --- Exportar dataset enriquecido ---
    df.to_excel(ENRICHED_XLSX_PATH, index=False)
    log(f"\nDataset enriquecido guardado en: {ENRICHED_XLSX_PATH}", buffer)

    # --- Guardar reporte de auditoría ---
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(buffer) + "\n")
    print(f"Reporte de auditoría guardado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
