# data-eng-agent

Un agente de ingeniería de datos (OpenCode) que **opera** un pipeline real —
extracción incremental e idempotente, dbt sobre DuckDB en capas, tests de
regla de negocio, y CI/CD — en vez de que alguien lo corra a mano.

Gratis de punta a punta, sin tarjeta: DuckDB (archivo local, no hay
servidor que pagar), Gemini (LLM, free tier sin tarjeta), GitHub Actions
(minutos gratis en repos públicos), Open-Meteo (sin key) y Banxico (key
gratis sin tarjeta).

> **Nota sobre este README**: todo lo que describe aquí fue probado en una
> máquina real (Windows), no solo en el entorno donde se escribió el
> código. La sección **"Bitácora real de puesta en marcha"** al final
> documenta, en orden, cada cosa que se rompió y cómo se arregló —
> léela si quieres ver el proceso completo, no solo el resultado final.

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

**Validado en producción real (no solo en teoría):** se corrió el flujo
completo de aprobación de punta a punta — el agente propuso un
full-refresh vía `propose_full_refresh` (abrió un PR describiendo
operación/razón/blast-radius), un humano disparó manualmente el workflow
`full-refresh.yml`, GitHub pausó la ejecución en estado "Waiting" hasta
que el reviewer configurado aprobó desde la UI de Environments, y solo
entonces se ejecutó el comando. En ningún punto el agente tuvo la
capacidad de saltarse ese paso.

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
   destructive-ops → Required reviewers*, ver más abajo). Aunque alguien
   dispare el workflow manualmente con `confirm=yes`, el job queda en
   estado "Waiting" hasta que un reviewer humano lo apruebe desde la UI
   de GitHub — el mismo patrón que un 2FA: quien pide la acción no es
   quien la autoriza.

Todo lo demás (extracción, `dbt build`/`test` normal, perfilar, diagnosticar,
abrir PRs) es autónomo — el agente sí "opera" el pipeline sin pedir permiso
para eso, porque nada de eso puede perder datos.

**Un límite honesto encontrado en producción:** para que el agente no
tenga NUNCA que pedir permiso de `bash` (que en un workflow sin
supervisión humana se queda colgado esperando una aprobación que nunca
llega, en vez de fallar rápido), el permiso `bash` está en `"deny"`
directo, no en `"ask"`. `"ask"` en un entorno sin nadie para responder no
es más seguro — es exactamente igual de seguro (nunca ejecuta) pero se
queda atorado indefinidamente en vez de fallar al instante. `"deny"` logra
la misma garantía de seguridad de forma limpia. Esto no afecta la
frontera de aprobación humana de operaciones destructivas, que es un
sistema completamente separado (ver arriba).

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
                    Agente OpenCode (Gemini, gratis)
                    tools propias + MCP propio (server.py, expone al agente)
```

## Setup

```bash
git clone <tu-fork>
cd data-eng-agent
cp .env.example .env   # llena BANXICO_TOKEN y GEMINI_API_KEY

pip install -r requirements.txt
dbt deps --project-dir dbt_project
python -m extraction.extract --source open_meteo --mode incremental
python -m extraction.extract --source banxico --mode incremental
dbt build --project-dir dbt_project --profiles-dir dbt_project
```

Keys necesarias (ambas gratis, sin tarjeta):
- **Banxico**: token en https://www.banxico.org.mx/SieAPIRest/service/v1/token
- **Gemini**: key en https://aistudio.google.com/apikey (no Groq — ver bitácora, el free tier de Groq resultó insuficiente)

En GitHub, agrega como secrets (*Settings → Secrets and variables → Actions*):
`BANXICO_TOKEN`, `GEMINI_API_KEY`.

### Instalar OpenCode

```bash
npm install -g opencode-ai
opencode auth login   # elige Google, pega tu API key de Gemini
```

Verifica que `opencode.json` tenga el modelo correcto (`google/gemini-3.5-flash-lite`
al momento de escribir esto — los nombres de modelo de Gemini cambian con
frecuencia, confirma el vigente si algo falla con "model not found").

### Configurar el gate de aprobación (una sola vez, en GitHub)

*Settings → Environments → New environment* → nombra `destructive-ops` →
agrega al menos un *Required reviewer*. Sin este paso, `full-refresh.yml`
sigue existiendo pero no tiene ningún gate real — es la única parte de
este proyecto que no se puede resolver con código, GitHub lo exige así.

### Permitir que el agente abra PRs en GitHub Actions

*Settings → Actions → General → Workflow permissions* → marca **"Allow
GitHub Actions to create and approve pull requests"**. Sin esto,
`open_fix_pr` falla con `GitHub Actions is not permitted to create or
approve pull requests` — es una restricción de seguridad que GitHub
aplica por default a cualquier repo nuevo, no algo de nuestra
configuración.

## Cómo correr al agente

Local: `opencode run "tu instrucción"` en la raíz del repo, con `.env` cargado.
Interactivo: `opencode` a secas, abre una sesión donde puedes aprobar
permisos en vivo.

En GitHub: comenta `/opencode <instrucción>` en cualquier issue o PR —
dispara `.github/workflows/opencode.yml`.

## Verificar que el incremental no duplica (lo que vas a revisar)

```bash
python -m extraction.extract --source open_meteo --mode incremental   # primera corrida
python -m extraction.extract --source open_meteo --mode incremental   # segunda, inmediata
```

La segunda corrida debe imprimir `nothing new to extract` — el watermark
en `state/*.json` ya avanzó. Esa es una protección; la protección real
está en `extraction/db.py::upsert`, que borra por natural key antes de
insertar, así que **incluso si el watermark se pierde o se resetea**,
volver a cargar la misma ventana no duplica nada. Validado dos veces:
sembrando datos sintéticos y corriendo `dbt build` dos veces seguidas
(90 filas antes, 90 después), y en la máquina real con datos de la API
verdadera.

**Backfill validado con datos reales:** `python -m extraction.extract
--source open_meteo --mode backfill --start 2025-01-01 --end 2025-01-31`
trajo exactamente 62 filas (31 días × 2 ubicaciones) de hace más de un
año, sin tocar el watermark de la extracción incremental — confirmando
que ambos modos son independientes entre sí, como se diseñó.

**MCP `context7` validado en uso real:** se le pidió al agente que
consultara la documentación de `dbt_utils.accepted_range` — llamó
`context7_resolve-library-id` y `context7_query-docs` de verdad (no
simulado), trajo la documentación real, y la usó para confirmar
correctamente que la configuración del test en este proyecto es válida.

## `make chaos` — para que rompas tu propia versión

```bash
python -m scripts.chaos --mode business_rule    # default
python -m scripts.chaos --mode schema_drift      # modo alterno
```

(El `Makefile` incluye un target `chaos`, pero requiere tener `make`
instalado — en Windows no viene por default; usa el comando de Python
directo de arriba si no lo tienes.)

- `business_rule`: inyecta `temp_min_c > temp_max_c` en `raw.open_meteo_daily`
  para hoy. No lo atrapa nada hasta `dbt test`, donde falla
  `assert_temp_max_gte_temp_min` (test singular, regla física real, no
  `unique`/`not_null`). Validado en máquina real: `FAIL 1
  assert_temp_max_gte_temp_min`, exactamente como se documenta.
- `schema_drift`: renombra `raw.banxico_fx.value → valor`. Falla antes,
  en `dbt run`, porque `stg_banxico__fx` castea `value`, que ya no existe.

**Hallazgo real sobre la calidad del diagnóstico con el modelo gratis
(`gemini-3.5-flash-lite`):** al pedirle al agente que corriera `dbt build`
y explicara el error, rastreó correctamente el problema hasta su origen
(`raw.open_meteo_daily`, no solo hasta donde el test lo atrapó en el
mart), confirmando temp_max=5.0 < temp_min=25.0 como físicamente
imposible. Sin embargo, **no conectó espontáneamente** que esos valores
exactos coincidían con lo que `scripts/chaos.py` inyecta — aunque ya
había leído ese archivo durante su propia investigación. Solo hizo la
conexión cuando se le preguntó explícitamente "¿esto es un dato real o
una inyección de prueba?". Es una limitación real y medible del modelo
"lite" (más barato, más rápido, menos capaz de conectar evidencia sin que
se lo pidan explícitamente), no del diseño de las tools o las skills — con
un modelo más grande es razonable esperar que hiciera esa conexión sin
el empujón.

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

`opencode.json` configura al agente para **usar** un servidor MCP (el
`duckdb` de terceros que resultó incompatible, ver bitácora — el agente
funciona igual de bien sin él, usando `profile_table` en su lugar). Eso
es distinto de que el agente **mismo** sea invocable por otras
herramientas vía MCP — por si tu evaluador se refería a eso con
"desplegable en mcp", se cubre en `mcp_server/server.py`.

Es un servidor MCP real (SDK oficial `mcp`, transporte stdio), con una
sola tool, `run_data_engineer_agent(prompt)`, que por debajo corre
`opencode run` en modo headless. Validado dos veces, en dos máquinas
distintas: se levantó el servidor, se conectó un cliente MCP real por
stdio, y se hizo el handshake `initialize()` + `list_tools()` — la tool
aparece con su descripción, tal cual la vería Claude Desktop u otra
instancia de OpenCode.

```bash
pip install -r mcp_server/requirements.txt
python mcp_server/server.py   # queda corriendo, esperando conexiones por stdio
```

Para conectarlo desde otro cliente MCP (ejemplo, otra instalación de
OpenCode, en su `opencode.json`):

```json
{
  "mcp": {
    "data-eng-agent": {
      "type": "local",
      "command": ["python", "/ruta/absoluta/a/data-eng-agent/mcp_server/server.py"]
    }
  }
}
```

**Por qué stdio local y no un servidor hosteado 24/7:** este proyecto
tiene la restricción explícita de cero costo y cero tarjeta. Un servidor
MCP con transporte HTTP corriendo permanentemente necesita hosting (aunque
sea un free tier, la mayoría se duermen por inactividad o tienen límites
de horas). El transporte stdio no tiene ese problema porque no es un
servicio persistente — cualquiera que quiera usarlo (incluyendo quien
evalúe este repo) lo levanta en su propia máquina con el comando de
arriba, exactamente como ya se hace con OpenCode mismo (tampoco hay un
"OpenCode en la nube" al que conectarse).

**Importante:** envolver al agente en MCP no le da ninguna capacidad
nueva. Las fronteras de `opencode.json` y `.opencode/tools/` (en
particular, que `propose_full_refresh` no puede ejecutar nada) siguen
aplicando exactamente igual sin importar por qué transporte llegue el
prompt.

## Cómo correrlo (checklist completo)

1. Clonar el repo y copiar `.env.example` a `.env`, llenar `BANXICO_TOKEN` y `GEMINI_API_KEY`
2. `pip install -r requirements.txt && dbt deps --project-dir dbt_project`
3. Instalar OpenCode (`npm install -g opencode-ai`) y autenticar (`opencode auth login`)
4. Instalar `uv`/`uvx` si se quiere usar algún MCP que lo requiera (opcional, ver bitácora)
5. Correr extracción + dbt build una vez, local, para tener un warehouse de partida
6. En GitHub: agregar los secrets, crear el Environment `destructive-ops` con reviewer, habilitar que Actions cree PRs
7. Probar el agente local: `opencode run "corre dbt build y dime si algo esta mal"`
8. Probar `/opencode <instrucción>` comentando en cualquier issue del repo
9. Probar `make chaos` (o `python -m scripts.chaos`) y pedirle al agente que diagnostique
10. Probar el flujo de aprobación: pedirle al agente que proponga un full-refresh, luego dispararlo manualmente en Actions y aprobarlo como reviewer
11. Probar el servidor MCP: `pip install -r mcp_server/requirements.txt && python mcp_server/server.py`

## Qué dejé fuera del alcance, y por qué

- **Solo 2 fuentes**, no más. Prefiero dos que de verdad sean
  incrementales, idempotentes y con backfill que seis a medias.
- **Sin Airflow.** El cron de GitHub Actions (`scheduled-incremental.yml`)
  hace de orquestador. Añadir Airflow aquí sumaba infraestructura sin
  demostrar nada que el cron no demuestre ya para este alcance.
- **Sin warehouse en la nube.** DuckDB es un archivo; en CI se persiste
  entre corridas vía GitHub Actions Cache (ver bitácora — esto no
  funcionaba así originalmente, fue un bug real encontrado y arreglado).
- **Sin instalar la GitHub App de OpenCode.** Uso `GITHUB_TOKEN` del
  runner con los permisos necesarios en el workflow — cero configuración
  extra para quien clone el repo.
- **`diagnose_failure` solo lee artefactos locales** (`run_results.json`).
  No hay integración con un observability tool — documentado como
  próximo paso, no simulado.
- **Servidor MCP propio en vez del paquete de terceros original.** Se
  intentó usar `mcp-server-duckdb` (PyPI) para exponer DuckDB vía MCP,
  pero resultó incompatible con la versión actual del SDK oficial de MCP
  (ver bitácora). Se optó por no perseguir versiones antiguas de un
  paquete de terceros y en su lugar el agente usa `profile_table`
  directamente para lo mismo.

## Bitácora real de puesta en marcha: qué se rompió y cómo se arregló

Todo lo de esta sección pasó corriendo el proyecto de verdad, en una
máquina Windows real, no solo en el entorno donde se escribió el código
originalmente. Se documenta en orden porque cada hallazgo es honesto y
verificable — nada de esto es hipotético.

**Elección de LLM gratis — tres intentos:**
1. **Groq (`llama-3.3-70b-versatile`)**: límite de 12,000 tokens/minuto en
   la capa gratis. El primer mensaje del agente (carga `AGENTS.md`, dos
   skills, y las tools de los MCPs configurados) ya pesa 40,000+ tokens —
   ningún prompt pasa.
2. **Groq (`llama-3.1-8b-instant`)**: el límite de la cuenta usada resultó
   ser 6,000 TPM (más bajo que lo documentado como típico) — tampoco
   alcanza, y apagar MCPs/tools solo bajó el peso del mensaje ~5%, no lo
   suficiente.
3. **Gemini (`gemini-2.5-flash`)**: modelo descontinuado para cuentas
   nuevas ("no longer available to new users").
4. **Gemini (`gemini-3.6-flash`)**: recién lanzado (días antes de esta
   prueba), cuota gratis diaria de solo 20 requests/día — los modelos
   nuevos suelen arrancar con cuotas muy restringidas antes de que Google
   las amplíe semanas después.
5. **Gemini (`gemini-3.5-flash-lite`)**: el que finalmente funcionó, con
   cuota diaria suficiente para uso normal de desarrollo.

**Instalación y dependencias:**
- `duckdb==1.1.3` no tiene wheel precompilado para Python 3.14 en
  Windows — pip intentaba compilarlo desde código fuente y fallaba por
  falta de Visual C++ Build Tools. Se relajó a `duckdb>=1.2,<2.0`.
- `uvx` (necesario para MCPs vía `uvx <paquete>`) no viene instalado por
  default — se instaló con el instalador oficial de `astral.sh/uv`.
- `.env` nunca se cargaba automáticamente — se agregó `load_dotenv()` en
  `extraction/__init__.py` para que cualquier script que importe del
  paquete lo cargue solo.
- El target `chaos` del `Makefile` usaba `python scripts/chaos.py`, que
  falla con `ModuleNotFoundError` porque no se ejecuta como módulo — se
  corrigió a `python -m scripts.chaos`. Además, `make` no viene instalado
  en Windows por default; el README ahora documenta el comando de Python
  equivalente directo.

**Bug de arquitectura real: el warehouse se "olvidaba" entre corridas de CI.**
El archivo `.duckdb` está en `.gitignore` (nunca se sube), pero el
watermark de extracción (`state/*.json`) sí se commitea automáticamente.
En un runner de GitHub Actions fresco (warehouse vacío) donde el
watermark ya dice "al día", la extracción se salta por completo (nada
nuevo que traer) — pero como el warehouse es nuevo, las tablas nunca se
crean, y `dbt build` truena buscando algo que nunca existió. Se arregló
persistiendo el archivo `.duckdb` entre corridas vía GitHub Actions Cache
(`actions/cache/restore` + `actions/cache/save`, con una clave rotativa y
`restore-keys` como prefijo) en los tres workflows que lo necesitan
(`ci.yml`, `scheduled-incremental.yml`, `full-refresh.yml`).

**`profiles.yml` con ruta relativa dependiente del directorio de invocación.**
`path: ../data/warehouse.duckdb` solo resuelve bien si se corre `dbt`
desde dentro de `dbt_project/`. El CI lo corre desde la raíz del repo, así
que ese mismo `../` apuntaba fuera del repo entero. Se corrigió a `path:
data/warehouse.duckdb`, consistente con invocar siempre desde la raíz.

**`opencode.yml` (el workflow que responde a `/opencode` en comentarios) —
la corrida con más bugs reales, encontrados uno tras otro:**
1. Nunca instalaba `pip install -r requirements.txt` ni `dbt deps` antes
   de dejar correr al agente → `ModuleNotFoundError: No module named
   'duckdb'`.
2. La variable de entorno correcta para la librería de IA de Google no es
   `GEMINI_API_KEY` sino `GOOGLE_GENERATIVE_AI_API_KEY` — nombre distinto
   al que se asumió inicialmente.
3. El permiso granular de `bash` (`"git log*": "allow"`) no matcheó como
   se esperaba cuando el agente pidió varios comandos en un solo bloque —
   cayó en el catch-all `"ask"`. En un workflow sin supervisión humana,
   `"ask"` no se auto-rechaza (como sí pasa en `opencode run` local) —
   se queda colgado indefinidamente esperando una aprobación que nunca
   llega. Fix real: la skill de diagnóstico se reescribió para no
   depender nunca de `bash`, y el permiso se endureció a `"deny"` directo
   (falla al instante, no se cuelga) como garantía adicional independiente
   de que el modelo "obedezca" la instrucción.
4. El runner no tenía configurada identidad de git (`user.name`/`user.email`)
   — el Action de OpenCode necesita hacer commits internos de la sesión.
5. `persist-credentials: false` en el checkout (puesto originalmente por
   buena práctica de seguridad) impedía que el agente hiciera `git push`
   de su propia rama de trabajo — se cambió a `true` solo en este
   workflow.
6. GitHub bloquea por default que Actions abra Pull Requests
   (`GitHub Actions is not permitted to create or approve pull requests`)
   — requiere habilitar explícitamente esa opción en *Settings → Actions
   → General*.
7. El propio `full-refresh.yml` tenía el mismo bug del warehouse
   olvidado (nunca restauraba el cache) más un bug adicional: usaba
   `working-directory: dbt_project`, lo cual rompía la ruta relativa de
   `profiles.yml` de la misma forma que el bug original del día 1. Se
   corrigió agregando el paso de cache y ejecutando siempre desde la raíz
   del repo con `--project-dir`/`--profiles-dir` explícitos.

**MCP de terceros incompatible — nunca se logró correr, y eso queda
explícito aquí para que no parezca un descuido si alguien ve la
referencia a `uvx mcp-server-duckdb` en `opencode.json`.** Ese MCP está
en el archivo de configuración con `"enabled": false` a propósito, no
por olvido. Falla con `AttributeError: 'Server' object has no attribute
'list_resources'` en cualquier máquina donde se probó (dos máquinas
distintas, mismo error) — usa una versión del SDK de MCP anterior a la
que trae `pip install mcp` hoy (el propio SDK oficial renombró su clase
principal de `FastMCP` a `MCPServer` entre versiones, un cambio rápido
que dejó atrás a paquetes de terceros que no se han actualizado al mismo
ritmo). Es un bug 100% del paquete de terceros, no de esta configuración
ni del código de este repo — no hay nada que arreglar del lado nuestro,
solo la decisión de usarlo o no.

Una alternativa que **no se intentó** (documentado para que quede claro
que se consideró, no que se pasó por alto): forzar que `uvx` instale una
versión anterior del SDK junto con el paquete, algo como `uvx --with
"mcp<2.0" mcp-server-duckdb ...`. No se persiguió esa ruta porque, aun si
funcionara, sería parchar un síntoma sobre un paquete que su propio autor
ya no mantiene al ritmo del SDK — el mismo tipo de incompatibilidad
podría volver a aparecer con el siguiente cambio de versión. Se optó por
usar `profile_table` directamente en su lugar, que cubre la misma
necesidad (perfilar tablas) sin depender de un paquete externo roto.

**Conflictos de merge en `state/*.json`.** Con el cron diario y las
corridas manuales avanzando el watermark desde distintos lugares (tu
máquina local y GitHub Actions), es normal toparse con conflictos de
merge en esos dos archivos al hacer `git pull`. Se resuelven sin
pérdida de información real — ambas versiones solo representan "hasta
qué fecha ya se extrajo", así que quedarse con cualquiera de las dos es
seguro.

**Límite real de `delete+insert` al limpiar el chaos manualmente.**
Después de correr `make chaos`, se limpió la fila envenenada borrándola
directamente de `raw.open_meteo_daily` — pero `dbt build` siguió
fallando el mismo test, porque la fila mala seguía en el mart
`fct_daily_conditions`. Mecanismo: `delete+insert` borra en el destino
solo las llaves (`location`, `date`) que **sí aparecen** en el lote nuevo
que trae el `SELECT` de esa corrida. Al borrar la fila de `raw` por
completo, esa fecha dejó de aparecer en cualquier parte de la consulta —
así que el modelo nunca "vio" esa llave para saber que debía borrarla del
mart también. Es una limitación real de esta estrategia incremental:
corrige valores que cambian para una llave que sigue existiendo, pero no
limpia una llave que desaparece de la fuente por completo. El fix
manual fue borrar la fila también del mart directamente; el fix "correcto"
en un escenario real habría sido justo un `--full-refresh` — el mismo
camino que este proyecto protege detrás de aprobación humana.
