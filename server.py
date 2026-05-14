"""
mcp-prompt-refiner — servidor MCP via stdio.

Registra quatro ferramentas:
  - refine_prompt    : refina uma intenção crua em prompt estruturado
  - save_context     : persiste estado do projeto em Markdown
  - load_context     : recupera o contexto Markdown de um projeto
  - list_projects    : lista projetos com contexto salvo

Comunicação via stdio — logs sempre no stderr para não corromper o canal.
"""

from __future__ import annotations

import asyncio
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


# Instância do servidor MCP. O nome é o identificador que aparece nos logs/cliente.
app: Server = Server("mcp-prompt-refiner")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Declara as ferramentas disponíveis e seus schemas de entrada."""
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
                    "project_name": {
                        "type": "string",
                        "description": "Nome do projeto.",
                    },
                    "what_was_done": {
                        "type": "string",
                        "description": "O que foi implementado ou feito nesta iteração.",
                    },
                    "decisions": {
                        "type": "string",
                        "description": "Decisões técnicas tomadas (opcional).",
                        "default": "",
                    },
                    "next_steps": {
                        "type": "string",
                        "description": "O que ainda falta fazer (opcional).",
                        "default": "",
                    },
                    "project_description": {
                        "type": "string",
                        "description": "Descrição geral do projeto (usado apenas na primeira vez).",
                        "default": "",
                    },
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
                    "project_name": {
                        "type": "string",
                        "description": "Nome do projeto.",
                    },
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
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Despacha a chamada para a função correspondente da tool.

    Erros são capturados e devolvidos como TextContent — o cliente MCP exibe
    a mensagem ao Claude para que ele saiba o que deu errado.
    """
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

    except Exception as e:
        # Loga no stderr e devolve mensagem amigável ao cliente.
        print(
            f"[mcp-prompt-refiner] erro na tool '{name}': {e}",
            file=sys.stderr,
        )
        return [
            TextContent(
                type="text",
                text=f"Erro ao executar '{name}': {e}",
            )
        ]


async def main() -> None:
    """Inicializa o transporte stdio e mantém o servidor em loop."""
    print("[mcp-prompt-refiner] servidor iniciado via stdio", file=sys.stderr)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
