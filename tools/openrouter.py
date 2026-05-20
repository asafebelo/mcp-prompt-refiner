"""
Cliente OpenRouter — encapsula a chamada à LLM leve.

Usa o SDK oficial da OpenAI apontado para o endpoint do OpenRouter
(compatível com a API OpenAI). Carrega as configurações de config.json
e oferece um fallback automático caso o modelo primário falhe.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError


# Caminho absoluto para config.json — fica na raiz do projeto, um nível acima de tools/
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"

# Cache em memória: config e cliente são lidos/criados uma vez por processo.
_config_cache: dict[str, Any] | None = None
_client_cache: OpenAI | None = None
_client_api_key: str = ""


def _load_config() -> dict[str, Any]:
    """Lê config.json na primeira chamada e usa cache nas seguintes.

    Retorna {} se o arquivo não existir — modo Docker usa apenas env vars.
    Levanta ValueError se o JSON estiver malformado.
    """
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    if not CONFIG_PATH.exists():
        _config_cache = {}
        return _config_cache
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            _config_cache = json.load(f)
        return _config_cache
    except json.JSONDecodeError as e:
        raise ValueError(f"config.json está malformado: {e}") from e


def _get_client(api_key: str) -> OpenAI:
    """Retorna o cliente OpenAI, criando um singleton por processo."""
    global _client_cache, _client_api_key
    if _client_cache is None or _client_api_key != api_key:
        _client_cache = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            timeout=30.0,
            default_headers={
                "HTTP-Referer": "https://github.com/mcp-prompt-refiner",
                "X-Title": "MCP Prompt Refiner",
            },
        )
        _client_api_key = api_key
    return _client_cache


def _resolve_api_key(or_cfg: dict[str, Any]) -> str:
    """Resolve a chave da OpenRouter: env var tem prioridade sobre config.json."""
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

    client = _get_client(api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_error: Exception | None = None
    for attempt, model in enumerate(models):
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
            # Backoff apenas em erros de rate limit ou servidor (não em auth/bad request).
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (429, 500, 502, 503, 504) and attempt < len(models) - 1:
                delay = min(0.5 * (2 ** attempt), 8.0)
                time.sleep(delay)

    raise RuntimeError(f"todos os modelos falharam. Último erro: {last_error}")


def get_default_language() -> str:
    """Devolve o idioma padrão configurado em config.json."""
    try:
        return _load_config().get("default_language", "pt-BR")
    except (FileNotFoundError, ValueError):
        return "pt-BR"
