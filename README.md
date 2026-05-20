# mcp-prompt-refiner

Servidor MCP que refina suas intenções em prompts estruturados e persiste o contexto de cada projeto entre sessões — compatível com Claude Code, Claude Desktop, ChatGPT, Cursor e outros clientes MCP.

---

## Quick Start — Claude Code (3 passos)

```bash
# 1. Clone e instale
git clone https://github.com/asafebelo/mcp-prompt-refiner.git
cd mcp-prompt-refiner
./install.sh   # escolha opção 1 (Claude Code)
```

```bash
# 2. Adicione sua chave da OpenRouter
#    Obtenha em: https://openrouter.ai/keys
echo 'OPENROUTER_API_KEY=sk-or-v1-...' >> .env   # ou edite config.json
```

```bash
# 3. Reinicie o Claude Code — pronto.
#    Nas próximas sessões, peça ao Claude:
#    "use o refine_prompt para: <sua intenção>"
#    "carrega o contexto do projeto <nome>"
```

> **Auto-save de contexto (opcional):** adicione o hook abaixo ao `~/.claude/settings.json` para que o contexto seja salvo automaticamente ao final de cada sessão:
> ```json
> {
>   "hooks": {
>     "Stop": [{ "hooks": [{ "type": "command", "asyncRewake": true,
>       "command": "bash /caminho/para/mcp-prompt-refiner/scripts/auto_save_hook.sh" }] }]
>   }
> }
> ```

> **CLAUDE.md nos seus projetos:** copie [`templates/CLAUDE.md`](templates/CLAUDE.md) para a raiz de cada projeto que usar o servidor. Substitua `[NOME-DO-PROJETO]` e remova o bloco de instruções. O Claude Code carrega o arquivo automaticamente em cada sessão.

> **Outros clientes** (Claude Desktop, ChatGPT, Cursor, Docker + Cloudflare): veja as seções abaixo.

---

## O problema

Quem usa o Claude Code no dia a dia esbarra em duas frustrações recorrentes:

**1. Perda de contexto entre sessões**
Cada vez que você abre o Claude Code em um projeto, ele começa do zero. Decisões técnicas tomadas ontem, o que já foi implementado, por que você escolheu aquela biblioteca — tudo isso precisa ser reexplicado a cada sessão. O resultado é desperdício de tokens e respostas que ignoram o histórico real do projeto.

**2. Prompts rasos geram resultados ruins**
"Adiciona autenticação no meu projeto" é uma intenção, não um prompt. O Claude vai fazer algo, mas provavelmente não exatamente o que você precisava, no estilo que você queria, com as restrições que você tem. Você reescreve, ajusta, itera — e gasta muito mais tempo do que deveria.

---

## A solução

O `mcp-prompt-refiner` é um servidor [MCP](https://modelcontextprotocol.io) que expõe quatro ferramentas ao Claude Code:

| Ferramenta | O que faz |
|---|---|
| `refine_prompt` | Transforma sua intenção crua em um prompt estruturado com objetivo, requisitos, restrições e resultado esperado |
| `save_context` | Persiste o que foi feito na iteração atual em `projects/{nome}.md` |
| `load_context` | Recupera o histórico completo do projeto no início de uma sessão |
| `list_projects` | Lista todos os projetos com contexto salvo |

O refinamento é feito por uma LLM leve via [OpenRouter](https://openrouter.ai), percorrendo uma cadeia de modelos baratos em ordem — só escala para modelos mais caros se os anteriores falharem.

> **Contexto persistido por projeto**
>
> Cada projeto que usa o `mcp-prompt-refiner` ganha automaticamente um arquivo `projects/{nome}.md` dentro da pasta do servidor. Esse arquivo acumula, a cada iteração, o histórico de decisões técnicas, o estado atual da implementação e os próximos passos — permitindo que o assistente retome exatamente de onde parou em qualquer sessão futura, sem precisar reexplicar nada.

---

## Como funciona por baixo dos panos

```
Cliente MCP (Claude Code, Claude Desktop, ChatGPT, Cursor…)
    │
    ▼  stdio (local) ou HTTP (tunnel)
server.py
    │
    ├── tools/refine.py     → monta system prompt + chama OpenRouter
    ├── tools/context.py    → lê/escreve projects/{nome}.md
    └── tools/openrouter.py → percorre cadeia de modelos até obter resposta
```

**Cadeia de modelos (ordem de preferência / custo crescente):**

| # | Modelo | Custo |
|---|---|---|
| 1 | `nvidia/nemotron-3-super-120b-a12b:free` | gratuito |
| 2 | `openai/gpt-oss-120b:free` | gratuito |
| 3 | `meta-llama/llama-3.3-70b-instruct:free` | gratuito |
| 4 | `google/gemini-2.0-flash-exp:free` | gratuito |
| 5 | `inclusionai/ring-2.6-1t:free` | gratuito |
| 6 | `qwen/qwen-2.5-7b-instruct:free` | gratuito |
| 7 | `openai/gpt-oss-20b:free` | gratuito |
| 8 | `meta-llama/llama-3.1-8b-instruct:free` | gratuito |
| 9 | `mistralai/mistral-7b-instruct:free` | gratuito |
| 10 | `poolside/laguna-m.1:free` | gratuito |
| 11 | `google/gemini-2.0-flash-001` | pago ← fallback |
| 12 | `anthropic/claude-haiku-4-5` | pago ← último recurso |

Se o primeiro modelo falhar (rate limit, timeout, resposta vazia), o próximo da lista é tentado automaticamente. Os modelos pagos só entram se todos os gratuitos falharem.

**Persistência de contexto:**
Cada projeto ganha um arquivo `projects/{nome}.md` com descrição, decisões técnicas, estado atual, próximos passos e histórico de iterações com timestamps. O arquivo é local — não vai ao git.

---

## Pré-requisitos

**Todos os modos**
- Conta na [OpenRouter](https://openrouter.ai) com créditos (uso mínimo — modelos gratuitos disponíveis)

**Modo stdio** (Claude Code, Claude Desktop, Cursor…)
- Python 3.11+

**Modo self-host** (Docker + Cloudflare Tunnel)
- [Docker Engine](https://docs.docker.com/engine/install/) — Python local não é necessário
- Domínio gerenciado no [Cloudflare](https://cloudflare.com) (gratuito)

---

## Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/asafebelo/mcp-prompt-refiner.git
cd mcp-prompt-refiner

# 2. Execute o instalador
# Cria o .venv, instala dependências e registra o MCP no Claude Code
./install.sh
```

> Se tiver Python 3.13: `PYTHON_BIN=python3.13 ./install.sh`

---

## Configuração

Abra `config.json` (criado pelo `install.sh` a partir do `config.example.json`) e substitua o placeholder pela sua chave obtida em [openrouter.ai/keys](https://openrouter.ai/keys):

```json
{
  "openrouter": {
    "api_key": "sk-or-v1-...",
    "models": [
      "google/gemini-2.0-flash-001",
      "google/gemini-flash-1.5-8b",
      "meta-llama/llama-3.1-8b-instruct",
      "anthropic/claude-haiku-4-5"
    ],
    "max_tokens": 2000,
    "temperature": 0.3
  },
  "projects_dir": "projects",
  "default_language": "pt-BR"
}
```

> **Alternativa segura:** defina a variável de ambiente `OPENROUTER_API_KEY` em vez de escrever a chave no arquivo. A env var tem prioridade sobre `config.json`.

---

## Passo a passo de uso

### Iniciando um projeto novo

1. Abra o Claude Code no seu projeto
2. Peça ao Claude para refinar sua intenção:

   > "use o refine_prompt para: quero adicionar autenticação JWT no meu servidor FastAPI"

3. O Claude mostra o prompt estruturado e pede confirmação antes de executar
4. Ao finalizar a sessão, o contexto é salvo automaticamente (se o hook estiver ativo), ou manualmente:

   > "salva o contexto do projeto meu-projeto com o que foi feito hoje"

### Retomando um projeto existente

1. Abra o Claude Code no projeto
2. Carregue o histórico:

   > "carrega o contexto do projeto meu-projeto antes de continuar"

3. O Claude lê o `projects/meu-projeto.md` e retoma de onde parou — sem você precisar reexplicar nada

> **Onde fica o arquivo de contexto?**
> O arquivo `projects/{nome}.md` fica dentro da pasta do `mcp-prompt-refiner`, não no seu projeto. Ele é local e não vai ao git (coberto pelo `.gitignore`). Você pode abri-lo a qualquer momento para revisar ou editar manualmente o histórico.

### Verificar todos os projetos salvos

> "lista todos os projetos com contexto salvo"

---

## Conectando o mcp-prompt-refiner aos clientes de IA

| Clientes | Modo | Como configurar |
|---|---|---|
| Claude Code, Claude Desktop, Cursor, Zed, Windsurf | stdio (local) | Seções abaixo |
| Claude Web, ChatGPT, Codex CLI | HTTP público | [Deploy via Docker Compose](#deploy-via-docker-compose--cloudflare-named-tunnel) |

---

### Claude Code (CLI)

#### Pré-requisitos
- [Claude Code](https://claude.ai/code) instalado (`claude --version` deve funcionar)
- Python 3.11+ e o projeto clonado com `.venv` criado (`./install.sh`)
- Chave da [OpenRouter](https://openrouter.ai/keys) configurada em `config.json` ou via `OPENROUTER_API_KEY`

#### Registrando o servidor

Execute o instalador e escolha a opção **1**:

```bash
./install.sh
# → escolha: 1) stdio — Claude Code
```

Ou registre manualmente:

```bash
claude mcp add --scope user mcp-prompt-refiner \
  /caminho/para/mcp-prompt-refiner/.venv/bin/python \
  /caminho/para/mcp-prompt-refiner/server.py

# Verifique:
claude mcp get mcp-prompt-refiner
```

O flag `--scope user` torna o servidor disponível em **todos os seus projetos**, sem precisar registrar novamente a cada clone.

#### Reiniciando

O servidor conecta ao iniciar uma nova sessão. Após registrar, reinicie o Claude Code.

#### (Opcional) Hook de auto-save

Ative o hook para que `save_context` seja chamado automaticamente ao final de cada sessão, sem você precisar pedir:

```json
// Adicione ao ~/.claude/settings.json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash /caminho/para/mcp-prompt-refiner/scripts/auto_save_hook.sh"
          }
        ]
      }
    ]
  }
}
```

Troque `/caminho/para/mcp-prompt-refiner` pelo caminho real onde você clonou o projeto.

**Como funciona:** ao parar, o Claude Code executa o hook. Se `save_context` ainda não foi chamado na sessão, o hook injeta uma instrução para que o Claude o chame antes de encerrar. Na segunda parada (após salvar), `CLAUDE_STOP_HOOK_ACTIVE=1` impede nova injeção, evitando loop infinito.

#### Como usar no chat

As quatro ferramentas aparecem automaticamente:

```
use o refine_prompt para: quero adicionar autenticação JWT no meu FastAPI
```

#### Solução de problemas
- **Servidor não aparece:** verifique com `claude mcp list` e confirme que o caminho do `.venv` está correto.
- **Erro "module not found":** rode `.venv/bin/pip install -r requirements.txt` dentro do diretório do projeto.

---

### Claude Desktop (Windows / macOS / Linux)

#### Pré-requisitos
- [Claude Desktop](https://claude.ai/download) instalado
- Python 3.11+ acessível no sistema (ou via WSL no Windows)
- Projeto clonado e `.venv` criado
- **Windows:** WSL 2 instalado e o projeto clonado dentro do filesystem WSL (ex: `/mnt/d/...` ou `~/projetos/...`)

#### Como configurar

Execute o instalador dentro do WSL (Windows) ou terminal nativo (macOS/Linux) e escolha a opção **2**:

```bash
./install.sh
# → escolha: 2) stdio — Claude Desktop
```

O script detecta o sistema e exibe o bloco JSON correto. Copie-o e adicione ao arquivo de configuração do Claude Desktop:

| Sistema | Caminho do arquivo |
|---|---|
| Windows | `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

**Exemplo para Windows com WSL** (gerado automaticamente pelo `install.sh`):

```json
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "wsl",
      "args": [
        "/caminho/wsl/.venv/bin/python",
        "/caminho/wsl/server.py"
      ]
    }
  }
}
```

**Exemplo para macOS / Linux nativo:**

```json
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "/caminho/para/.venv/bin/python",
      "args": ["/caminho/para/server.py"]
    }
  }
}
```

> Se o arquivo `claude_desktop_config.json` já existir com outros servidores, adicione apenas a chave `"mcp-prompt-refiner"` dentro de `"mcpServers"` — não substitua o arquivo inteiro.

#### Reiniciar corretamente

Feche o Claude Desktop completamente — **não apenas minimize**:
- **Windows:** clique com botão direito no ícone da bandeja do sistema → **Quit**
- **macOS:** menu Claude → **Quit Claude**

Reabra. O servidor conecta na inicialização.

#### Solução de problemas
- **MCP não aparece em Configurações → Conectores:** o processo não foi encerrado completamente. Use o Gerenciador de Tarefas (Windows) ou `killall Claude` (macOS) e tente novamente.
- **Erro de caminho no Windows:** confirme que o caminho nos `args` é um caminho WSL (começa com `/`), não um caminho Windows (`C:\`).

---

### Cursor / Zed / Windsurf

Esses editores seguem o mesmo padrão stdio do Claude Desktop.

Adicione nas configurações de MCP do editor (geralmente em um arquivo `mcp.json` ou nas preferências):

```json
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "/caminho/para/.venv/bin/python",
      "args": ["/caminho/para/server.py"]
    }
  }
}
```

Consulte a documentação de cada editor para o caminho exato do arquivo de configuração.

---

## Deploy via Docker Compose + Cloudflare Named Tunnel

Use esta opção para expor o servidor publicamente com URL fixa. Necessário para Claude Web, ChatGPT e Codex CLI — e também funciona para Claude Code e Claude Desktop via URL, sem instalação local do Python.

### Pré-requisitos

- [Docker Engine](https://docs.docker.com/engine/install/) instalado
- Conta no [Cloudflare](https://cloudflare.com) com um domínio gerenciado (gratuito)
- Chave da [OpenRouter](https://openrouter.ai/keys)

### Passo a passo

**1. Crie o Named Tunnel no Cloudflare**

1. Acesse [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → **Zero Trust → Networks → Tunnels**
2. Clique em **Create a tunnel** → escolha **Cloudflared**
3. Dê um nome (ex: `mcp-refiner`) e clique em **Save tunnel**
4. Copie o **token** exibido na tela de instalação
5. Em **Public Hostname**, configure:
   - **Subdomain:** ex `mcp` (resultará em `mcp.seudominio.com`)
   - **Domain:** seu domínio
   - **Service:** `http://mcp-server:8000`

> `http://mcp-server:8000` funciona porque `cloudflared` e o servidor rodam na mesma rede Docker interna. Use exatamente este valor no dashboard.

**2. Configure as variáveis de ambiente**

A forma mais simples é usar o instalador — ele guia o preenchimento interativamente e gera o `MCP_AUTH_TOKEN` automaticamente:

```bash
./install.sh  # → opção 3
```

Ou configure manualmente:

```bash
cp .env.example .env
# Preencha OPENROUTER_API_KEY e CLOUDFLARE_TUNNEL_TOKEN
# Gere um MCP_AUTH_TOKEN seguro:
openssl rand -hex 32
# Cole o resultado como valor de MCP_AUTH_TOKEN no .env
```

**3. Suba os containers**

```bash
docker compose up -d
```

**4. Verifique o tunnel**

```bash
docker compose logs -f cloudflared
# Aguarde: "Registered tunnel connection"
```

### Conectando os clientes ao servidor HTTP

Com o tunnel ativo, use `https://mcp.seudominio.com/mcp` em qualquer cliente.

> **Autenticação:** se você definiu `MCP_AUTH_TOKEN` no `.env`, todos os clientes precisam enviar o header `Authorization: Bearer <token>`. Consulte a documentação de cada cliente para saber onde configurar headers customizados. Para testar:
> ```bash
> curl https://mcp.seudominio.com/mcp \
>   -H "Authorization: Bearer SEU_TOKEN"
> ```

**Claude Web Connector** (requer plano Pro ou Team)
1. [claude.ai](https://claude.ai) → **Configurações → Conectores → Adicionar conector**
2. Cole a URL e salve. Abra uma nova conversa.

**ChatGPT Web e Desktop** (requer Plus, Pro ou Team)
1. ChatGPT → **Configurações → Conectores → Adicionar servidor MCP**
2. Cole a URL e confirme. Abra uma nova conversa.

**Codex CLI**
```toml
# ~/.codex/config.toml
[mcp_servers.mcp-prompt-refiner]
url = "https://mcp.seudominio.com/mcp"
```

**Claude Code via URL** (alternativa ao stdio local)
```bash
claude mcp add --scope user --url https://mcp.seudominio.com/mcp mcp-prompt-refiner
```

**Claude Desktop via URL**
```json
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "type": "sse",
      "url": "https://mcp.seudominio.com/mcp"
    }
  }
}
```

### Comandos úteis

```bash
docker compose logs -f mcp-server   # logs do servidor MCP
docker compose logs -f cloudflared  # status do tunnel
docker compose ps                   # estado dos serviços
docker compose down                 # encerrar tudo
docker compose up -d --build        # recriar após atualização
```

Os arquivos `projects/*.md` são montados como volume em `./projects/` — persistem entre restarts e ficam acessíveis no host.

---

## Configuração avançada

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Chave da OpenRouter (prioridade sobre `config.json`) |
| `CLOUDFLARE_TUNNEL_TOKEN` | — | Token do Named Tunnel (deploy Docker) |
| `MCP_PORT` | `8000` | Porta do servidor HTTP |
| `MCP_HOST` | `127.0.0.1` | Host do servidor HTTP (use `0.0.0.0` só com `MCP_AUTH_TOKEN` definido) |
| `MCP_AUTH_TOKEN` | (vazio) | Token Bearer para autenticação no endpoint `/mcp`. Gere com `openssl rand -hex 32`. Se vazio, o servidor opera sem auth. |

### Personalizar a cadeia de modelos

Edite o campo `models` em `config.json`. A ordem importa — o primeiro modelo disponível é usado:

```json
"models": [
  "google/gemini-2.0-flash-001",
  "mistralai/mistral-small-3.1-24b-instruct",
  "anthropic/claude-haiku-4-5"
]
```

Consulte os modelos disponíveis em [openrouter.ai/models](https://openrouter.ai/models).

---

## Estrutura do projeto

```
mcp-prompt-refiner/
├── server.py             # Entry point — registra e despacha as tools MCP
├── tools/
│   ├── __init__.py
│   ├── refine.py         # refine_prompt: monta o system prompt e chama a LLM
│   ├── context.py        # save_context, load_context, list_projects
│   └── openrouter.py     # Cliente OpenRouter com cadeia de modelos
├── projects/             # Um .md por projeto (local, não vai ao git)
├── scripts/
│   └── auto_save_hook.sh # Stop hook do Claude Code para auto-save de contexto
├── Dockerfile            # Imagem Python para deploy em container
├── docker-compose.yml    # Orquestra mcp-server + cloudflared
├── .env.example          # Template de variáveis de ambiente
├── config.json           # Sua configuração com a chave (não vai ao git)
├── config.example.json   # Template versionado sem segredos
├── requirements.txt
├── install.sh
├── CLAUDE.md             # Instrui o Claude Code a usar as ferramentas
└── README.md
```

---

## Segurança

- `config.json` está no `.gitignore` — sua chave nunca vai ao repositório
- Use a variável de ambiente `OPENROUTER_API_KEY` para não ter a chave em disco
- Os contextos de projeto (`projects/*.md`) também são locais e não versionados

---

## Licença

MIT
