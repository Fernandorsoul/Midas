# Módulo: carteira e proventos

## Responsabilidade

Gerenciar ativos acompanhados, quantidades, posições, operações e proventos do usuário.

## Estado atual

- A carteira padrão `Minha Carteira` é persistida em PostgreSQL (`portfolios` e `portfolio_assets`).
- Existe livro razão auditável em `portfolio_operations` com compra, venda, aporte, retirada, dividendo, JCP, taxa e imposto.
- Posição, custo médio, P&L realizado/não realizado e retorno total são calculados das operações pelo domínio.
- A lista simples de tickers/quantidades (`portfolio_assets`) continua sendo a fonte do filtro de treino e dos dividendos simulados.

## Persistência

- `portfolios` e `portfolio_assets` mantêm a lista de ativos e quantidade.
- `portfolio_operations` é a fonte de verdade do livro financeiro. Migrações idempotentes: `001-persistent-portfolio.sql` e `002-portfolio-operations.sql`.
- `PostgresRepository` oferece CRUD de operações (`list_portfolio_operations`, `insert_portfolio_operation`, `update_portfolio_operation`, `delete_portfolio_operation`) e `latest_price` para P&L a mercado.

## Regras de domínio confirmadas

- Cálculo por custo médio móvel em ordem cronológica (`midas_core/domain/portfolio.py`).
- Compra soma `quantity * unit_price + fees + taxes` ao custo.
- Venda parcial realiza P&L com preço médio da data; venda acima da posição é rejeitada (sem venda descoberta).
- Dividendos/JCP são renda líquida de impostos; taxas/impostos avulsos são despesa e não alteram o custo dos ativos mantidos.
- Aportes e retiradas afetam o fluxo de caixa, não a quantidade.
- Operações da mesma posição devem usar a mesma moeda (padrão `BRL`).
- `total_pnl = realizado + não realizado + renda - despesas avulsas`.
- Edição e exclusão são controladas: o livro restante é revalidado antes de persistir.

## Fluxo confirmado

- Lançamento de operação valida payload, regras de tipo/ticker/valor e o livro resultante antes do insert.
- Edição exige tipo e data; se o ticker mudar, revalida o livro do ativo anterior e do novo.
- Consulta de posição devolve quantidade, custo, preço médio, mercado (com data/fonte), realizado, não realizado, renda, despesas, fluxo de caixa e retorno total por ativo e no agregado.
- Histórico é ordenado por data e id.

## Não confundir

- “Ativo na carteira” (`portfolio_assets`) não substitui o livro de operações.
- Reinvestimento exibido em dividendos é simulação, não operação real.
- Favoritos são uma watchlist separada da carteira.
- Ranking/estimativa do modelo não é recomendação de compra/venda.

## Pontos de código

- `midas_core/domain/portfolio.py` (`Operation`, `calculate_position`, `PositionSummary.total_pnl`)
- `midas_core/application/portfolio_ledger.py` (payload, CRUD validado, `position_summary`)
- `midas_core/infrastructure/repositories.py` (operações e `latest_price`)
- `midas_core/interfaces/http.py` (rotas de operações/posições)
- `web/OperationsLedger.js` (formulário, histórico e resumo)
- `web/app.js` (`PortfolioPage` e `PortfolioManager`)

## Dados mínimos da posição

Quantidade, custo total, preço médio, cotação/data/fonte, valor de mercado, resultado realizado/não realizado, proventos, despesas, fluxo de caixa, retorno total e moeda.

## Dashboard patrimonial

- `GET /api/wealth/dashboard` (`midas_core/application/wealth_dashboard.py`, `midas_core/domain/wealth.py`).
- **TWR** é o retorno da estratégia (aportes/retiradas isolados); **XIRR** é o retorno pessoal quando há fluxo de caixa.
- Benchmarks: CDI (BCB SGS 12) e Ibovespa (Yahoo `^BVSP`), rebased em 100, com fonte/período/data de atualização.
- Valores consolidados reconciliam com posições e operações; comparação é informativa, não recomendação.
