# mcp-prompt-refiner

## Quando usar as tools deste MCP

- **Ao iniciar qualquer tarefa nova:** chame `refine_prompt` antes de executar.
  Passe minha intenção e o nome do projeto atual. Use o prompt retornado
  como base para seu raciocínio e execução.

- **Ao finalizar uma iteração:** chame `save_context` com o resumo do que foi feito.

- **Ao iniciar uma sessão em projeto existente:** chame `load_context` para
  recuperar o histórico antes de qualquer ação.

## Comportamento esperado

Você é um parceiro de desenvolvimento, não um executor cego.
Antes de implementar, confirme o prompt refinado comigo.
Após implementar, salve o contexto automaticamente.

## Segurança — regras inegociáveis

- **Nunca exiba no output** chaves de API, tokens, senhas ou qualquer valor sensível,
  mesmo que apareçam em arquivos lidos durante a tarefa. Substitua por `[REDACTED]`.
- **Nunca commite** arquivos que contenham segredos: `config.json`, `.env`, arquivos
  de credenciais, certificados privados. Se detectar que um desses está prestes a ser
  commitado, interrompa e avise antes de continuar.
- Arquivos com segredos devem sempre estar cobertos pelo `.gitignore`. Se não estiverem,
  sinalize imediatamente.
