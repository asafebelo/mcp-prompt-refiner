#!/usr/bin/env bash
# install.sh — instala e configura o mcp-prompt-refiner
#
# 1. Cria e ativa um virtualenv em .venv/
# 2. Instala dependências de requirements.txt
# 3. Garante a existência de config.json (copia de config.example.json se faltar)
# 4. Detecta Claude Desktop ou Claude Code e registra o MCP
# 5. Imprime instruções finais ao usuário

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
  echo "ERRO: '$PYTHON_BIN' não encontrado. Instale Python 3.13 ou ajuste a variável PYTHON_BIN." >&2
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

# --- 3. Instala dependências ---
echo "==> instalando dependências"
pip install --upgrade pip >/dev/null
pip install -r requirements.txt

# --- 4. Garante config.json ---
if [ ! -f "$SCRIPT_DIR/config.json" ]; then
  if [ -f "$SCRIPT_DIR/config.example.json" ]; then
    cp "$SCRIPT_DIR/config.example.json" "$SCRIPT_DIR/config.json"
    echo "==> config.json criado a partir de config.example.json"
  else
    echo "AVISO: nem config.json nem config.example.json existem." >&2
  fi
else
  echo "==> config.json já existe — mantido"
fi

# --- 5. Detecta cliente Claude e registra o MCP ---
PYTHON_IN_VENV="$VENV_DIR/bin/python"

register_claude_code() {
  if command -v claude >/dev/null 2>&1; then
    echo "==> Claude Code detectado — registrando MCP via 'claude mcp add'"
    # Remove registro antigo se existir, ignora erro.
    claude mcp remove mcp-prompt-refiner >/dev/null 2>&1 || true
    claude mcp add mcp-prompt-refiner "$PYTHON_IN_VENV" "$SERVER_PATH"
    echo "    registrado em Claude Code."
    return 0
  fi
  return 1
}

register_claude_desktop() {
  # macOS e Linux têm caminhos diferentes para a config do Claude Desktop.
  local config_path=""
  case "$(uname -s)" in
    Darwin)
      config_path="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
      ;;
    Linux)
      config_path="$HOME/.config/Claude/claude_desktop_config.json"
      ;;
    *)
      return 1
      ;;
  esac

  if [ ! -f "$config_path" ]; then
    return 1
  fi

  echo "==> Claude Desktop detectado em: $config_path"
  echo "    Adicione manualmente esta entrada em mcpServers:"
  cat <<JSON

  "mcp-prompt-refiner": {
    "command": "$PYTHON_IN_VENV",
    "args": ["$SERVER_PATH"]
  }

JSON
  return 0
}

REGISTERED=0
if register_claude_code; then
  REGISTERED=1
fi
if register_claude_desktop; then
  REGISTERED=1
fi

if [ "$REGISTERED" -eq 0 ]; then
  echo "AVISO: nenhum cliente Claude detectado automaticamente." >&2
  echo "       Para Claude Code, rode manualmente:"
  echo "         claude mcp add mcp-prompt-refiner \"$PYTHON_IN_VENV\" \"$SERVER_PATH\""
fi

# --- 6. Instruções finais ---
cat <<EOF

==> instalação concluída.

PRÓXIMOS PASSOS:

  1. Edite config.json e coloque sua chave da OpenRouter em openrouter.api_key
     (obtenha em https://openrouter.ai/keys).

  2. Se você não usa Claude Code, registre manualmente o MCP no seu cliente
     usando o comando ou a entrada JSON mostrados acima.

  3. Para testar localmente, ative o venv e rode:
       source .venv/bin/activate
       python server.py
     (o servidor fica aguardando JSON-RPC via stdio — encerre com Ctrl+C)

  4. Reinicie o Claude Code/Desktop para carregar o novo servidor.

EOF
