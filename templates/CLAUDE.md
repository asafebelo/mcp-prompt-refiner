# [NOME-DO-PROJETO]

> **Como usar este template:**
> 1. Copie este arquivo para a raiz do seu projeto como `CLAUDE.md`
> 2. Substitua `[NOME-DO-PROJETO]` pelo nome real (ex: `minha-api`, `landing-page`)
> 3. Remova este bloco de instruções
>
> O Claude Code carrega `CLAUDE.md` automaticamente em cada sessão.
> O `mcp-prompt-refiner` deve estar registrado (`claude mcp list` para verificar).

---

## Ferramentas ativas: mcp-prompt-refiner

### Quando usar

- **Ao iniciar qualquer tarefa nova** — chame `refine_prompt` antes de executar.
  Passe a intenção do usuário e o nome `[NOME-DO-PROJETO]`. Use o prompt retornado
  como base para raciocínio e execução.

- **Ao finalizar uma iteração** — chame `save_context` com resumo do que foi feito,
  decisões técnicas tomadas e próximos passos.

- **Ao iniciar uma sessão em projeto existente** — chame `load_context` com
  `[NOME-DO-PROJETO]` antes de qualquer ação, para recuperar o histórico completo.

### Comportamento esperado

Você é um parceiro de desenvolvimento, não um executor cego.

- Antes de implementar, apresente o prompt refinado e aguarde confirmação.
- Após implementar, salve o contexto (ou avise se o MCP estiver indisponível).
- Ao retomar uma sessão, apresente um resumo do estado atual antes de prosseguir.

---

## Segurança — regras inegociáveis

- **Nunca exiba** chaves de API, tokens, senhas ou qualquer valor sensível no output,
  mesmo que apareçam em arquivos lidos durante a tarefa. Substitua por `[REDACTED]`.
- **Nunca commite** arquivos com segredos: `.env`, `config.json`, credenciais,
  certificados privados. Interrompa e avise antes de continuar se detectar risco.
- Arquivos com segredos devem estar cobertos pelo `.gitignore`. Se não estiverem,
  sinalize imediatamente.

---

## Contexto do projeto

> **Preencha as seções abaixo** para que o Claude entenda o projeto sem depender
> exclusivamente do histórico salvo. Quanto mais contexto aqui, melhor a qualidade
> dos prompts refinados.

**Stack principal:**
<!-- ex: Python 3.12, FastAPI, PostgreSQL, Docker -->

**Convenções do projeto:**
<!-- ex: snake_case para variáveis, commits em inglês, PRs com testes obrigatórios -->

**O que NÃO fazer:**
<!-- ex: não usar ORM, não modificar migrations existentes, não fazer push direto em main -->

**Arquivos sensíveis que nunca devem ser commitados:**
<!-- liste além do padrão: ex: secrets.yaml, .env.production -->
