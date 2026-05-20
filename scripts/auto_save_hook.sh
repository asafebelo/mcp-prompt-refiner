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

# Lê em ordem reversa — para em save_context sem carregar o arquivo inteiro.
found = False
with open(sys.argv[1], "rb") as fh:
    fh.seek(0, 2)
    pos = fh.tell()
    buf = b""
    while pos > 0:
        chunk = min(pos, 8192)
        pos -= chunk
        fh.seek(pos)
        buf = fh.read(chunk) + buf
        lines = buf.split(b"\n")
        # Mantém a linha incompleta no início para a próxima iteração.
        buf = lines[0]
        for line in reversed(lines[1:]):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            content = entry.get("message", {}).get("content", [])
            if isinstance(content, list):
                for block in content:
                    if (isinstance(block, dict)
                            and block.get("type") == "tool_use"
                            and "save_context" in block.get("name", "")):
                        found = True
                        break
            if found:
                break
        if found:
            break

sys.exit(0 if found else 1)
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
