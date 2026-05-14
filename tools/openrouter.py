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

    Levanta FileNotFoundError com mensagem clara se o arquivo não existir,
    e ValueError se o JSON estiver malformado.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json não encontrado em {CONFIG_PATH}. "
            f"Copie config.example.json para config.json e preencha sua chave OpenRouter."
        )
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


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """Chama a LLM leve via OpenRouter e devolve o texto da resposta.

    Tenta primeiro o modelo principal definido em config.json.
    Se falhar, faz fallback para o modelo secundário.
    Erros são logados no stderr para não corromper o canal stdio do MCP.
    """
    config = _load_config()
    or_cfg = config.get("openrouter", {})

    api_key = or_cfg.get("api_key", "").strip()
    if not api_key or api_key == "COLOQUE_SUA_CHAVE_AQUI":
        raise ValueError(
            "Chave da OpenRouter não configurada. "
            "Edite config.json e coloque sua chave em openrouter.api_key."
        )

    primary_model = or_cfg.get("model", "google/gemini-2.0-flash-001")
    fallback_model = or_cfg.get("fallback_model", "anthropic/claude-haiku-4-5")
    max_tokens = int(or_cfg.get("max_tokens", 2000))
    temperature = float(or_cfg.get("temperature", 0.3))

    client = _build_client(api_key)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    # Tenta modelo primário, com fallback automático em caso de erro.
    for attempt_model in (primary_model, fallback_model):
        try:
            print(f"[mcp-prompt-refiner] chamando modelo {attempt_model}", file=sys.stderr)
            response = client.chat.completions.create(
                model=attempt_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("resposta da LLM veio vazia")
            return content.strip()
        except (OpenAIError, ValueError) as e:
            print(
                f"[mcp-prompt-refiner] falha em {attempt_model}: {e}",
                file=sys.stderr,
            )
            # Se for o último modelo da lista, propaga o erro.
            if attempt_model == fallback_model:
                raise

    # Inalcançável — o loop sempre retorna ou levanta.
    raise RuntimeError("fluxo inesperado em call_llm")


def get_default_language() -> str:
    """Devolve o idioma padrão configurado em config.json."""
    try:
        return _load_config().get("default_language", "pt-BR")
    except (FileNotFoundError, ValueError):
        return "pt-BR"
