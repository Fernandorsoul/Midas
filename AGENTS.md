# Instruções para agentes — Midas

## Regra central: RAG antes de código

Antes de pesquisar, explicar, planejar ou alterar qualquer parte do Midas, leia `docs/rag/00-router.md`. Use o roteador para identificar o domínio da tarefa e recupere somente os módulos necessários em `docs/rag/`.

**É proibido ler o repositório inteiro, varrer todos os arquivos de código ou carregar `docs/product-rag-context.md` por padrão.** O contexto amplo só deve ser aberto quando a tarefa realmente cruzar vários domínios e os módulos específicos não forem suficientes.

Fluxo obrigatório:

1. Ler `docs/rag/00-router.md`.
2. Selecionar no máximo dois módulos de domínio inicialmente.
3. Ler os módulos selecionados por completo.
4. Abrir apenas os arquivos de código apontados por esses módulos e necessários à tarefa.
5. Recuperar outro módulo apenas quando houver dependência explícita descoberta durante o trabalho.
6. Antes de encerrar, salvar conhecimento estável novo ou corrigido no módulo dono da informação.

## Mapa de módulos

| Domínio | Documento RAG | Responsabilidade |
|---|---|---|
| Produto | `docs/rag/01-product.md` | Propósito, limites e linguagem de investimento |
| Dados de mercado | `docs/rag/02-market-data.md` | Ativos, preços, fontes e importação |
| Carteira | `docs/rag/03-portfolio.md` | Posições, operações e proventos |
| Pesquisa quantitativa | `docs/rag/04-quant-research.md` | Dataset, modelo, ranking e validação |
| Interface | `docs/rag/05-web-ui.md` | Componentes, navegação, UX e acessibilidade |
| API e jobs | `docs/rag/06-api-jobs.md` | Rotas, contratos, tarefas e erros |
| Persistência e segurança | `docs/rag/07-storage-security.md` | Bancos, segredos, usuários e acesso |
| Roadmap | `docs/rag/08-roadmap.md` | Prioridades e fases de evolução |
| Qualidade | `docs/rag/09-quality.md` | Testes, critérios de aceite e confiabilidade |

Use `docs/rag/rag-manifest.json` para integrações programáticas de recuperação. Ele contém palavras-chave e pontos de código proprietários de cada módulo.

## Separação modular obrigatória

- Cada mudança deve ter um módulo de negócio dono.
- Não misture regras de negócio na interface nem detalhes de HTTP no domínio.
- Uma mudança transversal deve declarar seus módulos afetados antes de editar.
- Ao criar uma nova área de produto, criar um módulo RAG dedicado (`NN-nome.md`), registrar no roteador, no `README.md` e no `rag-manifest.json`.
- Módulos RAG devem conter fatos estáveis, contratos, decisões, limitações e caminhos de entrada; não devem duplicar grandes trechos de código.
- Cada módulo deve ser pequeno o suficiente para ser recuperado integralmente como contexto de uma única tarefa.

## Atualização e indexação do RAG

Após qualquer alteração material, atualizar o módulo proprietário quando ela modificar:

- comportamento de produto;
- contrato de API;
- schema ou persistência;
- fonte/qualidade de dados;
- regras de modelo ou validação;
- fluxos de interface;
- regra de segurança;
- prioridade de roadmap;
- critérios de teste ou aceite.

Ao usar o índice `rag-postgres`, indexar somente documentos RAG alterados ou novos. Nunca indexar automaticamente:

- `.env`, credenciais, tokens ou dados pessoais;
- `node_modules`, lockfiles, builds ou caches;
- dumps de banco, logs brutos ou artefatos temporários;
- o repositório inteiro sem filtro explícito.

O conteúdo em `docs/rag/` é a fonte de verdade. O banco RAG é um índice reconstruível e não substitui os arquivos Markdown.

Depois de alterar documentos em `docs/rag/`, executar `python scripts/index_rag.py` quando o serviço `rag-postgres` estiver disponível. O indexador só processa documentos RAG e não envia conteúdo a serviços externos.

## Estratégia de recuperação eficiente

1. Aplicar filtro por módulo a partir do roteador.
2. Usar busca textual/palavras-chave para nomes de rotas, tabelas, símbolos e arquivos.
3. Usar busca vetorial somente para perguntas conceituais ou linguagem natural ambígua.
4. Recuperar de 1 a 3 chunks por padrão; justificar qualquer recuperação acima de 5 chunks.
5. Preferir resumos de trabalho já obtidos na tarefa a recuperar o mesmo conteúdo novamente.
6. Confirmar no código somente o fato necessário; não abrir arquivos vizinhos por hábito.

## Regras de produto e comunicação

- Midas é uma ferramenta de pesquisa e acompanhamento de investimentos, não uma corretora.
- Não apresentar ranking, previsão ou sinal como recomendação individual de compra/venda ou garantia de retorno.
- Ao tratar dados de mercado, informar fonte, data de referência e limitações quando disponíveis.
- Ao tratar o modelo, informar horizonte, métricas de validação e incerteza.
- Não expor segredos em respostas, logs, documentação ou índice RAG.

## Checklist de encerramento

Antes de finalizar uma tarefa, confirmar:

- [ ] O roteador e os módulos corretos foram usados antes de abrir código.
- [ ] Apenas o contexto necessário foi recuperado.
- [ ] Os módulos RAG afetados foram atualizados.
- [ ] O manifesto foi atualizado se um módulo foi criado, removido ou renomeado.
- [ ] Nenhum segredo ou arquivo excluído foi incluído no RAG.
- [ ] Testes relevantes foram executados ou a limitação foi declarada.
