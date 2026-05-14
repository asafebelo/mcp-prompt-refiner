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
1. `google/gemini-2.0-flash-001`
2. `google/gemini-flash-1.5-8b`
3. `meta-llama/llama-3.1-8b-instruct`
4. `anthropic/claude-haiku-4-5` ← último recurso

Se o primeiro modelo falhar (rate limit, timeout, resposta vazia), o próximo da lista é tentado automaticamente. Haiku entra apenas se todos os outros falharem.

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

3. O Claude lê o `.md` e retoma de onde parou — sem você precisar reexplicar nada

### Verificar todos os projetos salvos

> "lista todos os projetos com contexto salvo"

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
