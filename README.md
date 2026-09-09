# EA1 — Ingestión de Datos desde un API

**Estudiante:** Jonatan Dair Ávila Agamez
**Proyecto:** Big Data — Proyecto integrador (Etapa 1: Ingesta)
**Fuente de datos:** [CoinGecko API](https://www.coingecko.com/api/documentation) — endpoint público `/coins/markets`, sin API key.

## Descripción de la solución

Este proyecto es la primera etapa de un proyecto integrador de Big Data. Extrae, en
cada ejecución, un snapshot de mercado de las 100 criptomonedas con mayor
capitalización (precio, volumen, variación 24h, entre otros) desde el API público de
CoinGecko, lo almacena en una base de datos SQLite, y genera dos evidencias
complementarias: una muestra de los datos en Excel (Pandas) y un reporte de auditoría
en texto plano que compara lo extraído del API contra lo efectivamente guardado.

Todo el proceso está automatizado con GitHub Actions: corre en cada `push` a `main`,
manualmente desde la pestaña *Actions*, y **todos los días a las 9:00 UTC**. Esa
corrida programada es intencional: cada ejecución guarda su propio `run_id`, así que
con el tiempo la tabla `coins_market` se convierte en una serie histórica de precios —
justo lo que necesitan las siguientes etapas del proyecto integrador (preprocesamiento,
enriquecimiento y modelado).

## Estructura del proyecto

```
jonatan_avila/
├── setup.py                                 # dependencias del proyecto
├── README.md
├── .github/workflows/bigdata.yml            # automatización (GitHub Actions)
└── src/
    ├── ingestion.py                         # script principal de ingesta
    ├── db/
    │   └── ingestion.db                     # base de datos SQLite (generada)
    ├── xlsx/
    │   └── ingestion.xlsx                   # muestra de datos (generada)
    └── static/auditoria/
        └── ingestion.txt                    # reporte de auditoría (generado)
```

## Diseño de la base de datos

Dos tablas, no una sola, y por una razón concreta:

- **`ingestion_runs`** — un renglón por *cada vez* que se ejecuta el script:
  cuándo corrió, cuántos registros extrajo, cuántos insertó, y si terminó bien o con
  error. Es la bitácora del proceso.
- **`coins_market`** — un renglón por moneda **por cada corrida** (el `run_id` queda
  guardado en cada fila). Esto es lo que permite que, con el tiempo, esta tabla se
  convierta sola en una serie de tiempo de precios sin tener que rediseñar nada en
  etapas futuras.

## Cómo clonar, instalar y ejecutar

```bash
git clone https://github.com/<tu-usuario>/<tu-repo>.git
cd jonatan_avila

# Instala las dependencias declaradas en setup.py (requests, pandas, openpyxl)
pip install .

# Ejecuta la ingesta
python src/ingestion.py
```

Al terminar, deja tres archivos actualizados: `src/db/ingestion.db`,
`src/xlsx/ingestion.xlsx` y `src/static/auditoria/ingestion.txt`.

## Automatización con GitHub Actions

El workflow `.github/workflows/bigdata.yml`:

1. Clona el repo e instala Python 3.11 y las dependencias (`pip install .`).
2. Ejecuta `python src/ingestion.py`.
3. Verifica explícitamente que los 3 artefactos se generaron (el job falla si falta
   alguno).
4. Sube los 3 archivos como **artefacto descargable** del workflow run.
5. **Commitea los archivos actualizados de vuelta al repositorio** (con
   `git-auto-commit-action`), para que la evidencia quede visible directamente en el
   código sin tener que entrar a la pestaña Actions.

### Cómo verificar que funcionó

- Pestaña **Actions** del repo → el workflow más reciente debe tener el ✅ verde en
  todos los pasos, incluido "Verificar que los artefactos existen".
- El paso "Verificar..." imprime en el log el contenido completo de
  `ingestion.txt`, así que la auditoría se puede leer sin descargar nada.
- En la pestaña **Code**, los archivos `src/db/ingestion.db`,
  `src/xlsx/ingestion.xlsx` y `src/static/auditoria/ingestion.txt` deben tener fecha
  de modificación reciente (el commit automático del workflow).

## Nota sobre el uso de asistencia de IA

Se usó asistencia de IA (Claude) para la estructura inicial de este proyecto. El
código fue probado localmente con datos simulados antes de conectarlo al API real
para validar el flujo completo (creación de esquema, inserción, generación de muestra
y auditoría), y puede explicarse en detalle: cada función de `ingestion.py` tiene un
comentario explicando su propósito y por qué está diseñada así.

---

# EA2 — Preprocesamiento y Limpieza de Datos en Plataforma de Big Data en la Nube

## Descripción de la solución

Segunda etapa del proyecto integrador. Este script **no vuelve a llamar al API**:
lee el histórico completo ya guardado en `src/db/ingestion.db` (tabla
`coins_market`), que en este ejercicio hace de "almacenamiento en la nube
simulado" — en un entorno real sería un bucket S3, un Blob Storage de Azure o un
data lake. A partir de ahí, valida la calidad del dato, lo limpia, lo transforma,
y deja evidencia de todo el proceso.

Qué hace `src/cleaning.py`, en orden:

1. **Extracción** del dataset completo desde `ingestion.db` (1100+ filas, una por
   moneda por cada corrida histórica de la ingesta).
2. **Análisis exploratorio** antes de tocar nada: cuenta filas, duplicados y
   nulos por columna.
3. **Limpieza**:
   - Elimina duplicados exactos.
   - Corrige tipos de dato: `last_updated` y `ath_date` pasan de texto a
     `datetime` real.
   - Rellena con `0.0` los nulos de `price_change_24h` /
     `price_change_percentage_24h` (justificado: son columnas de variación,
     y "sin dato" se interpreta como "sin variación reportada" para activos
     muy nuevos).
4. **Transformaciones adicionales**:
   - `is_price_change_outlier`: bandera booleana de valores atípicos en la
     variación de 24h, calculada con el método de rango intercuartílico
     (IQR). Se marcan, no se eliminan — una variación cripto de +30% en un
     día es inusual pero real.
   - `market_cap_normalized`: escalado min-max de la capitalización de
     mercado, calculado dentro de cada corrida (`run_id`), para poder
     comparar el peso relativo de una moneda frente a las demás del mismo
     snapshot.
5. **Evidencias**: exporta una muestra representativa (el snapshot más
   reciente, 100 monedas ordenadas por ranking) a
   `src/xlsx/cleaned_data.xlsx`, y un reporte de auditoría completo
   (antes/después) a `src/static/auditoria/cleaning_report.txt`.

## Cómo ejecutar EA2 localmente

```bash
pip install .
python src/ingestion.py   # (opcional) trae un snapshot nuevo del API
python src/cleaning.py    # lee ingestion.db y genera los artefactos de EA2
```

Al terminar, quedan actualizados `src/xlsx/cleaned_data.xlsx` y
`src/static/auditoria/cleaning_report.txt`.

## Automatización (EA2)

El mismo workflow `.github/workflows/bigdata.yml` de EA1 se extendió con dos
pasos nuevos: después de la ingesta, corre `python src/cleaning.py`, verifica
que sus artefactos existan, y los sube tanto como artefacto descargable del
workflow como comiteados de vuelta al repositorio — igual que se hacía con la
ingesta.
