# Handoff — mcp-prompt-refiner

Último update: 2026-05-14

## O que está pronto

- Código completo: `server.py` + `tools/` (refine, context, openrouter).
- `install.sh` cria venv, instala deps e registra o MCP no Claude Code.
- Repositório privado no GitHub: https://github.com/asafebelo/mcp-prompt-refiner
- `.gitignore` cobrindo: `config.json` (segredo), `.venv/`, `__pycache__/`, `.claude/`, caches, IDE, OS.
- Identidade git **local** ao repo: `Asafe Belo <asafemito22@gmail.com>`.

## Estado da máquina de origem (WSL)

- Python 3.13.13 instalado via deadsnakes PPA.
- `.venv/` criado com Python 3.13; dependências instaladas a partir de `requirements.txt`.
- MCP `mcp-prompt-refiner` registrado no Claude Code (stdio).

## Bloqueio atual

`config.json` ainda contém o placeholder `COLOQUE_SUA_CHAVE_AQUI` no campo `openrouter.api_key`. Sem a chave real, `refine_prompt` falha ao chamar a OpenRouter. `save_context` / `load_context` / `list_projects` funcionam normalmente (são só I/O de arquivo).

## Próximos passos (em ordem)

1. Pegar a chave em https://openrouter.ai/keys e colar em `config.json` → `openrouter.api_key`.
2. Reiniciar o Claude Code para que ele recarregue o MCP registrado.
3. Testar o fluxo end-to-end:
   - `refine_prompt` com uma intenção crua.
   - `save_context` após uma iteração.
   - `load_context` para validar persistência.

## Setup no novo computador (amanhã)

```bash
# 1. Clonar
git clone https://github.com/asafebelo/mcp-prompt-refiner.git
cd mcp-prompt-refiner

# 2. Garantir Python 3.13 disponível
python3.13 --version  # se faltar: deadsnakes PPA + python3.13 python3.13-venv

# 3. Instalar (cria .venv, instala deps, registra MCP no Claude Code)
PYTHON_BIN=python3.13 ./install.sh

# 4. Colocar a chave OpenRouter em config.json (NÃO commitar — está no .gitignore)

# 5. Reiniciar o Claude Code
```

## Decisões tomadas

- `projects/*.md` está **ignorado** no git: cada usuário tem seus próprios contextos persistidos localmente. `projects/.gitkeep` preserva a pasta no repo.
- `config.example.json` é o template versionado; `config.json` (com segredo) nunca vai pro repo.
- gh CLI foi instalado nesta máquina; no outro computador será necessário instalar e fazer `gh auth login` se quiser usar o gh, ou usar git + credenciais HTTPS direto.
