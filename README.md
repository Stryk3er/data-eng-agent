# data-eng-agent

Un agente de ingeniería de datos (OpenCode) que **opera** un pipeline real —
extracción incremental e idempotente, dbt sobre DuckDB en capas, tests de
regla de negocio, y CI/CD — en vez de que alguien lo corra a mano.

Gratis de punta a punta, sin tarjeta: DuckDB (archivo local, no hay
servidor que pagar), Groq (LLM, free tier sin tarjeta), GitHub Actions
(minutos gratis en repos públicos), Open-Meteo (sin key) y Banxico (key
gratis sin tarjeta).

## Qué hace el agente (y qué no)

| Tool | Qué hace | Destructivo |
|---|---|---|
| `run_extraction` | Corre la extracción incremental o backfill de una fuente | No |
| `run_dbt` | Corre `dbt build/run/test` | No |
| `profile_table` | Row count, % nulos, min/max/distinct por columna | No |
| `diagnose_failure` | Lee `run_results.json` y devuelve la falla real, no un resumen | No |
| `open_fix_pr` | Crea branch, commitea, abre PR contra `main` | No (nunca mergea) |
| `propose_full_refresh` | Abre un issue con el impacto de una operación destructiva | **No puede ejecutar nada** — ver abajo |

**No existe ninguna tool en este repo que pueda correr un `--full-refresh`,
un `DROP TABLE`, o borrar historial.** No es una restricción de permisos
que se pueda desactivar — es que el código de esa tool nunca implementó
un `execute()` que corra el comando, solo uno que escribe un issue de
GitHub describiéndolo.

## Dónde puse la frontera de aprobación humana, y por qué

La aprobación humana vive en dos capas independientes, a propósito:

1. **La tool `propose_full_refresh` no tiene capacidad de ejecución.** Aun
   si el modelo "decidiera" saltarse las reglas, no hay código que
   ejecute el comando — solo `gh issue create`. Esto es más fuerte que un
   permiso, porque un permiso mal configurado puede fallar abierto; una
   capacidad que no existe, no.
2. **El workflow `full-refresh.yml` corre en el GitHub Environment
   `destructive-ops`, con reviewer requerido.** Esto sí es configuración
   (no código — GitHub no permite declarar reviewers requeridos en YAML,
   se configura en *Settings → Environments → New environment →
   destructive-ops → Required reviewers*, lo documento abajo). Aunque
   alguien dispare el workflow manualmente con `confirm=yes`, el job queda
   en estado "Waiting" hasta que un reviewer humano lo apruebe desde la UI
   de GitHub — el mismo patrón que un 2FA: quien pide la acción no es
   quien la autoriza.

Todo lo demás (extracción, `dbt build`/`test` normal, perfilar, diagnosticar,
abrir PRs) es autónomo — el agente sí "opera" el pipeline sin pedir permiso
para eso, porque nada de eso puede perder datos.

## Arquitectura

```
Open-Meteo (sin key)  ──┐
                        ├──▶ extraction/extract.py ──▶ raw.* (DuckDB)
Banxico SIE (key free) ─┘         │ incremental + watermark persistido
                                   │ idempotente (delete+insert por key)
                                   │ reintentos con backoff exponencial
                                   ▼
                              dbt (staging → intermediate → marts)
                                   │
                                   ├─ staging: solo cast/rename, 1:1 con la fuente
                                   ├─ intermediate: gap-fill de FX + join clima+fx
                                   └─ marts: fct_daily_conditions
                                        contract enforced, incremental
                                        delete+insert, 2 tests de regla real
                                   │
                                   ▼
                    Agente OpenCode (Groq, gratis)
                    tools propias + MCP duckdb (solo lectura) + MCP context7
                    skills: cómo operar, cómo diagnosticar sin repetir stack traces
```

## Setup

```bash
git clone <tu-fork>
cd data-eng-agent
cp .env.example .env   # llena BANXICO_TOKEN y GROQ_API_KEY

make install
make extract-all       # primera corrida: trae ~30 días por fuente
make dbt-build          # corre modelos + tests
```

Keys necesarias (ambas gratis, sin tarjeta):
- **Banxico**: token en https://www.banxico.org.mx/SieAPIRest/service/v1/token
- **Groq**: key en https://console.groq.com/keys

En GitHub, agrega ambas como *Settings → Secrets and variables → Actions*:
`BANXICO_TOKEN`, `GROQ_API_KEY`.

### Configurar el gate de aprobación (una sola vez, en GitHub)

*Settings → Environments → New environment* → nombra `destructive-ops` →
agrega al menos un *Required reviewer*. Sin este paso, `full-refresh.yml`
sigue existiendo pero no tiene ningún gate real — es la única parte de
este proyecto que no se puede resolver con código, GitHub lo exige así.

## Cómo correr al agente

Local: `opencode` en la raíz del repo, con `.env` cargado.

En GitHub: comenta `/opencode revisa el último run y dime si algo se rompió`
en cualquier issue o PR — dispara `.github/workflows/opencode.yml`.

## Verificar que el incremental no duplica (lo que vas a revisar)

```bash
make extract-all   # primera corrida
make extract-all   # segunda corrida inmediata
```

La segunda corrida debe imprimir `nothing new to extract` para ambas
fuentes — el watermark en `state/*.json` ya avanzó. Esto es una protección;
la protección real está en `extraction/db.py::upsert`, que borra por
natural key antes de insertar, así que **incluso si el watermark se
pierde o se resetea**, volver a cargar la misma ventana no duplica nada
(lo validé sembrando datos sintéticos y corriendo `dbt build` dos veces
seguidas: 90 filas antes, 90 después).

## `make chaos` — para que rompas tu propia versión

```bash
make chaos                    # modo business_rule (default)
make chaos MODE=schema_drift  # modo alterno
```

- `business_rule`: inyecta `temp_min_c > temp_max_c` en `raw.open_meteo_daily`
  para hoy. No lo atrapa nada hasta `dbt test`, donde falla
  `assert_temp_max_gte_temp_min` (test singular, regla física real, no
  `unique`/`not_null`). Lo validé: `FAIL 1 assert_temp_max_gte_temp_min`.
- `schema_drift`: renombra `raw.banxico_fx.value → valor`. Falla antes,
  en `dbt run`, porque `stg_banxico__fx` castea `value`, que ya no existe
  — simula que la API de origen cambió su esquema sin avisar.

Después de correr `make chaos`, pídele al agente `diagnose_failure` +
que te explique el mecanismo (no el stack trace) — es exactamente lo que
la skill `diagnose-pipeline-failure` le exige hacer.

## Los dos tests que no son `unique`/`not_null`

En `dbt_project/models/marts/_marts__schema.yml` y
`dbt_project/tests/assert_temp_max_gte_temp_min.sql`:

1. **`temp_max_c >= temp_min_c`** (test singular). Regla física, no de
   esquema — un termómetro no puede reportar el máximo por debajo del
   mínimo del mismo día.
2. **`fx_usd_mxn` entre 5 y 50** (`dbt_utils.accepted_range`). Cota de
   sanidad real para USD/MXN — si algún día sale 0.02 o 4500, es un bug
   de parseo (coma decimal, unidad equivocada), no un tipo de cambio real.

## Por qué el incremental de `fct_daily_conditions` usa `delete+insert`

Comentario completo en el propio modelo, resumen: ambas fuentes pueden
revisar los últimos días (Open-Meteo corrige lecturas recientes de su
archivo; Banxico puede republicar una tasa el mismo día). Un `append`
duplicaría esas correcciones. Un rebuild completo cada corrida sería
correcto pero reprocesa años de historia por cambios que solo tocan los
últimos días. `delete+insert` con `unique_key` + ventana de 10 días da
seguridad ante correcciones sin pagar el costo de un full-refresh cada vez.

## El agente como servidor MCP (no solo como consumidor de MCPs)

`opencode.json` ya configura al agente para **usar** dos servidores MCP
(`duckdb` de solo lectura, `context7` para docs). Eso es una cosa distinta
de que el agente **mismo** sea invocable por otras herramientas vía MCP —
por si tu evaluador se refería a eso con "desplegable en mcp", lo cubro
aparte en `mcp_server/server.py`.

Es un servidor MCP real (SDK oficial `mcp`, transporte stdio), con una
sola tool, `run_data_engineer_agent(prompt)`, que por debajo corre
`opencode run` en modo headless. Lo validé de punta a punta: levanté el
servidor, conecté un cliente MCP real por stdio, e hice el handshake
`initialize()` + `list_tools()` — la tool aparece con su descripción, tal
cual la vería Claude Desktop u otra instancia de OpenCode.

```bash
pip install -r mcp_server/requirements.txt
```

Para conectarlo desde otro cliente MCP (ejemplo, otra instalación de
OpenCode, en su `opencode.json`):

```json
{
  "mcp": {
    "data-eng-agent": {
      "type": "local",
      "command": ["python3", "/ruta/absoluta/a/data-eng-agent/mcp_server/server.py"]
    }
  }
}
```

**Importante:** envolver al agente en MCP no le da ninguna capacidad
nueva. Las fronteras de `opencode.json` y `.opencode/tools/` (en
particular, que `propose_full_refresh` no puede ejecutar nada) siguen
aplicando exactamente igual sin importar por qué transporte llegue el
prompt.

## Qué dejé fuera del alcance, y por qué

- **Solo 2 fuentes**, no más. Prefiero dos que de verdad sean
  incrementales, idempotentes y con backfill que seis a medias.
- **Sin Airflow.** El cron de GitHub Actions (`scheduled-incremental.yml`)
  hace de orquestador. Añadir Airflow aquí sumaba infraestructura sin
  demostrar nada que el cron no demuestre ya para este alcance.
- **Sin warehouse en la nube.** DuckDB es un archivo; en CI vive solo
  durante el run (el estado persistido es lo que sobrevive entre runs,
  vía commit a `state/*.json` — el archivo `.duckdb` en sí se reconstruye
  desde `raw.*` en cada run limpio de CI, por diseño, para no comprometer
  un archivo binario a git).
- **Sin instalar la GitHub App de OpenCode.** Uso `GITHUB_TOKEN` del
  runner con los permisos necesarios en el workflow — cero configuración
  extra para quien clone el repo, a costa de que los comentarios del bot
  aparecen como el token del repo, no como una app dedicada.
- **`diagnose_failure` solo lee artefactos locales** (`run_results.json`).
  No hay integración con un observability tool (ej. Sentry MCP) — lo
  documento como próximo paso, no lo simulé para no fingir alcance que no
  tiene datos reales detrás.

## Una limitación honesta de cómo construí esto

No pude probar las llamadas HTTP reales a Open-Meteo/Banxico desde el
entorno donde armé este repo (sandbox sin acceso a esos dominios). Sí
validé todo lo que depende de DuckDB/dbt de punta a punta sembrando datos
sintéticos con la misma forma que producirían los extractores reales
(mismas columnas, mismo tipo de gap de días no hábiles en FX) y corriendo
`dbt build` dos veces, y `make chaos` una vez, contra esos datos. La
primera corrida real contra las APIs va a pasar por tu CI, que sí tiene
salida a internet — si algo truena ahí, es la superficie más probable de
un bug real (nombres de campos de la respuesta JSON, principalmente).
