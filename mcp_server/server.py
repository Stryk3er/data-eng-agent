"""
Expone al agente de este repo como un servidor MCP -- para que cualquier
cliente MCP (Claude Desktop, otra instancia de OpenCode, un IDE) pueda
invocarlo como una tool. Esto es distinto de lo que ya hace
opencode.json (donde el agente CONSUME servidores MCP como duckdb y
context7); aquí el agente se convierte en el servidor.

Transporte: stdio. Es el más simple de desplegar -- no requiere hosting,
no abre superficie de red que asegurar, y es exactamente el tipo de
config que Claude Desktop / otra instalación de OpenCode esperan para un
servidor MCP local.

Expone una sola tool: run_data_engineer_agent, que ejecuta `opencode run`
en modo headless (no interactivo). Las fronteras del agente definidas en
opencode.json y .opencode/tools/ siguen aplicando sin cambios -- este
servidor es un wrapper de transporte, no una forma de saltarse permisos.
En particular, propose_full_refresh sigue sin poder ejecutar nada;
exponer al agente por MCP no cambia lo que el agente puede hacer.
"""
import subprocess
from pathlib import Path

from mcp.server import MCPServer

REPO_ROOT = Path(__file__).resolve().parent.parent
MODEL = "groq/llama-3.3-70b-versatile"

server = MCPServer(
    name="data-eng-agent",
    description=(
        "Agente de ingeniería de datos que opera un pipeline de clima+FX "
        "(extracción, dbt, perfilado, diagnóstico, PRs de fix). No puede "
        "ejecutar operaciones destructivas bajo ninguna circunstancia -- "
        "solo puede proponerlas vía un issue de GitHub."
    ),
)


@server.tool()
def run_data_engineer_agent(prompt: str) -> str:
    """
    Corre al agente data-engineer de OpenCode con un prompt y devuelve su
    respuesta final. Usa las tools/skills/permisos definidos en
    opencode.json de este repo -- no tiene capacidad de ejecutar
    full-refresh, DROP, ni ninguna otra operación destructiva sin
    importar cómo se le pida.
    """
    result = subprocess.run(
        ["opencode", "run", "--model", MODEL, prompt],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=600,
    )
    output = result.stdout.strip()
    if result.returncode != 0:
        output += f"\n\n[opencode exited with code {result.returncode}]\n{result.stderr.strip()}"
    return output or "(sin salida)"


if __name__ == "__main__":
    server.run(transport="stdio")
