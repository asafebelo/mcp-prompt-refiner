# mcp-prompt-refiner

Servidor MCP que refina suas intenções em prompts estruturados e persiste o contexto de cada projeto entre sessões — compatível com Claude Code, Claude Desktop, ChatGPT, Cursor e outros clientes MCP.

---

A principal dificuldade na interação humano-IA não é a IA — é o prompt.

**"Adiciona autenticação no meu projeto"** é uma intenção, não um prompt. O assistente vai fazer algo, mas provavelmente não exatamente o que você precisava, no estilo que você queria, com as restrições que você tem. Você reescreve, ajusta, itera — e gasta muito mais tempo do que deveria.

O segundo problema: cada vez que você abre o Claude Code em um projeto, ele começa do zero. Decisões técnicas tomadas ontem, o que já foi implementado, por que você escolheu aquela biblioteca — tudo precisa ser reexplicado a cada sessão.

O `mcp-prompt-refiner` ataca os dois: transforma intenções cruas em prompts estruturados antes de executar, e persiste o contexto de cada projeto entre sessões para que o assistente retome exatamente de onde parou.

---

## Ferramentas

| Ferramenta | O que faz |
|---|---|
| `refine_prompt` | Transforma uma intenção crua em um prompt estruturado com objetivo, requisitos, restrições e resultado esperado |
| `save_context` | Persiste o que foi feito na iteração atual em `projects/{nome}.md` |
| `load_context` | Recupera o histórico completo do projeto no início de uma sessão |
| `list_projects` | Lista todos os projetos com contexto salvo |

O refinamento é feito por uma LLM leve via [OpenRouter](https://openrouter.ai), percorrendo uma cadeia de modelos em ordem de custo crescente — modelos gratuitos primeiro, pagos só como último recurso.

---

## Pré-requisitos

**Todos os modos**
- Conta na [OpenRouter](https://openrouter.ai) com créditos (modelos gratuitos disponíveis)

**Modo stdio** (Claude Code, Claude Desktop, Cursor…)
- Python 3.11+

**Modo self-host** (Docker + Cloudflare Tunnel)
- [Docker Engine](https://docs.docker.com/engine/install/)
- Domínio gerenciado no [Cloudflare](https://cloudflare.com) (gratuito)

---

## Instalação

```bash
git clone https://github.com/asafebelo/mcp-prompt-refiner.git
cd mcp-prompt-refiner
chmod +x install.sh
./install.sh
```

> **Windows:** o `install.sh` requer bash e utilitários Unix — não roda diretamente no `cmd.exe` nem no PowerShell. Use o **WSL** (Windows Subsystem for Linux) ou o **Git Bash**. No WSL, clone o repositório dentro do ambiente Linux e execute normalmente:
> ```bash
> chmod +x install.sh && ./install.sh
> ```

O instalador:
1. Cria o `.venv` e instala dependências
2. Cria `config.json` (personalização de modelos) e `.env` (chave da API)
3. Exibe o menu de modos — escolha um ou mais
4. Pede sua chave da [OpenRouter](https://openrouter.ai/keys) e salva em `.env`
5. Configura o ambiente escolhido

> Python 3.13: `PYTHON_BIN=python3.13 ./install.sh`

---

## Modos de conexão

### Claude Code

Execute o instalador e escolha **opção 1**. O servidor é registrado globalmente (`--scope user`) — disponível em todos os seus projetos sem precisar registrar novamente.

Após instalar, reinicie o Claude Code. Verifique com:

```bash
claude mcp list
```

**Registro manual** (sem o instalador):

```bash
claude mcp add --scope user mcp-prompt-refiner \
  /caminho/para/.venv/bin/python \
  /caminho/para/server.py
```

**Solução de problemas**
- Servidor não aparece: verifique `claude mcp list` e confirme que o caminho do `.venv` está correto
- `module not found`: rode `.venv/bin/pip install -r requirements.txt`

---

### Claude Desktop

Execute o instalador e escolha **opção 2**. O script detecta o sistema (WSL, macOS ou Linux) e exibe o bloco JSON correto — pronto para copiar.

Cole o bloco no arquivo de configuração do Claude Desktop:

| Sistema | Caminho |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | `~/.config/Claude/claude_desktop_config.json` |

> **Windows:** o caminho inclui um ID gerado automaticamente, difícil de localizar manualmente. Use o atalho nativo: abra o Claude Desktop → **Configurações → Desenvolvedor → Editar Config** — o arquivo `claude_desktop_config.json` abrirá direto no seu editor padrão.

> Se o arquivo já existir com outros servidores, adicione apenas a chave `"mcp-prompt-refiner"` dentro de `"mcpServers"` — não substitua o arquivo inteiro.

**Formato gerado pelo instalador (Windows / WSL):**

```json
{
  "mcpServers": {
    "mcp-prompt-refiner": {
      "command": "wsl",
      "args": ["/caminho/wsl/.venv/bin/python", "/caminho/wsl/server.py"]
    }
  }
}
```

**macOS / Linux nativo:**

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

Encerre o Claude Desktop completamente antes de reabrir (**não apenas minimize**):
- Windows: bandeja do sistema → **Quit**
- macOS: menu Claude → **Quit Claude**

**Solução de problemas**
- MCP não aparece em Configurações → Conectores: o processo não foi encerrado completamente — use o Gerenciador de Tarefas (Windows) ou `killall Claude` (macOS)
- Erro de caminho no Windows: confirme que os `args` usam caminho WSL (começa com `/`), não caminho Windows (`C:\`)

---

### Cursor / Zed / Windsurf

Adicione nas configurações de MCP do editor (geralmente `mcp.json` ou nas preferências):

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

### Docker + Cloudflare Named Tunnel

Use esta opção para expor o servidor publicamente. Necessário para Claude Web, ChatGPT e Codex CLI. Também funciona para Claude Code e Claude Desktop via URL, sem instalação local do Python.

**1. Crie o Named Tunnel no Cloudflare**

1. Acesse [one.dash.cloudflare.com](https://one.dash.cloudflare.com) → **Zero Trust → Networks → Tunnels**
2. Clique em **Create a tunnel** → escolha **Cloudflared**
3. Dê um nome (ex: `mcp-refiner`) e clique em **Save tunnel**
4. Copie o **token** exibido na tela de instalação
5. Na aba **Public Hostname**, configure o endereço público:
   - **Subdomain:** ex `mcp` (resultará em `mcp.seudominio.com`)
   - **Domain:** seu domínio
6. Na aba **Service**, configure o destino interno:
   - **Type:** `HTTP`
   - **URL:** `mcp-server:8000`

> **Por que HTTP e não HTTPS aqui?** O Cloudflare termina o TLS no edge — a URL pública (`mcp.seudominio.com`) é sempre HTTPS para quem acessa. O campo **Service** é a perna *interna*: o `cloudflared` fala com o `mcp-server` dentro da rede privada Docker, onde não há certificado TLS. Usar `https://` aqui causa erro de handshake porque o servidor fala HTTP puro. Não há perda de segurança: o tráfego externo já está protegido pelo próprio protocolo do Cloudflare Tunnel.

**2. Suba os containers**

Execute o instalador e escolha **opção 3** — ele pede a chave da OpenRouter e o token do Cloudflare:

```bash
./install.sh  # → opção 3
```

Ou configure manualmente:

```bash
cp .env.example .env
# Preencha OPENROUTER_API_KEY e CLOUDFLARE_TUNNEL_TOKEN
```

```bash
docker compose up -d
```

**3. Verifique**

```bash
docker compose logs -f cloudflared  # aguarde: "Registered tunnel connection"
docker compose logs -f mcp-server   # deve mostrar: "Uvicorn running on..."
```

**Comandos úteis:**

```bash
docker compose logs -f mcp-server   # logs do servidor
docker compose ps                   # estado dos serviços
docker compose down                 # encerrar
docker compose up -d --build        # recriar após atualização
```

Os arquivos `projects/*.md` são montados como volume em `./projects/` — persistem entre restarts.

**4. Conecte os clientes**

Com o tunnel ativo, use `https://mcp.seudominio.com/mcp` em qualquer cliente.

**Claude Web** (plano Pro ou Team)
: [claude.ai](https://claude.ai) → Configurações → Conectores → Adicionar conector → cole a URL

**ChatGPT** (Plus, Pro ou Team)
: Configurações → Conectores → Adicionar servidor MCP → cole a URL

**Claude Code via URL:**
```bash
claude mcp add --scope user --url https://mcp.seudominio.com/mcp mcp-prompt-refiner
```

**Claude Desktop via URL:**
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

**Codex CLI:**
```toml
# ~/.codex/config.toml
[mcp_servers.mcp-prompt-refiner]
url = "https://mcp.seudominio.com/mcp"
```

---

## Hook de auto-save (Claude Code)

Ative para que `save_context` seja chamado automaticamente ao final de cada sessão, sem você precisar pedir.

Adicione ao `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "asyncRewake": true,
            "command": "bash /caminho/para/mcp-prompt-refiner/scripts/auto_save_hook.sh"
          }
        ]
      }
    ]
  }
}
```

Substitua `/caminho/para/mcp-prompt-refiner` pelo caminho real do projeto.

**Como funciona:** ao parar, o Claude Code executa o hook. Se `save_context` ainda não foi chamado na sessão, o hook injeta uma instrução para que o Claude o chame antes de encerrar. Na segunda parada (após salvar), o hook sai silenciosamente, evitando loop.

**CLAUDE.md nos seus projetos:** copie [`templates/CLAUDE.md`](templates/CLAUDE.md) para a raiz de cada projeto que usar o servidor. Substitua `[NOME-DO-PROJETO]` e remova o bloco de instruções. O Claude Code carrega o arquivo automaticamente em cada sessão.

---

## Como usar

### Iniciando um projeto novo

```
use o refine_prompt para: quero adicionar autenticação JWT no meu servidor FastAPI
```

O Claude apresenta o prompt estruturado e pede confirmação antes de executar. Ao finalizar, salve o contexto:

```
salva o contexto do projeto meu-projeto com o que foi feito hoje
```

### Retomando um projeto existente

```
carrega o contexto do projeto meu-projeto antes de continuar
```

O Claude lê o `projects/meu-projeto.md` e retoma de onde parou — sem você precisar reexplicar nada.

### Verificar projetos salvos

```
lista todos os projetos com contexto salvo
```

> O arquivo `projects/{nome}.md` fica dentro da pasta do `mcp-prompt-refiner`, não no seu projeto. É local e não vai ao git.

---

## Referência

### Variáveis de ambiente

| Variável | Padrão | Descrição |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Chave da OpenRouter — fonte única para todos os modos |
| `CLOUDFLARE_TUNNEL_TOKEN` | — | Token do Named Tunnel (deploy Docker) |
| `MCP_PORT` | `8000` | Porta do servidor HTTP |
| `MCP_HOST` | `127.0.0.1` | Host do servidor HTTP (Docker usa `0.0.0.0`) |

### Personalizar modelos

Edite `config.json` (criado pelo instalador a partir de `config.example.json`):

```json
{
  "openrouter": {
    "models": [
      "google/gemini-2.0-flash-001",
      "meta-llama/llama-3.1-8b-instruct:free",
      "anthropic/claude-haiku-4-5"
    ],
    "max_tokens": 2000,
    "temperature": 0.3
  },
  "projects_dir": "projects",
  "default_language": "pt-BR"
}
```

> `config.json` não precisa de `api_key` — a chave é gerenciada pela variável `OPENROUTER_API_KEY` no `.env`.

Consulte os modelos disponíveis em [openrouter.ai/models](https://openrouter.ai/models).

### Cadeia de modelos padrão

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

Se um modelo falhar (rate limit, timeout, resposta vazia), o próximo é tentado automaticamente.

---

## Estrutura do projeto

```
mcp-prompt-refiner/
├── server.py             # Entry point — registra e despacha as tools MCP
├── tools/
│   ├── refine.py         # refine_prompt: monta o system prompt e chama a LLM
│   ├── context.py        # save_context, load_context, list_projects
│   └── openrouter.py     # Cliente OpenRouter com cadeia de modelos
├── projects/             # Um .md por projeto (local, não vai ao git)
├── scripts/
│   └── auto_save_hook.sh # Stop hook do Claude Code para auto-save de contexto
├── templates/
│   └── CLAUDE.md         # Template para copiar aos seus projetos
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config.example.json
├── install.sh
└── CLAUDE.md             # Instrui o Claude Code a usar as ferramentas
```

---

## Segurança

- A chave da OpenRouter fica no `.env` — nunca vai ao repositório
- `config.json` e `projects/*.md` estão no `.gitignore`
- No modo Docker: rate limiting por IP, bind em `0.0.0.0` acessível só via Cloudflare Named Tunnel

---

## Licença

MIT
