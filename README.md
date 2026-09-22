# Proyecto Integrador Big Data — Ingesta, Limpieza y Enriquecimiento de Datos

**Estudiante:** Jonatan Dair Ávila Agamez
**Proyecto:** Big Data — Proyecto Integrador
**Repositorio:** `JonathanAgamez25/Ingesta_Api`

---

# EA1 — Ingestión de Datos desde un API

## Descripción de la solución

Este proyecto corresponde a la primera etapa del proyecto integrador de Big Data. Extrae, en cada ejecución, un snapshot de mercado de las 100 criptomonedas con mayor capitalización desde el API público de CoinGecko.

Los datos obtenidos incluyen información como precio, volumen, capitalización de mercado y variación de precio en 24 horas.

Los datos se almacenan en una base de datos SQLite y se generan evidencias en formato Excel y TXT.

Todo el proceso está automatizado mediante GitHub Actions.

## Fuente de datos

**CoinGecko API**

Endpoint utilizado:

`/coins/markets`

La fuente es pública y no requiere API key para la consulta utilizada en el proyecto.

## Estructura del proyecto

```text
Ingesta_Api/
├── setup.py
├── README.md
├── .github/
│   └── workflows/
│       └── bigdata.yml
└── src/
    ├── ingestion.py
    ├── cleaning.py
    ├── enrichement.py
    ├── db/
    │   └── ingestion.db
    ├── xlsx/
    │   ├── ingestion.xlsx
    │   ├── cleaned_data.xlsx
    │   └── enriched_data.xlsx
    ├── enrichment_sources/
    │   ├── categorias.json
    │   ├── consenso.xlsx
    │   ├── sitios_web.csv
    │   ├── casos_uso.xml
    │   ├── tipo_red.html
    │   └── notas.txt
    └── static/
        └── auditoria/
            ├── ingestion.txt
            ├── cleaning_report.txt
            └── enriched_report.txt
```

## Diseño de la base de datos

La base de datos contiene principalmente dos tablas:

* **`ingestion_runs`**: registra cada ejecución del proceso de ingesta, incluyendo fecha, cantidad de registros y estado.
* **`coins_market`**: almacena los datos de las criptomonedas obtenidos en cada ejecución. Cada registro conserva el `run_id` correspondiente.

Esto permite mantener un histórico de las diferentes ejecuciones del proceso.

## Cómo clonar, instalar y ejecutar

```bash
git clone https://github.com/JonathanAgamez25/Ingesta_Api.git
cd Ingesta_Api

pip install .

python src/ingestion.py
```

La ejecución genera o actualiza:

```text
src/db/ingestion.db
src/xlsx/ingestion.xlsx
src/static/auditoria/ingestion.txt
```

## Automatización con GitHub Actions

El workflow se encuentra en:

```text
.github/workflows/bigdata.yml
```

El proceso se ejecuta:

* Cuando se realiza un `push` a `main`.
* Manualmente desde GitHub Actions.
* Automáticamente todos los días a las 09:00 UTC.

El workflow instala Python 3.11, instala las dependencias del proyecto y ejecuta las diferentes etapas del proyecto integrador.

---

# EA2 — Preprocesamiento y Limpieza de Datos

## Descripción de la solución

La segunda etapa corresponde al preprocesamiento y limpieza de los datos obtenidos durante la ingesta.

El script:

```text
src/cleaning.py
```

lee el histórico almacenado en:

```text
src/db/ingestion.db
```

y realiza diferentes procesos de análisis, limpieza y transformación.

## Procesos realizados

### 1. Extracción

Se obtiene el histórico completo de datos almacenados en la tabla `coins_market`.

### 2. Análisis de calidad

Se revisan:

* Cantidad de registros.
* Valores nulos.
* Registros duplicados.
* Tipos de datos.

### 3. Limpieza

Se realizan, entre otras, las siguientes operaciones:

* Eliminación de duplicados.
* Conversión de fechas a tipos `datetime`.
* Tratamiento de valores nulos en variables de variación de precio.

### 4. Transformaciones

Se agregan variables para mejorar el análisis:

* `is_price_change_outlier`: identifica valores atípicos mediante el método IQR.
* `market_cap_normalized`: normaliza la capitalización de mercado dentro de cada ejecución.

## Evidencias de EA2

El proceso genera:

```text
src/xlsx/cleaned_data.xlsx
src/static/auditoria/cleaning_report.txt
```

## Ejecución local de EA2

```bash
pip install .

python src/ingestion.py

python src/cleaning.py
```

---

# EA3 — Enriquecimiento de Datos en Plataforma de Big Data en la Nube

## Descripción de la solución

La tercera etapa corresponde al **enriquecimiento de los datos**.

El objetivo es integrar información adicional proveniente de diferentes formatos para complementar el dataset limpio obtenido en EA2.

El proceso principal se encuentra en:

```text
src/enrichement.py
```

El enriquecimiento utiliza seis fuentes externas en diferentes formatos:

| Formato | Archivo           | Información integrada                      |
| ------- | ----------------- | ------------------------------------------ |
| JSON    | `categorias.json` | Categoría y subcategoría                   |
| XLSX    | `consenso.xlsx`   | Mecanismo de consenso y año de lanzamiento |
| CSV     | `sitios_web.csv`  | Sitio web                                  |
| XML     | `casos_uso.xml`   | Caso de uso                                |
| HTML    | `tipo_red.html`   | Tipo de red                                |
| TXT     | `notas.txt`       | Notas adicionales                          |

## Fuentes de enriquecimiento

Las fuentes se encuentran dentro de:

```text
src/enrichment_sources/
```

Contiene:

```text
categorias.json
consenso.xlsx
sitios_web.csv
casos_uso.xml
tipo_red.html
notas.txt
```

## Proceso de integración

El script utiliza el identificador `id` como clave para relacionar los datos de las diferentes fuentes.

Se utiliza un **left join**, conservando todos los registros del dataset base aunque alguna fuente externa no tenga información correspondiente.

Las columnas agregadas incluyen:

```text
categoria
subcategoria
mecanismo_consenso
anio_lanzamiento
sitio_web
caso_de_uso
tipo_red
nota
```

De esta manera, el dataset original conserva sus registros y se complementa con información adicional proveniente de las seis fuentes.

## Ejecución de EA3

El proceso puede ejecutarse localmente mediante:

```bash
python src/enrichement.py
```

El script genera:

```text
src/xlsx/enriched_data.xlsx
src/static/auditoria/enriched_report.txt
```

## Reporte de auditoría

El archivo:

```text
src/static/auditoria/enriched_report.txt
```

documenta el proceso de enriquecimiento, incluyendo:

* Dataset utilizado como base.
* Fuentes utilizadas.
* Cantidad de registros de cada fuente.
* Cantidad de registros coincidentes.
* Porcentaje de coincidencias.
* Columnas agregadas.
* Método de integración utilizado.
* Cantidad final de registros.

Esto permite realizar la trazabilidad del proceso de enriquecimiento.

---

# Automatización completa con GitHub Actions

El workflow:

```text
.github/workflows/bigdata.yml
```

automatiza las tres etapas del proyecto.

## EA1 — Ingesta

Ejecuta:

```bash
python src/ingestion.py
```

y verifica:

```text
src/db/ingestion.db
src/xlsx/ingestion.xlsx
src/static/auditoria/ingestion.txt
```

## EA2 — Limpieza

Ejecuta:

```bash
python src/cleaning.py
```

y verifica:

```text
src/xlsx/cleaned_data.xlsx
src/static/auditoria/cleaning_report.txt
```

## EA3 — Enriquecimiento

Ejecuta:

```bash
python src/enrichement.py
```

y verifica:

```text
src/xlsx/enriched_data.xlsx
src/static/auditoria/enriched_report.txt
```

## Evidencias del workflow

GitHub Actions genera un artefacto descargable que contiene las evidencias de las diferentes etapas:

```text
src/db/ingestion.db
src/xlsx/ingestion.xlsx
src/xlsx/cleaned_data.xlsx
src/xlsx/enriched_data.xlsx
src/static/auditoria/ingestion.txt
src/static/auditoria/cleaning_report.txt
src/static/auditoria/enriched_report.txt
```

Además, las evidencias generadas por el proceso pueden quedar actualizadas directamente en el repositorio mediante `git-auto-commit-action`.

---

# Verificación del proceso

La ejecución correcta del workflow se puede comprobar desde la pestaña **Actions** del repositorio.

El workflow debe mostrar una ejecución con estado:

```text
Success
```

Durante la ejecución se verifican automáticamente los archivos generados por EA1, EA2 y EA3.

Esto permite comprobar que:

1. La ingesta se ejecutó correctamente.
2. Los datos fueron procesados y limpiados.
3. Las seis fuentes de información fueron integradas.
4. Se generó el dataset enriquecido.
5. Se generó el reporte de auditoría.
6. Los archivos requeridos quedaron disponibles como evidencias.

---

# Tecnologías utilizadas

* Python 3.11
* Pandas
* SQLite
* OpenPyX

