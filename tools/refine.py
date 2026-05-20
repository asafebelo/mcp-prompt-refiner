"""
Tool: refine_prompt

Recebe uma intenção crua em linguagem natural, carrega o contexto do projeto
(se existir) e devolve um prompt estruturado pronto para o Claude Code executar.

A LLM leve usada para refinar é definida em config.json e chamada via OpenRouter.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .context import _sanitize_project_name
from .openrouter import call_llm, get_default_language


# Pasta padrão onde os contextos de projeto são persistidos.
PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


# System prompt da LLM leve — instrui como o prompt refinado deve ser estruturado.
REFINER_SYSTEM_PROMPT = """Você é um especialista em prompt engineering para o Claude Code.
Sua única função é transformar intenções em linguagem natural em prompts
estruturados, detalhados e eficientes para o Claude Code executar.

Regras:
- Seja específico sobre o que deve ser feito e como
- Inclua contexto técnico relevante do projeto quando disponível
- Estruture em seções claras: Objetivo, Contexto, Requisitos, Restrições, Resultado esperado
- Nunca inclua explicações sobre o que você fez — apenas o prompt final
- Responda no idioma solicitado"""


def _load_project_context(project_name: str) -> str:
    """Lê o arquivo {project_name}.md do projeto, se existir.

    Devolve string vazia caso o arquivo não exista — isso é normal para projetos novos.
    """
    safe_name = _sanitize_project_name(project_name)
    project_file = PROJECTS_DIR / f"{safe_name}.md"
    if not project_file.exists():
        return ""
    try:
        return project_file.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"[mcp-prompt-refiner] erro ao ler contexto de {project_name}: {e}",
            file=sys.stderr,
        )
        return ""


def refine_prompt(
    intention: str,
    project_name: str,
    language: str | None = None,
) -> str:
    """Refina uma intenção em linguagem natural em um prompt estruturado.

    Args:
        intention: O que o usuário quer fazer, em linguagem natural.
        project_name: Nome do projeto atual — usado para carregar contexto persistido.
        language: Idioma do prompt de saída. Se None, usa o default de config.json.

    Returns:
        Prompt estruturado em string, gerado pela LLM leve via OpenRouter.
    """
    if not intention or not intention.strip():
        raise ValueError("intention não pode estar vazia")
    if not project_name or not project_name.strip():
        raise ValueError("project_name não pode estar vazio")

    lang = language or get_default_language()
    project_context = _load_project_context(project_name)

    # Monta o prompt do usuário com contexto opcional do projeto.
    if project_context:
        user_prompt = (
            f"Idioma de saída: {lang}\n\n"
            f"Contexto do projeto '{project_name}' (lido de {project_name}.md):\n"
            f"---\n{project_context}\n---\n\n"
            f"Intenção do usuário:\n{intention}\n\n"
            f"Gere o prompt estruturado para o Claude Code executar."
        )
    else:
        user_prompt = (
            f"Idioma de saída: {lang}\n\n"
            f"Projeto '{project_name}' ainda não tem contexto salvo (projeto novo).\n\n"
            f"Intenção do usuário:\n{intention}\n\n"
            f"Gere o prompt estruturado para o Claude Code executar."
        )

    refined = call_llm(REFINER_SYSTEM_PROMPT, user_prompt)
    return refined
