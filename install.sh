#!/usr/bin/env bash
# install.sh — instala e configura o mcp-prompt-refiner
#
# 1. Cria e ativa um virtualenv em .venv/
# 2. Instala dependências de requirements.txt
# 3. Garante a existência de config.json (copia de config.example.json se faltar)
# 4. Menu interativo para escolha do modo de deploy
# 5. Configura o ambiente conforme a opção escolhida

set -euo pipefail

# Diretório absoluto deste script (raiz do projeto).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="$SCRIPT_DIR/.venv"
SERVER_PATH="$SCRIPT_DIR/server.py"

echo "==> mcp-prompt-refiner :: instalação"
echo "    diretório: $SCRIPT_DIR"

# --- 1. Verifica versão do Python ---
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "ERRO: '$PYTHON_BIN' não encontrado. Instale Python 3.11+ ou ajuste a variável PYTHON_BIN." >&2
  exit 1
fi

PY_VERSION="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
echo "    Python detectado: $PY_VERSION"

# --- 2. Cria virtualenv ---
if [ ! -d "$VENV_DIR" ]; then
  echo "==> criando virtualenv em .venv/"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
else
  echo "==> virtualenv já existe em .venv/"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

PYTHON_IN_VENV="$VENV_DIR/bin/python"

# --- 3. Instala dependências ---
echo "==> instalando dependências"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- 4. Garante config.json ---
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
  if [ -f "$SCRIPT_DIR/config.example.json" ]; then
    cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
    echo "==> config.json criado a partir de config.example.json"
    echo "    IMPORTANTE: edite config.json e insira sua chave da OpenRouter em openrouter.api_key"
    echo "                ou defina a variável de ambiente OPENROUTER_API_KEY"
  else
    echo "AVISO: nem config.json nem config.example.json existem." >&2
  fi
else
  echo "==> config.json já existe — mantido"
fi

# ---------------------------------------------------------------------------
# Menu interativo — escolha do modo de deploy
# ---------------------------------------------------------------------------

echo ""
echo "╔════════════════════════════════════════════════════════╗"
echo "║         mcp-prompt-refiner :: modo de deploy           ║"
echo "╠════════════════════════════════════════════════════════╣"
echo "║  1) stdio — Claude Code (recomendado para dev local)   ║"
echo "║  2) stdio — Claude Desktop (WSL / Linux / macOS)       ║"
echo "║  3) HTTP local (Claude Web Connector / ChatGPT)        ║"
echo "║  4) HTTP + tunnel público (Cloudflare / ngrok)         ║"
echo "╚════════════════════════════════════════════════════════╝"
echo ""

DEPLOY_MODE=""
while true; do
  printf "Escolha o modo [1-4]: "
  read -r DEPLOY_MODE
  case "$DEPLOY_MODE" in
    1|2|3|4) break ;;
    *) echo "  Entrada inválida. Digite 1, 2, 3 ou 4." ;;
  esac
done

# ---------------------------------------------------------------------------
# Opção 1 — stdio para Claude Code
# ---------------------------------------------------------------------------

_deploy_claude_code() {
  echo ""
  echo "==> Registrando no Claude Code (escopo: user)"

  if ! command -v claude >/dev/null 2>&1; then
    echo "ERRO: 'claude' não encontrado no PATH." >&2
    echo "      Instale o Claude Code em https://claude.ai/code e rode install.sh novamente." >&2
    exit 1
  fi

  # Remove registro anterior, ignora falha.
  claude mcp remove mcp-prompt-refiner >/dev/null 2>&1 || true

  claude mcp add --scope user mcp-prompt-refiner \
    "$PYTHON_IN_VENV" "$SERVER_PATH"

  echo ""
  echo "✓ MCP registrado com sucesso."
  echo ""
  echo "PRÓXIMOS PASSOS:"
  echo "  1. Edite config.json e insira sua chave da OpenRouter."
  echo "  2. Reinicie o Claude Code para carregar o servidor."
  echo "  3. Nas próximas sessões, use 'refine_prompt', 'save_context',"
  echo "     'load_context' e 'list_projects' diretamente no chat."
}

# ---------------------------------------------------------------------------
# Opção 2 — stdio para Claude Desktop
# ---------------------------------------------------------------------------

_deploy_claude_desktop() {
  echo ""
  echo "==> Configuração para Claude Desktop"

  # Detecta se estamos dentro do WSL
  IS_WSL=0
  if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=1
  fi

  if [ "$IS_WSL" -eq 1 ]; then
    echo "    Ambiente: WSL detectado — usando comando 'wsl' para o Claude Desktop Windows."
    echo ""
    echo "Adicione o bloco abaixo ao arquivo claude_desktop_config.json do Windows:"
    echo "  Caminho típico: %APPDATA%\\Claude\\claude_desktop_config.json"
    echo ""
    cat <<JSON
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "wsl",
      "args": [
        "$PYTHON_IN_VENV",
        "$SERVER_PATH"
      ]
    }
  }
}
JSON
  else
    # macOS ou Linux nativo
    case "$(uname -s)" in
      Darwin)
        DESKTOP_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
        ;;
      Linux)
        DESKTOP_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
        ;;
      *)
        DESKTOP_CONFIG="<caminho do claude_desktop_config.json>"
        ;;
    esac

    echo "Adicione o bloco abaixo ao arquivo: $DESKTOP_CONFIG"
    echo ""
    cat <<JSON
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "$PYTHON_IN_VENV",
      "args": ["$SERVER_PATH"]
    }
  }
}
JSON

    # Tenta copiar para área de transferência se disponível
    CLIPBOARD_CMD=""
    if command -v pbcopy >/dev/null 2>&1; then
      CLIPBOARD_CMD="pbcopy"
    elif command -v xclip >/dev/null 2>&1; then
      CLIPBOARD_CMD="xclip -selection clipboard"
    elif command -v xsel >/dev/null 2>&1; then
      CLIPBOARD_CMD="xsel --clipboard --input"
    fi

    if [ -n "$CLIPBOARD_CMD" ]; then
      printf '{\n  "mcpServers": {\n    "mcp-prompt-refiner": {\n      "command": "%s",\n      "args": ["%s"]\n    }\n  }\n}\n' \
        "$PYTHON_IN_VENV" "$SERVER_PATH" | $CLIPBOARD_CMD
      echo ""
      echo "✓ JSON copiado para a área de transferência."
    fi
  fi

  echo ""
  echo "PRÓXIMOS PASSOS:"
  echo "  1. Edite config.json e insira sua chave da OpenRouter."
  echo "  2. Mescle o bloco acima em mcpServers no claude_desktop_config.json."
  echo "     (se o arquivo já existir, adicione apenas a chave 'mcp-prompt-refiner')"
  echo "  3. Encerre completamente o Claude Desktop (bandeja → Quit) e reabra."
}

# ---------------------------------------------------------------------------
# Opção 3 — HTTP local
# ---------------------------------------------------------------------------

_deploy_http_local() {
  echo ""
  echo "==> Modo HTTP local"
  echo ""

  printf "Host [127.0.0.1]: "
  read -r HTTP_HOST
  HTTP_HOST="${HTTP_HOST:-127.0.0.1}"

  printf "Porta [8000]: "
  read -r HTTP_PORT
  HTTP_PORT="${HTTP_PORT:-8000}"

  MCP_URL="http://${HTTP_HOST}:${HTTP_PORT}/mcp"

  echo ""
  echo "Para iniciar o servidor:"
  echo ""
  echo "  source \"$VENV_DIR/bin/activate\""
  echo "  python \"$SERVER_PATH\" --mode http --host $HTTP_HOST --port $HTTP_PORT"
  echo ""
  echo "O endpoint MCP estará disponível em: $MCP_URL"
  echo ""
  echo "Para conectar no Claude Web Connector ou ChatGPT:"
  echo "  Cole a URL $MCP_URL no campo de conector."
  echo "  (Nota: Claude Web e ChatGPT exigem HTTPS — use opção 4 para URL pública.)"
  echo ""

  printf "Deseja iniciar o servidor agora em segundo plano? [s/N]: "
  read -r START_NOW
  case "$START_NOW" in
    [sS]|[yY])
      echo "==> Iniciando servidor em segundo plano..."
      OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}" \
        nohup "$PYTHON_IN_VENV" "$SERVER_PATH" \
          --mode http --host "$HTTP_HOST" --port "$HTTP_PORT" \
          >"$SCRIPT_DIR/server.log" 2>&1 &
      SERVER_PID=$!
      echo "    PID: $SERVER_PID | Log: $SCRIPT_DIR/server.log"
      echo "    Para encerrar: kill $SERVER_PID"
      ;;
    *)
      echo "    Servidor não iniciado. Rode o comando acima quando quiser."
      ;;
  esac

  echo ""
  echo "PRÓXIMOS PASSOS:"
  echo "  1. Edite config.json e insira sua chave da OpenRouter."
  echo "  2. Inicie o servidor com o comando acima."
  echo "  3. Conecte no cliente MCP usando a URL: $MCP_URL"
}

# ---------------------------------------------------------------------------
# Opção 4 — HTTP com tunnel público
# ---------------------------------------------------------------------------

_deploy_http_tunnel() {
  echo ""
  echo "==> Modo HTTP + tunnel público"
  echo ""

  printf "Host local [0.0.0.0]: "
  read -r HTTP_HOST
  HTTP_HOST="${HTTP_HOST:-0.0.0.0}"

  printf "Porta local [8000]: "
  read -r HTTP_PORT
  HTTP_PORT="${HTTP_PORT:-8000}"

  echo ""
  echo "Passo 1 — Inicie o servidor MCP em HTTP:"
  echo ""
  echo "  source \"$VENV_DIR/bin/activate\""
  echo "  python \"$SERVER_PATH\" --mode http --host $HTTP_HOST --port $HTTP_PORT"
  echo ""
  echo "Passo 2 — Abra um tunnel público (em outro terminal):"
  echo ""
  echo "  Com Cloudflare Tunnel (recomendado para produção/homelab):"
  echo "    cloudflared tunnel --url http://localhost:$HTTP_PORT"
  echo ""
  echo "  Com ngrok (dev/teste):"
  echo "    ngrok http $HTTP_PORT"
  echo ""
  echo "Passo 3 — Cole a URL pública no conector do cliente:"
  echo "  Formato: https://<subdominio>.ngrok.app/mcp"
  echo "        ou https://<seu-dominio>/mcp  (Cloudflare)"
  echo ""
  echo "  Claude Web Connector: Configurações → Conectores → Adicionar conector"
  echo "  ChatGPT:              Configurações → Conectores → Adicionar servidor MCP"
  echo ""
  echo "IMPORTANTE: mantenha o servidor e o tunnel ativos enquanto usar o conector."
  echo ""
  echo "PRÓXIMOS PASSOS:"
  echo "  1. Edite config.json e insira sua chave da OpenRouter."
  echo "  2. Inicie o servidor (Passo 1) e o tunnel (Passo 2) em terminais separados."
  echo "  3. Cole a URL pública no cliente MCP."
}

# ---------------------------------------------------------------------------
# Despacha para a função correspondente
# ---------------------------------------------------------------------------

case "$DEPLOY_MODE" in
  1) _deploy_claude_code ;;
  2) _deploy_claude_desktop ;;
  3) _deploy_http_local ;;
  4) _deploy_http_tunnel ;;
esac

echo ""
echo "==> instalação concluída."
