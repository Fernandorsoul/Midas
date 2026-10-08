# Módulo: qualidade e validação

## Responsabilidade

Testes, critérios de aceite, dados inválidos, observabilidade e regressões.

## Cobertura existente

Há testes de regras de análise, HTTP, importação e treinamento. Endpoints básicos possuem cobertura, incluindo validação de payload e origem em algumas rotas.

## Lacunas prioritárias

- Eventos de dividendos/JCP e data-com.
- Falhas, timeout e lacunas de provedores.
- Importações duplicadas e concorrência.
- Fluxos de interface: carregar, erro, vazio e sucesso.
- Contratos de novas rotas e autorização futura.

## Cobertura do livro de operações

- `test_portfolio.py` cobre compra, venda parcial, taxas, rejeição de venda descoberta, renda/despesa e ordem cronológica.
- `test_portfolio_ledger.py` cobre `total_pnl`, moeda única, payload, lançamento, edição/exclusão controladas e resumo de posição com repositório fake.
- `test_http.py` cobre rotas de operações/posições, validação de `id` e origem.

## Cobertura de jobs

- `test_jobs.py` cobre transições, erro seguro, enfileiramento, unicidade de treino, worker (sucesso/falha/cancelamento), retry e recuperação de running interrompido.
- `test_http.py` cobre rotas de jobs, treino (202/400/409), import enfileirada (202) e status persistido.

## Cobertura de dados de mercado

- `test_market_quality.py` cobre política de fontes/fallback, série consistente, frescor/stale, distinção close vs adjusted_close, outcome de coleta (sucesso/parcial/falha) e disponibilidade de `fetch_fundamentals`.
- `test_market_api.py` cobre normalização, resposta parcial da brapi e persistência de preço ajustado.

## Critérios de aceite transversais

- Não perder dados de usuário ao reiniciar.
- Não exibir cotação sem data/fonte verificável.
- Não mascarar falha como sucesso.
- Não criar sinais de investimento sem modelo validado.
- Não registrar nem expor segredos.
- Toda alteração de regra de negócio deve ter teste automatizado.

## Contratos cobertos para carteira

`test_http.py` isola PostgreSQL e Yahoo com mocks e cobre listagem, adição/importação, remoção, dividendos e relatório usando posições persistidas. A persistência real entre reinícios também deve ser validada no ambiente integrado antes de publicar uma versão.

## Pontos de código

- `test_analysis.py`
- `test_http.py`
- `test_market_api.py`
- `test_midas.py`
- `test_portfolio.py`
- `test_portfolio_ledger.py`
- `test_jobs.py`
- `test_market_quality.py`
