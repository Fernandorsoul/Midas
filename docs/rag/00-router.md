# Roteador de contexto RAG

Leia este arquivo antes de qualquer outro módulo.

## Decisão rápida

| Intenção identificada | Módulo mínimo | Módulos adicionais somente se necessário |
|---|---|---|
| O que o produto faz, limites, tom ou telas gerais | `01-product.md` | `05-web-ui.md` |
| Cotação, ticker, preço, fonte, importação ou atualização | `02-market-data.md` | `06-api-jobs.md`, `07-storage-security.md` |
| Compra, venda, posição, preço médio, P&L ou dividendos | `03-portfolio.md` | `07-storage-security.md`, `05-web-ui.md` |
| Modelo, previsão, candidato, fatores, treino ou validação | `04-quant-research.md` | `02-market-data.md`, `06-api-jobs.md` |
| Página, componente, CSS, filtro, navegação ou mobile | `05-web-ui.md` | módulo de negócio da página |
| Endpoint, JSON, erro HTTP, fila ou status de tarefa | `06-api-jobs.md` | módulo de negócio correspondente |
| Banco, schema, usuário, autenticação, segredo ou acesso | `07-storage-security.md` | módulo afetado |
| Priorização, fase ou plano de produto | `08-roadmap.md` | `01-product.md` |
| Teste, bug, qualidade, monitoramento ou aceite | `09-quality.md` | módulo afetado |
| Localizar arquivo, script auxiliar, wrapper ou componente legado | `10-codebase-catalog.md` | módulo dono |

## Quando carregar vários módulos

- Uma nova funcionalidade de carteira: `03` + `05` + `06` + `07` + `09`.
- Nova fonte de preços: `02` + `06` + `07` + `09`.
- Nova métrica/modelo: `04` + `02` + `06` + `09`.
- Novo dashboard patrimonial: `03` + `05` + `06` + `09`.

## Limite de recuperação

Comece com no máximo dois módulos de domínio, além deste roteador. Recupere outro apenas se a resposta ou a alteração depender explicitamente dele.

## Arquivos que não devem entrar no contexto automaticamente

- `.env` e qualquer segredo;
- `node_modules/`, lockfiles e artefatos gerados;
- bases de dados e dumps;
- todo o código-fonte;
- toda a documentação histórica.
