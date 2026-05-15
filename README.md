# mcp-prompt-refiner

Servidor MCP que refina suas intenções em prompts estruturados e persiste o contexto de cada projeto entre sessões do Claude Code.

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
Claude Code
    │
    ▼
server.py  ←── MCP stdio transport
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

- Python 3.11+
- [Claude Code](https://claude.ai/code) instalado
- Conta na [OpenRouter](https://openrouter.ai) com créditos (uso mínimo — modelos gratuitos ou de baixo custo)

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

### 1. Chave da OpenRouter

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

### 2. Registro no Claude Code

O `install.sh` registra automaticamente. Para registrar manualmente com escopo de usuário (disponível em todos os projetos):

```bash
claude mcp add --scope user mcp-prompt-refiner \
  /caminho/para/mcp-prompt-refiner/.venv/bin/python \
  /caminho/para/mcp-prompt-refiner/server.py

# Verificar
claude mcp get mcp-prompt-refiner
```

### 3. Reinicie o Claude Code

O servidor só conecta ao iniciar uma nova sessão.

---

## Passo a passo de uso

### Iniciando um projeto novo

1. Abra o Claude Code no seu projeto
2. Peça ao Claude para refinar sua intenção:

   > "use o refine_prompt para: quero adicionar autenticação JWT no meu servidor FastAPI"

3. O Claude mostra o prompt estruturado e pede confirmação antes de executar
4. Ao finalizar a sessão, salve o contexto:

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

O servidor opera em dois modos de transporte:

- **stdio** — comunicação via stdin/stdout, sem rede. Usado por Claude Code, Claude Desktop, Cursor, Zed e Windsurf.
- **HTTP** — expõe o endpoint `/mcp` via HTTP. Necessário para Claude Web Connector, ChatGPT e Codex CLI (requer URL HTTPS pública).

O script `install.sh` guia você pelo modo correto com um menu interativo. As seções abaixo explicam o processo completo para cada cliente.

---

### Claude Code (CLI)

**MCP (Model Context Protocol)** é o protocolo que permite ao Claude Code se comunicar com servidores externos de ferramentas — como este.

#### Pré-requisitos
- [Claude Code](https://claude.ai/code) instalado (`claude --version` deve funcionar)
- Python 3.11+ e o projeto clonado com `.venv` criado (`./install.sh`)
- Chave da [OpenRouter](https://openrouter.ai/keys) configurada em `config.json` ou via `OPENROUTER_API_KEY`

#### Como configurar

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

#### Como usar no chat

Reinicie o Claude Code. As quatro ferramentas aparecem automaticamente:

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
| Windows (Store) | `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\claude_desktop_config.json` |
| Windows (instalador direto) | `%APPDATA%\Claude\claude_desktop_config.json` |
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

### Claude Web Connector

O Claude Web permite adicionar servidores MCP externos via **Configurações → Conectores personalizados**. O servidor precisa estar acessível via **HTTPS público**.

#### Pré-requisitos
- Conta Claude Pro ou Team (conectores personalizados requerem plano pago)
- Servidor rodando em modo HTTP acessível publicamente
- URL HTTPS válida apontando para o endpoint `/mcp` — use [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) ou [ngrok](https://ngrok.com)

#### Como iniciar o servidor

```bash
# Ative o venv
source .venv/bin/activate

# Inicie em modo HTTP
python server.py --mode http --host 0.0.0.0 --port 8000
```

Ou via variável de ambiente:

```bash
MCP_MODE=http MCP_PORT=8000 python server.py
```

#### Expondo com Cloudflare Tunnel (recomendado para homelab)

```bash
# Em outro terminal, com cloudflared instalado:
cloudflared tunnel --url http://localhost:8000
# → URL gerada: https://xxxx.trycloudflare.com
```

Para uma URL permanente em um domínio próprio, configure um [Named Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/get-started/) no painel da Cloudflare.

#### Expondo com ngrok (dev / testes rápidos)

```bash
ngrok http 8000
# → URL gerada: https://xxxx.ngrok.app
```

#### Configurando no Claude Web

1. Acesse [claude.ai](https://claude.ai) → **Configurações** → **Conectores**
2. Clique em **Adicionar conector**
3. Cole a URL pública no formato: `https://xxxx.trycloudflare.com/mcp`
4. Salve e inicie uma nova conversa — as ferramentas estarão disponíveis

#### Solução de problemas
- **Erro de conexão:** confirme que o servidor está rodando (`curl https://sua-url/mcp -X POST`) e que o tunnel está ativo.
- **Tunnel caiu:** o Claude Web desconecta automaticamente quando o tunnel encerra. Reinicie o tunnel e reconecte o conector.

---

### ChatGPT (Web, Desktop e Codex CLI)

O ChatGPT suporta servidores MCP via **Configurações → Conectores**. O fluxo é idêntico ao Claude Web: servidor HTTP + URL HTTPS pública.

#### Pré-requisitos
- Conta ChatGPT Plus, Pro ou Team
- Servidor rodando em modo HTTP (mesmo processo descrito na seção Claude Web acima)
- URL HTTPS pública via Cloudflare Tunnel ou ngrok

#### Configurando no ChatGPT Web / Desktop

1. Abra o ChatGPT → **Configurações** → **Conectores** (ou **MCP Servers** dependendo da versão)
2. Clique em **Adicionar servidor MCP**
3. Cole a URL: `https://sua-url-publica/mcp`
4. Confirme e inicie uma nova conversa

> O ChatGPT Desktop (aplicativo nativo) segue o mesmo fluxo da versão web para conectores remotos.

#### Configurando no Codex CLI

O [Codex CLI](https://github.com/openai/codex) da OpenAI suporta MCP via arquivo de configuração:

```bash
# ~/.codex/config.toml (ou conforme documentação da versão instalada)
[mcp_servers.mcp-prompt-refiner]
url = "https://sua-url-publica/mcp"
```

Consulte a [documentação oficial do Codex CLI](https://github.com/openai/codex) para a versão exata do formato de configuração.

#### Solução de problemas
- **Ferramentas não aparecem:** inicie uma **nova conversa** após adicionar o conector — conversas existentes não recarregam os servidores MCP.
- **Erro 401/403:** o endpoint `/mcp` deste servidor não requer autenticação por padrão. Se aparecer erro de auth, verifique se há proxy ou firewall na frente do tunnel.

---

### Referência rápida: variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `MCP_MODE` | `stdio` | Modo de transporte: `stdio` ou `http` |
| `MCP_HOST` | `0.0.0.0` | Host para modo HTTP |
| `MCP_PORT` | `8000` | Porta para modo HTTP |
| `OPENROUTER_API_KEY` | — | Chave da OpenRouter (prioridade sobre `config.json`) |

---

## Personalizar a cadeia de modelos

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
