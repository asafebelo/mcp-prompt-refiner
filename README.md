# mcp-prompt-refiner

Servidor MCP (Model Context Protocol) em Python 3.13 que atua como camada
intermediária entre sua intenção em linguagem natural e o Claude Code.

Ele chama uma LLM leve via OpenRouter para transformar intenções cruas em
prompts estruturados, e mantém contexto persistente por projeto em arquivos
Markdown locais.

---

## Por que usar

- **Economia de tokens no Claude:** o Claude recebe um prompt já bem
  estruturado, gastando seu raciocínio em executar, não em entender.
- **Contexto persistente sem banco:** cada projeto vira um `.md` em
  `projects/`, fácil de versionar e auditar.
- **Sem dependências pesadas:** só `mcp` e `openai`. Nada de SQLite,
  webserver, ou frontend.

---

## Ferramentas expostas

| Ferramenta | O que faz |
|---|---|
| `refine_prompt` | Recebe uma intenção crua + nome do projeto; devolve prompt estruturado gerado pela LLM leve. |
| `save_context` | Persiste estado do projeto após uma iteração em `projects/{nome}.md`. |
| `load_context` | Devolve o `.md` completo do projeto, para injetar no início de uma sessão. |
| `list_projects` | Lista os projetos que já têm contexto salvo. |

---

## Instalação

```bash
git clone <este-repo> mcp-prompt-refiner
cd mcp-prompt-refiner
./install.sh
```

O script `install.sh`:

1. Cria um virtualenv em `.venv/`
2. Instala `mcp` e `openai`
3. Copia `config.example.json` para `config.json` se ainda não existir
4. Tenta detectar **Claude Code** ou **Claude Desktop** e registra o MCP
5. Imprime instruções finais

---

## Configuração

Edite `config.json` e coloque sua chave da OpenRouter:

```json
{
  "openrouter": {
    "api_key": "sk-or-v1-...",
    "model": "google/gemini-2.0-flash-001",
    "fallback_model": "anthropic/claude-haiku-4-5",
    "max_tokens": 2000,
    "temperature": 0.3
  },
  "projects_dir": "projects",
  "default_language": "pt-BR"
}
```

Obtenha uma chave em https://openrouter.ai/keys.

### Trocar o modelo refinador

Qualquer modelo disponível no OpenRouter funciona. Sugestões leves/baratas:

- `google/gemini-2.0-flash-001`
- `anthropic/claude-haiku-4-5`
- `openai/gpt-4o-mini`
- `mistralai/mistral-small-latest`

---

## Uso no Claude Code

Depois de instalar e configurar, abra o Claude Code em qualquer projeto. As
ferramentas aparecem automaticamente.

Fluxo recomendado:

1. **Iniciando uma sessão:** peça ao Claude para chamar `load_context`
   passando o nome do projeto.
2. **Antes de qualquer tarefa nova:** peça `refine_prompt` com sua intenção
   crua e o nome do projeto.
3. **Ao finalizar:** peça `save_context` com o que foi feito.

O arquivo `CLAUDE.md` na raiz deste repo já instrui o Claude Code a seguir
esse fluxo automaticamente.

---

## Estrutura

```
mcp-prompt-refiner/
├── server.py             # Entry point — registra e despacha as tools
├── tools/
│   ├── __init__.py
│   ├── refine.py         # refine_prompt
│   ├── context.py        # save_context, load_context, list_projects
│   └── openrouter.py     # Cliente OpenRouter
├── projects/             # Um .md por projeto (criado em runtime)
├── config.json           # Sua configuração (com a chave)
├── config.example.json   # Template — não contém chave
├── requirements.txt
├── install.sh
├── CLAUDE.md             # Instruções de comportamento para o Claude
└── README.md
```

---

## Teste rápido

Após `./install.sh` e configurar `config.json`:

```bash
source .venv/bin/activate
python server.py
```

O processo fica aguardando JSON-RPC pelo stdin (esse é o protocolo MCP).
Feche com `Ctrl+C` — o objetivo aqui é só confirmar que o servidor sobe sem
erro. O uso real é via Claude Code / Claude Desktop.

---

## Notas

- Logs vão para `stderr` — `stdout` é reservado para o canal MCP.
- Se a chamada ao modelo primário falhar, o cliente tenta `fallback_model`
  automaticamente.
- Sem banco de dados. Sem servidor web. Sem frontend.
