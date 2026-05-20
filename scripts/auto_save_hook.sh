#!/usr/bin/env bash
# Stop hook do Claude Code — injeta save_context ao final de cada sessão.
#
# Fluxo:
#   1ª parada → injeta prompt pedindo save_context (exit 2)
#   2ª parada → CLAUDE_STOP_HOOK_ACTIVE=1 → sai silenciosamente (exit 0)
#
# Prevenção adicional de injeção desnecessária:
#   lê transcript_path do JSON de entrada e verifica se save_context
#   já foi chamado na sessão; se sim, sai sem injetar.

set -uo pipefail

# Segundo disparo (após injeção) — sai sem fazer nada
if [ "${CLAUDE_STOP_HOOK_ACTIVE:-0}" = "1" ]; then
    exit 0
fi

# Lê dados do hook via stdin (formato JSON)
HOOK_INPUT=$(cat 2>/dev/null || true)

# Extrai transcript_path do JSON de entrada
TRANSCRIPT=""
if [ -n "$HOOK_INPUT" ]; then
    TRANSCRIPT=$(printf '%s' "$HOOK_INPUT" | python3 -c \
        "import sys, json; d=json.load(sys.stdin); print(d.get('transcript_path',''))" \
        2>/dev/null || true)
fi

# Se save_context já foi chamado como ferramenta nesta sessão, não injeta.
# Busca por chamada real de ferramenta no JSON (evita falso positivo por
# menções textuais de "save_context" na conversa).
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    if python3 - "$TRANSCRIPT" 2>/dev/null <<'PYEOF'
import sys, json

with open(sys.argv[1], encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Procura blocos tool_use com name == "save_context"
        content = entry.get("message", {}).get("content", [])
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "save_context":
                    sys.exit(0)
sys.exit(1)
PYEOF
    then
        exit 0
    fi
fi

# Extrai nome do projeto do diretório atual
PROJECT=$(basename "$PWD")

# Injeta prompt — Claude lê como nova mensagem do usuário e chama save_context
printf 'Antes de finalizar, chame a ferramenta save_context do mcp-prompt-refiner para o projeto "%s". Registre: o que foi feito nesta sessão, decisões técnicas tomadas e próximos passos pendentes.' "$PROJECT"
exit 2
