# Módulo: carteira e proventos

## Responsabilidade

Gerenciar ativos acompanhados, quantidades, posições, operações e proventos do usuário.

## Estado atual

- A carteira padrão é persistida no PostgreSQL com o nome `Minha Carteira`.
- A quantidade é editável, mas não existe histórico de compra/venda, preço médio ou custo.
- Dividendos são consultados no Yahoo Finance durante a requisição e a simulação de reinvestimento considera apenas cotas inteiras.
- A lista é perdida quando a aplicação reinicia.

## Persistência

O schema contém `portfolios` e `portfolio_assets`, com uma carteira nomeada e quantidades positivas por ativo. `PostgresRepository` oferece leitura, upsert e remoção dessas posições. A migração idempotente é `infra/postgres/migrations/001-persistent-portfolio.sql`; as rotas de carteira, dividendos, relatório e o filtro de treino usam esse repositório como fonte de verdade.

## Fluxo confirmado

- Adição recebe ticker e quantidade, importa cinco anos de preços Yahoo e só então cria/atualiza a posição persistida.
- Se a importação falhar, a posição não é criada ou alterada e a rota devolve erro; uma falha não pode ser apresentada como sucesso.
- O relatório de carteira filtra o ranking completo pelos tickers; tickers ainda sem dados aparecem como ativo sintético com status de ausência de dados.
- O treino iniciado pela carteira usa somente os tickers persistidos; não usa quantidade, custo ou data de entrada.
- Dividendos multiplicam o valor anual de 12 meses pela quantidade atual e estimam reinvestimento por `floor(total_dividendos / preço_atual)`.

## Não confundir

- “Ativo na carteira” atual não é uma posição financeira auditável.
- Reinvestimento exibido é simulação, não uma nova operação real.
- Favoritos são uma watchlist separada da carteira.

## Direção de evolução

Fonte de verdade deve ser uma tabela de operações: compra, venda, dividendos/JCP, aportes, retiradas, taxas e eventos corporativos. Posições, preço médio e P&L devem ser calculados dessas operações.

## Pontos de código

- `midas_core/interfaces/http.py` (`PORTFOLIO_TICKERS` e rotas de carteira)
- `midas_core/application/analysis.py` (`build_portfolio_report`)
- `web/app.js` (`PortfolioPage` e `PortfolioManager`)
- `web/api.js`

## Dados mínimos da posição futura

Quantidade, custo total, preço médio, cotação/data, valor de mercado, resultado realizado/não realizado, proventos brutos/líquidos e peso na carteira.
