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
