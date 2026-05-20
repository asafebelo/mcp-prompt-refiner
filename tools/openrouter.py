"""
Cliente OpenRouter — encapsula a chamada à LLM leve.

Usa o SDK oficial da OpenAI apontado para o endpoint do OpenRouter
(compatível com a API OpenAI). Carrega as configurações de config.json
e oferece um fallback automático caso o modelo primário falhe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError


# Caminho absoluto para config.json — fica na raiz do projeto, um nível acima de tools/
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> dict[str, Any]:
    """Lê e devolve o conteúdo de config.json como dict.

    Retorna {} se o arquivo não existir — modo Docker usa apenas env vars.
    Levanta ValueError se o JSON estiver malformado.
    """
    if not CONFIG_PATH.exists():
        return {}
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json está malformado: {e}") from e


def _build_client(api_key: str) -> OpenAI:
    """Cria o cliente OpenAI configurado para o endpoint do OpenRouter."""
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/mcp-prompt-refiner",
            "X-Title": "MCP Prompt Refiner",
        },
    )


def _resolve_api_key(or_cfg: dict[str, Any]) -> str:
    """Resolve a chave da OpenRouter: env var tem prioridade sobre config.json."""
    import os

    env_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if env_key:
        return env_key

    file_key = or_cfg.get("api_key", "").strip()
    if file_key and file_key != "COLOQUE_SUA_CHAVE_AQUI":
        return file_key

    raise ValueError(
        "Chave da OpenRouter não configurada. "
        "Defina a variável de ambiente OPENROUTER_API_KEY (recomendado) "
        "ou edite config.json e coloque sua chave em openrouter.api_key."
    )


_DEFAULT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-120b:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
    "inclusionai/ring-2.6-1t:free",
    "qwen/qwen-2.5-7b-instruct:free",
    "openai/gpt-oss-20b:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "poolside/laguna-m.1:free",
    "google/gemini-2.0-flash-001",
    "anthropic/claude-haiku-4-5",
]


def _resolve_models(or_cfg: dict[str, Any]) -> list[str]:
    """Resolve a lista de modelos a tentar em ordem de preferência."""
    if "models" in or_cfg:
        models = [m for m in or_cfg["models"] if isinstance(m, str) and m.strip()]
        if models:
            return models
    return _DEFAULT_MODELS


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Chama a LLM via OpenRouter percorrendo a lista de modelos até obter resposta."""
    config = _load_config()
    or_cfg = config.get("openrouter", {})

    api_key = _resolve_api_key(or_cfg)
    models = _resolve_models(or_cfg)
    max_tokens = int(or_cfg.get("max_tokens", 2000))
    temperature = float(or_cfg.get("temperature", 0.3))

    client = _build_client(api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for model in models:
        try:
            print(f"[mcp-prompt-refiner] chamando modelo {model}", file=sys.stderr)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("resposta da LLM veio vazia")
            return content.strip()
        except (OpenAIError, ValueError) as e:
            print(f"[mcp-prompt-refiner] falha em {model}: {e}", file=sys.stderr)
            last_error = e

    raise RuntimeError(f"todos os modelos falharam. Último erro: {last_error}")


def get_default_language() -> str:
    """Devolve o idioma padrão configurado em config.json."""
    try:
        return _load_config().get("default_language", "pt-BR")
    except (FileNotFoundError, ValueError):
        return "pt-BR"
