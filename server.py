"""
mcp-prompt-refiner — servidor MCP com suporte a stdio e HTTP.

Modos de execução:
  stdio (padrão) — comunicação via stdin/stdout, para Claude Code e Claude Desktop.
  http           — servidor HTTP com transporte Streamable HTTP, para Claude Web
                   Connector e ChatGPT Connector (requer URL pública via tunnel).

Controle do modo:
  --mode stdio|http        argumento de linha de comando (prioridade máxima)
  MCP_MODE=stdio|http      variável de ambiente (fallback)
  sem nada                 assume stdio

Ferramentas expostas:
  refine_prompt   — refina intenção crua em prompt estruturado
  save_context    — persiste estado do projeto em Markdown
  load_context    — recupera contexto de um projeto
  list_projects   — lista projetos com contexto salvo
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import os
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from tools import (
    load_context,
    list_projects,
    refine_prompt,
    save_context,
)

# ---------------------------------------------------------------------------
# Instância do servidor MCP
# ---------------------------------------------------------------------------

app: Server = Server("mcp-prompt-refiner")


# ---------------------------------------------------------------------------
# Declaração das ferramentas
# ---------------------------------------------------------------------------

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="refine_prompt",
            description=(
                "Transforma uma intenção em linguagem natural em um prompt "
                "estruturado e detalhado para o Claude Code executar. "
                "Use SEMPRE antes de iniciar uma tarefa nova."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "intention": {
                        "type": "string",
                        "description": "O que o usuário quer fazer, em linguagem natural.",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Nome do projeto atual (usado para carregar contexto).",
                    },
                    "language": {
                        "type": "string",
                        "description": "Idioma do prompt de saída. Padrão: pt-BR.",
                        "default": "pt-BR",
                    },
                },
                "required": ["intention", "project_name"],
            },
        ),
        Tool(
            name="save_context",
            description=(
                "Salva o estado atual do projeto após uma iteração: o que foi feito, "
                "decisões tomadas e próximos passos. Atualiza projects/{project_name}.md. "
                "Use ao finalizar cada iteração."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "what_was_done": {"type": "string"},
                    "decisions": {"type": "string", "default": ""},
                    "next_steps": {"type": "string", "default": ""},
                    "project_description": {"type": "string", "default": ""},
                },
                "required": ["project_name", "what_was_done"],
            },
        ),
        Tool(
            name="load_context",
            description=(
                "Carrega e retorna o contexto completo de um projeto. "
                "Use ao iniciar uma sessão em projeto existente."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                },
                "required": ["project_name"],
            },
        ),
        Tool(
            name="list_projects",
            description=(
                "Lista todos os projetos com contexto salvo, mostrando o nome "
                "e a data da última atualização."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
    ]


# ---------------------------------------------------------------------------
# Despachante de ferramentas
# ---------------------------------------------------------------------------

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    try:
        if name == "refine_prompt":
            result = refine_prompt(
                intention=arguments["intention"],
                project_name=arguments["project_name"],
                language=arguments.get("language"),
            )
        elif name == "save_context":
            result = save_context(
                project_name=arguments["project_name"],
                what_was_done=arguments["what_was_done"],
                decisions=arguments.get("decisions", ""),
                next_steps=arguments.get("next_steps", ""),
                project_description=arguments.get("project_description", ""),
            )
        elif name == "load_context":
            result = load_context(project_name=arguments["project_name"])
        elif name == "list_projects":
            result = list_projects()
        else:
            result = f"Ferramenta desconhecida: {name}"

        return [TextContent(type="text", text=result)]

    except ValueError as e:
        # Erros de validação de input são seguros para retornar ao cliente.
        print(f"[mcp-prompt-refiner] validação falhou em '{name}': {e}", file=sys.stderr)
        return [TextContent(type="text", text=f"Parâmetro inválido: {e}")]
    except Exception as e:
        # Erros internos (I/O, LLM, etc.) — loga o detalhe, retorna mensagem genérica.
        print(f"[mcp-prompt-refiner] erro interno na tool '{name}': {e}", file=sys.stderr)
        return [TextContent(type="text", text=f"Erro interno ao executar '{name}'. Verifique os logs do servidor.")]


# ---------------------------------------------------------------------------
# Modo stdio
# ---------------------------------------------------------------------------

async def run_stdio() -> None:
    print("[mcp-prompt-refiner] modo stdio iniciado", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


# ---------------------------------------------------------------------------
# Modo HTTP (Streamable HTTP — compatível com Claude Web e ChatGPT Connector)
# ---------------------------------------------------------------------------

def build_http_app():
    """Constrói e retorna o app ASGI com transporte Streamable HTTP no endpoint /mcp."""
    import contextlib
    from starlette.middleware.cors import CORSMiddleware
    from starlette.responses import JSONResponse, PlainTextResponse
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    auth_token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if auth_token:
        print("[mcp-prompt-refiner] autenticação Bearer habilitada", file=sys.stderr)

    session_manager = StreamableHTTPSessionManager(
        app=app,
        stateless=True,
        json_response=False,
    )

    @contextlib.asynccontextmanager
    async def lifespan(inner_app):
        async with session_manager.run():
            yield

    async def router(scope, receive, send):
        """Roteia /mcp para o session_manager; demais paths retornam 404."""
        if scope["type"] == "lifespan":
            async with session_manager.run():
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                message = await receive()
                if message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
            return

        path = scope.get("path", "")

        # Endpoint de health check — sem autenticação (usado pelo Docker)
        if path == "/health":
            await PlainTextResponse("ok")(scope, receive, send)
            return

        # Autenticação Bearer opcional para /mcp
        if path in ("/mcp", "/mcp/") and auth_token:
            headers = dict(scope.get("headers", []))
            authorization = headers.get(b"authorization", b"").decode()
            expected = f"Bearer {auth_token}"
            if not hmac.compare_digest(authorization, expected):
                await JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )(scope, receive, send)
                return

        if path in ("/mcp", "/mcp/"):
            await session_manager.handle_request(scope, receive, send)
        else:
            await PlainTextResponse("Not Found", status_code=404)(scope, receive, send)

    _MAX_BODY = 1 * 1024 * 1024  # 1 MB

    async def limit_body(scope, receive, send):
        if scope["type"] == "http":
            # Rejeita cedo via Content-Length antes de qualquer receive().
            headers = dict(scope.get("headers", []))
            cl = headers.get(b"content-length", b"")
            try:
                if cl and int(cl) > _MAX_BODY:
                    await JSONResponse({"error": "payload too large"}, status_code=413)(scope, receive, send)
                    return
            except ValueError:
                pass

            # Defesa em profundidade para streams sem Content-Length.
            body_size = 0

            async def checked_receive():
                nonlocal body_size
                message = await receive()
                if message.get("type") == "http.request":
                    body_size += len(message.get("body", b""))
                    if body_size > _MAX_BODY:
                        await JSONResponse({"error": "payload too large"}, status_code=413)(scope, receive, send)
                        return {"type": "http.disconnect"}
                return message

            await router(scope, checked_receive, send)
        else:
            await router(scope, receive, send)

    # CORS — quando sem auth, restringe a origens locais para evitar
    # que sites visitados pelo navegador do usuário acessem o servidor.
    if auth_token:
        cors_origins = ["*"]
    else:
        cors_origins = [
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:*",
            "http://127.0.0.1:*",
        ]
        print(
            "[mcp-prompt-refiner] AVISO: sem MCP_AUTH_TOKEN — CORS restrito a localhost",
            file=sys.stderr,
        )

    cors_app = CORSMiddleware(
        limit_body,
        allow_origins=cors_origins,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$" if not auth_token else None,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    return cors_app


def run_http(host: str, port: int) -> None:
    import uvicorn

    # Aborta se bind público sem token — evita expor o servidor por engano.
    auth_token = os.environ.get("MCP_AUTH_TOKEN", "").strip()
    if host in ("0.0.0.0", "::") and not auth_token:
        print(
            f"[mcp-prompt-refiner] ERRO: bind em {host} sem MCP_AUTH_TOKEN. "
            f"Defina MCP_AUTH_TOKEN ou use --host 127.0.0.1 para escutar só no localhost.",
            file=sys.stderr,
        )
        sys.exit(1)

    starlette_app = build_http_app()
    print(f"[mcp-prompt-refiner] modo HTTP em http://{host}:{port}/mcp", file=sys.stderr)
    uvicorn.run(starlette_app, host=host, port=port, log_level="info")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="mcp-prompt-refiner — servidor MCP para refinamento de prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modos:
  stdio   Claude Code, Claude Desktop, Cursor, Zed, Windsurf (padrão)
  http    Claude Web Connector, ChatGPT Connector (requer URL pública)

Exemplos:
  python server.py                        # stdio
  python server.py --mode http            # HTTP em 0.0.0.0:8000
  python server.py --mode http --port 9000
  MCP_MODE=http python server.py
        """,
    )
    parser.add_argument(
        "--mode",
        choices=["stdio", "http"],
        default=os.environ.get("MCP_MODE", "stdio"),
        help="Modo de transporte (padrão: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Host para modo HTTP (padrão: 127.0.0.1; use 0.0.0.0 só com MCP_AUTH_TOKEN)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8000")),
        help="Porta para modo HTTP (padrão: 8000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.mode == "http":
        run_http(args.host, args.port)
    else:
        asyncio.run(run_stdio())
