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

## Cobertura patrimonial

- `test_wealth.py` cobre TWR sem distorção de aporte, XIRR, alocação, rebase de benchmarks e reconciliação do dashboard.

## Cobertura de artefatos de modelo

- `test_model_artifacts.py` cobre round-trip ridge/ensemble, rejeição de modelo não serializável, semântica de ensemble (2+ membros), explicação de fatores e bloqueio de publicação do run.

## Cobertura de autenticação e isolamento

- `test_auth.py` cobre hash de senha, tokens de sessão, `assert_owner` (nega acesso a outro usuário e recurso sem dono), login/logout e export/exclusão sem hashes.
- `test_http.py` cobre 401 em rotas privadas e contratos de auth.

## Cobertura de migrações e CI

- `test_migrations.py` cobre checksum, detecção de drift e presença dos scripts de check/RAG/CI.
- `scripts/check_quality.py` executa JS + testes + healthcheck em um comando.
- `scripts/validate_rag.py` valida manifesto/RAG.
- CI (`.github/workflows/ci.yml`) roda checks e migrações idempotentes em PR/push.

## Cobertura de recuperação RAG

- `test_rag.py` cobre embedding `local-hash-256`, similaridade, score híbrido, limite de 3 chunks com fonte e filtro por módulo.

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
- `test_wealth.py`
- `test_model_artifacts.py`
- `test_auth.py`
- `test_migrations.py`
- `test_rag.py`
