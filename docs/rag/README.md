# Base RAG modular do Midas

Esta pasta é a fonte de contexto para LLMs que trabalham no Midas. Ela substitui o carregamento indiscriminado do repositório por módulos curtos, independentes e roteáveis.

## Fluxo obrigatório de recuperação

1. Carregue primeiro `00-router.md`.
2. Classifique a intenção do pedido do usuário.
3. Carregue somente o módulo ou os módulos indicados pelo roteador.
4. Abra os arquivos de código citados pelo módulo apenas quando a tarefa exigir confirmação ou alteração de implementação.
5. Para mudanças que cruzem domínios, carregue os módulos envolvidos, mas não módulos adjacentes por precaução.
6. Ao descobrir uma regra estável que falta aqui, atualize o módulo dono dela junto com a implementação.

Integrações programáticas podem usar `rag-manifest.json` para filtrar módulos por palavras-chave e localizar os pontos de código proprietários.

## Propriedade dos módulos

| Módulo | Dono conceitual | Carregar quando |
|---|---|---|
| `00-router.md` | Roteamento | Sempre, primeiro |
| `01-product.md` | Visão e limites do produto | Escopo, UX geral, linguagem de investimento |
| `02-market-data.md` | Ativos, cotações, provedores e importação | Dados de mercado, Yahoo, brapi, atualização |
| `03-portfolio.md` | Carteira, posições e proventos | Posições, compras, vendas, dividendos |
| `04-quant-research.md` | Dataset, fatores, treino, ranking e validação | Modelo, sinais, backtest, métricas |
| `05-web-ui.md` | Interface React e experiência de uso | Páginas, componentes, estilos, acessibilidade |
| `06-api-jobs.md` | HTTP, contratos e tarefas assíncronas | Rotas, payloads, jobs, erros |
| `07-storage-security.md` | Bancos, persistência, autenticação e segurança | PostgreSQL, MongoDB, usuários, dados sensíveis |
| `08-roadmap.md` | Decisões e ordem de evolução | Planejamento e priorização |
| `09-quality.md` | Testes, observabilidade e critérios de aceite | Verificação, bugs e confiabilidade |
| `10-codebase-catalog.md` | Inventário completo | Localizar arquivos e recursos auxiliares |

## Regras de economia de tokens

- Não carregar `product-rag-context.md` como contexto padrão; ele é uma visão ampla de referência.
- Não ler código por varredura. Usar primeiro os caminhos de código listados no módulo relevante.
- Não anexar logs, arquivos de lock, `.env`, `node_modules` ou o histórico inteiro do Git ao contexto.
- Resumir resultados de arquivos longos antes de seguir para outro domínio.
- Em tarefas repetidas no mesmo domínio, reutilizar o resumo de trabalho já obtido em vez de recuperar o módulo novamente.
- Quando a pergunta for conceitual, responder usando o módulo; abrir código somente para confirmar comportamento atual.

## Manutenção

Os módulos descrevem fatos estáveis, contratos e pontos de entrada — não devem copiar código extenso. Cada módulo deve caber em um contexto pequeno e apontar para seus arquivos proprietários.

## Índice persistente opcional

O serviço Docker `rag-postgres` mantém um índice PostgreSQL com pgvector. Ele armazena chunks, metadados, busca textual em português e embeddings. A documentação em `docs/rag/` continua sendo a fonte de verdade; o banco pode ser apagado e reindexado sem perda de conhecimento de produto.

Use a busca textual e o filtro por módulo antes da similaridade vetorial. Como a dimensão do embedding depende do modelo escolhido, o schema não cria um índice vetorial até que esse modelo seja definido.

Para indexar os documentos-fonte no banco, use `python scripts/index_rag.py` depois de iniciar `rag-postgres`. O comando lê exclusivamente `docs/rag/*.md`, remove apenas chunks anteriormente indexados desse mesmo diretório e recria o índice textual. Use `python scripts/index_rag.py --check` para validar os chunks sem conexão ao banco.
