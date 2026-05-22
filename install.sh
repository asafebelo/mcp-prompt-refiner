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
    echo "    (use config.json para personalizar modelos, temperatura e idioma)"
  else
    echo "AVISO: nem config.json nem config.example.json existem." >&2
  fi
else
  echo "==> config.json já existe — mantido"
fi

# ---------------------------------------------------------------------------
# Garante .env e funções de leitura/escrita (compartilhado por todos os modos)
# ---------------------------------------------------------------------------

ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  cp "$SCRIPT_DIR/.env.example" "$ENV_FILE"
  echo "==> .env criado a partir de .env.example"
fi

# Lê valor atual de uma variável no .env (ignora linhas comentadas)
_get_env_val() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-
}

# Define ou atualiza variável no .env
_set_env_val() {
  local key="$1" val="$2"
  # Escapa caracteres especiais do sed no valor (|, \, &) para evitar
  # interpretação no RHS do comando s|...|...|.
  local escaped_val
  escaped_val="$(printf '%s' "$val" | sed -e 's/[\\&|]/\\&/g')"
  if grep -qE "^#*[[:space:]]*${key}=" "$ENV_FILE" 2>/dev/null; then
    sed -i "s|^#*[[:space:]]*${key}=.*|${key}=${escaped_val}|" "$ENV_FILE"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

# ---------------------------------------------------------------------------
# Menu interativo — escolha do modo de deploy
# ---------------------------------------------------------------------------

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           mcp-prompt-refiner :: modos de deploy               ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  1) stdio — Claude Code (dev local)                           ║"
echo "║  2) stdio — Claude Desktop (WSL / Linux / macOS)              ║"
echo "║  3) Docker Compose + Cloudflare Named Tunnel (self-host)      ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Você pode configurar múltiplos ambientes de uma vez.         ║"
echo "║  Exemplos: '1'    →  apenas Claude Code                       ║"
echo "║            '1,2'  →  Claude Code + Claude Desktop             ║"
echo "║            '1,3'  →  Code local + self-host compartilhado     ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Valida e normaliza entrada com seleção múltipla (ex: "1,2" ou "1 2")
DEPLOY_MODES=""
while true; do
  printf "Escolha os modos [1-3, separados por vírgula]: "
  read -r RAW_INPUT

  NORMALIZED="$(echo "$RAW_INPUT" | tr ' ' ',' | tr -s ',')"
  VALID=1
  DEPLOY_MODES=""

  IFS=',' read -r -a SELECTIONS <<< "$NORMALIZED"
  for SEL in "${SELECTIONS[@]}"; do
    SEL="$(echo "$SEL" | tr -d '[:space:]')"
    case "$SEL" in
      1|2|3)
        case ",$DEPLOY_MODES," in
          *",$SEL,"*) ;;
          *) DEPLOY_MODES="${DEPLOY_MODES:+$DEPLOY_MODES,}$SEL" ;;
        esac
        ;;
      "")
        ;;
      *)
        echo "  Valor inválido: '$SEL'. Use apenas os números 1, 2 ou 3."
        VALID=0
        break
        ;;
    esac
  done

  if [ "$VALID" -eq 1 ] && [ -n "$DEPLOY_MODES" ]; then
    break
  elif [ "$VALID" -eq 1 ]; then
    echo "  Entrada vazia. Digite ao menos um número (1-3)."
  fi
done

echo "  Ambientes selecionados: $DEPLOY_MODES"

# ---------------------------------------------------------------------------
# Coleta OPENROUTER_API_KEY e salva em .env (fonte única para todos os modos)
# ---------------------------------------------------------------------------

OR_KEY="${OPENROUTER_API_KEY:-}"
if [ -z "$OR_KEY" ]; then
  CURRENT_OR=$(_get_env_val "OPENROUTER_API_KEY")
  if [ -n "$CURRENT_OR" ] && [ "$CURRENT_OR" != "your_openrouter_key_here" ]; then
    echo "==> OPENROUTER_API_KEY já configurada no .env — mantida"
  else
    echo ""
    echo "Chave da OpenRouter (https://openrouter.ai/keys):"
    printf "  Cole aqui (Enter para configurar depois): "
    read -rs OR_KEY
    echo ""
    if [ -z "$OR_KEY" ]; then
      echo "  AVISO: sem chave — edite .env e preencha OPENROUTER_API_KEY antes de usar." >&2
    fi
  fi
fi

if [ -n "$OR_KEY" ]; then
  _set_env_val "OPENROUTER_API_KEY" "$OR_KEY"
  echo "==> OPENROUTER_API_KEY salva em .env"
fi

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
  echo "  1. Reinicie o Claude Code para carregar o servidor."
  echo "  2. Nas próximas sessões, use 'refine_prompt', 'save_context',"
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
    echo "  Caminho: %LOCALAPPDATA%\\Packages\\Claude_*\\LocalCache\\Roaming\\Claude\\claude_desktop_config.json"
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
  echo "  1. Mescle o bloco acima em mcpServers no claude_desktop_config.json."
  echo "     (se o arquivo já existir, adicione apenas a chave 'mcp-prompt-refiner')"
  echo "  2. Encerre completamente o Claude Desktop (bandeja → Quit) e reabra."
}

# ---------------------------------------------------------------------------
# Opção 3 — Docker Compose + Cloudflare Named Tunnel
# ---------------------------------------------------------------------------

_deploy_docker_compose() {
  echo ""
  echo "==> Deploy via Docker Compose + Cloudflare Named Tunnel"
  echo ""

  # Verifica Docker
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERRO: 'docker' não encontrado no PATH." >&2
    echo "      Instale o Docker Engine: https://docs.docker.com/engine/install/" >&2
    return 1
  fi

  # Verifica Docker Compose (plugin v2 ou standalone)
  if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
  elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
  else
    echo "ERRO: Docker Compose não encontrado." >&2
    echo "      Instale o plugin: https://docs.docker.com/compose/install/" >&2
    return 1
  fi

  # --- CLOUDFLARE_TUNNEL_TOKEN ---
  CURRENT_CF=$(_get_env_val "CLOUDFLARE_TUNNEL_TOKEN")
  if [ -z "$CURRENT_CF" ] || [ "$CURRENT_CF" = "your_tunnel_token_here" ]; then
    echo ""
    echo "Token do Cloudflare Named Tunnel"
    echo "  (one.dash.cloudflare.com → Zero Trust → Networks → Tunnels → Create a tunnel)"
    echo "  Configure o hostname público com Service: http://mcp-server:8000"
    printf "  Cole o token aqui: "
    read -rs CF_TOKEN
    echo ""
    [ -n "$CF_TOKEN" ] && _set_env_val "CLOUDFLARE_TUNNEL_TOKEN" "$CF_TOKEN" && echo "    ✓ CLOUDFLARE_TUNNEL_TOKEN salva"
  else
    echo "    CLOUDFLARE_TUNNEL_TOKEN já configurada — mantida"
  fi

  # --- MCP_AUTH_TOKEN (obrigatório no modo Docker: o servidor recusa bind em
  #     0.0.0.0 sem token, então geramos automaticamente se não estiver definido) ---
  CURRENT_AUTH=$(_get_env_val "MCP_AUTH_TOKEN")
  if [ -z "$CURRENT_AUTH" ]; then
    echo ""
    echo "==> Gerando MCP_AUTH_TOKEN (obrigatório para Docker + Cloudflare Tunnel)..."
    if command -v openssl >/dev/null 2>&1; then
      NEW_AUTH_TOKEN=$(openssl rand -hex 32)
    else
      NEW_AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    fi
    _set_env_val "MCP_AUTH_TOKEN" "$NEW_AUTH_TOKEN"
    echo "    ✓ MCP_AUTH_TOKEN gerado e salvo em .env"
    echo "      Para ver: grep MCP_AUTH_TOKEN .env"
    echo ""
    echo "    IMPORTANTE: guarde este token — clientes de IA precisam enviá-lo"
    echo "    no header:  Authorization: Bearer <token>"
  else
    echo "    MCP_AUTH_TOKEN já configurada — mantida"
  fi

  echo ""
  echo "==> Iniciando containers..."
  cd "$SCRIPT_DIR"
  $COMPOSE_CMD up -d --build

  echo ""
  echo "✓ Containers iniciados."
  echo ""
  echo "Comandos úteis:"
  echo "  $COMPOSE_CMD logs -f mcp-server   # acompanhar logs do servidor"
  echo "  $COMPOSE_CMD logs -f cloudflared  # verificar status do tunnel"
  echo "  $COMPOSE_CMD ps                   # ver estado dos serviços"
  echo "  $COMPOSE_CMD down                 # encerrar tudo"
  echo ""
  echo "PRÓXIMOS PASSOS:"
  echo "  1. Aguarde o tunnel ficar ativo: $COMPOSE_CMD logs -f cloudflared"
  echo "  2. Anote a URL pública configurada no Cloudflare (seu domínio/subdomínio)."
  echo "  3. Configure o cliente de IA usando: https://seu-dominio/mcp"
  echo "     (com header Authorization: Bearer <token> se MCP_AUTH_TOKEN estiver ativo)"
}

# ---------------------------------------------------------------------------
# Despacha para cada ambiente selecionado (em ordem 1 → 2 → 3)
# ---------------------------------------------------------------------------

for MODE in 1 2 3; do
  case ",$DEPLOY_MODES," in
    *",$MODE,"*)
      case "$MODE" in
        1) _deploy_claude_code ;;
        2) _deploy_claude_desktop ;;
        3) _deploy_docker_compose ;;
      esac
      ;;
  esac
done

echo ""
echo "==> instalação concluída."
