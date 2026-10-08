# Módulo: catálogo integral do código

## Finalidade e escopo da primeira rodada

Este catálogo registra todos os arquivos relevantes de código, configuração, infraestrutura, documentação e teste presentes na primeira auditoria. Ele é um mapa de recuperação: descreve responsabilidades e vínculos, mas não replica o código-fonte. Arquivos excluídos do RAG: `.env`, `.git`, `.venv`, `node_modules`, caches, bancos, builds e lockfile.

## Entradas e compatibilidade

| Arquivo | Papel |
|---|---|
| `midas.py` | Inicializa o servidor HTTP por `run_server`. |
| `market_api.py` | Fachada CLI para importação brapi. |
| `yahoo_api.py` | Fachada CLI para importação Yahoo. |
| `dataset.py` | Fachada CLI para publicar dataset e treinar. |
| `training.py` | Exporta API compatível de treino e executa CLI. |
| `features.py` | Reexporta funções de features do domínio. |
| `storage.py` | Fachada de repositórios/conexões legadas. |
| `train_xgboost.py` | Script experimental de treino; ainda persiste artefato no formato linear e não é fluxo de produção confiável para modelo de árvore. |

## Núcleo de domínio

| Arquivo | Papel |
|---|---|
| `midas_core/domain/entities.py` | Dataclasses imutáveis `PricePoint` e `ImportedStock`. |
| `midas_core/domain/features.py` | Série mensal, fatores de preço/fundamentos e criação de amostras para horizontes 6/12/24/36. Inclui indicadores auxiliares não usados no vetor atual (ADX, estocástico, Williams, OBV e MFI). |
| `midas_core/domain/regression.py` | Ridge NumPy, normalização, predição, MAE, acerto direcional, ranking Spearman e particionamento temporal. |
| `midas_core/domain/portfolio.py` | Livro razão puro: `Operation`, `calculate_position` (custo médio), `PositionSummary` e `total_pnl`. |
| `midas_core/domain/__init__.py` | Marcador de pacote. |

## Treinamento e casos de uso

| Arquivo | Papel |
|---|---|
| `midas_core/training/variables.py` | Seleciona candidatos Ridge/Lasso/ElasticNet/Huber e, quando bibliotecas estão instaladas, árvores e redes. Avalia por MAE temporal, mede teste final e produz métricas/quantis. |
| `midas_core/training/__init__.py` | Expõe `VariableTrainer` e configuração. |
| `midas_core/application/datasets.py` | Lê preços por fonte, busca fundamentos históricos, cria e publica snapshots MongoDB. |
| `midas_core/application/training.py` | Carrega amostras, treina, salva artefato MongoDB e run PostgreSQL com compensação simples. |
| `midas_core/application/analysis.py` | Gera ranking, busca o artefato mais recente utilizável, calcula oportunidade e relatório de carteira. |
| `midas_core/application/portfolio_ledger.py` | Caso de uso do livro de operações: payload, CRUD com revalidação e resumo de posição/P&L. |
| `midas_core/application/jobs.py` | Jobs persistidos: enfileirar, consultar, cancelar, retry e `JobWorker`. |
| `midas_core/application/market_quality.py` | Relatório de proveniência e frescor dos preços. |
| `midas_core/domain/jobs.py` | Estados, transições e erro seguro de jobs. |
| `midas_core/domain/market_quality.py` | Política de fontes, frescor e outcome de coleta. |
| `midas_core/domain/model_artifacts.py` | Contrato versionado de artefatos e explicação de fatores. |
| `midas_core/worker.py` | Entrypoint do worker dedicado de jobs. |
| `midas_core/application/market_import.py` | Importador brapi com validação, parsing e persistência. |
| `midas_core/application/market_import_yahoo.py` | Importador Yahoo tolerante a falhas parciais. |
| `midas_core/application/__init__.py` | Marcador de pacote. |

## Infraestrutura de dados externos

| Arquivo | Papel |
|---|---|
| `midas_core/infrastructure/brapi.py` | Cliente HTTP brapi v2, ticker seguro, retries de rede/429 e token Bearer. |
| `midas_core/infrastructure/yahoo.py` | Histórico, dividendos e fundamentos Yahoo (`fetch_fundamentals` pontual e `fetch_historical_fundamentals`). |
| `midas_core/infrastructure/enrichment.py` | Enriquecimento experimental com Yahoo, brapi e Alpha Vantage; mescla por data e preço. Chama `fetch_fundamentals` inexistente somente dentro de bloco protegido, portanto cai em fallback de nome. |
| `midas_core/infrastructure/macro.py` | Consulta séries BCB (Selic, IPCA, dólar e desemprego) com cache local de 24h; as features macro não estão ligadas ao vetor atual. |
| `midas_core/infrastructure/database.py` | Fábricas psycopg e MongoClient. |
| `midas_core/infrastructure/repositories.py` | Repositórios PostgreSQL/MongoDB e regras de persistência. |
| `midas_core/infrastructure/__init__.py` | Marcador de pacote. |
| `midas_core/config.py` | Lê `.env` e produz `Settings` para bancos, HTTP e token brapi. |

## Interfaces e operação

| Arquivo | Papel |
|---|---|
| `midas_core/interfaces/http.py` | Servidor HTTP, API JSON, job de treino em thread e carteira em memória. |
| `midas_core/interfaces/cli.py` | Parsers CLI de importação, dataset e treino. |
| `midas_core/interfaces/__init__.py` | Marcador de pacote. |
| `scripts/setup_env.py` | Gera credenciais ausentes sem revelar valores. |
| `scripts/set_brapi_token.py` | Atualiza token brapi no `.env` sem imprimi-lo. |
| `scripts/check_databases.py` | Healthcheck de leitura/escrita dos bancos operacionais via Docker. |
| `scripts/enrich_data.py` | Lê universo e persiste dados enriquecidos sob fonte `enriched`. |
| `scripts/index_rag.py` | Divide `docs/rag/*.md` por títulos e indexa chunks no `rag-postgres`; não gera embeddings. |

## Interface web e entrega

| Arquivo | Papel |
|---|---|
| `web/index.html` | Shell HTML e entrada do app. |
| `web/react.js` | Adaptador de imports React. |
| `web/app.js` | Estado principal, carregamento paralelo, páginas e ações de carteira/treino. |
| `web/OperationsLedger.js` | Formulário de operações, histórico e resumo de posição na carteira. |
| `web/api.js` | Cliente fetch e contratos das rotas HTTP. |
| `web/layout.js` | Sidebar e navegação local. |
| `web/AssetExplorer.js` | Filtros, tabela de ativos e favoritos. |
| `web/TrainingConsole.js` | Disparo e polling de treino. |
| `web/EvaluationPanel.js` | Métricas e explicação do método. |
| `web/ValidationHistory.js` | Tabela de previsões de teste. |
| `web/ui.js` | Primitivas de título, cartão e tabela. |
| `web/Sparkline.js` | Gráfico SVG compacto de fechamento. |
| `web/format.js` | Formatação pt-BR e categorias. |
| `web/style.css` | Tema, responsividade e estilos das páginas. |
| `vite.config.js` | Proxy `/api` para o serviço dev. |
| `package.json` | Vite/React e verificações sintáticas. |
| `Dockerfile` | Build frontend, imagem base Python/Node, alvo dev e imagem de produção. |
| `compose.yaml` | Serviços app/dev/ui/PostgreSQL/MongoDB/rag-postgres, volumes e healthchecks. |

## Persistência e configuração

| Arquivo | Papel |
|---|---|
| `infra/postgres/01-init.sh` | Roles, tabelas e privilégios do PostgreSQL operacional. |
| `infra/postgres/migrations/001-persistent-portfolio.sql` | Tabelas `portfolios` e `portfolio_assets`. |
| `infra/postgres/migrations/002-portfolio-operations.sql` | Tabela `portfolio_operations` e invariantes do livro razão. |
| `infra/postgres/migrations/003-jobs.sql` | Tabela `jobs` e índice de treino único ativo. |
| `scripts/migrate_postgres.py` | Aplica migrations em ordem via Docker. |
| `infra/mongo/01-init.js` | Usuário, coleções, validadores e índices MongoDB. |
| `infra/rag-postgres/01-init.sql` | Extensão pgvector e tabela/índices `rag_chunks`. |
| `config/stock-universe.txt` | Universo manual de 34 tickers B3 para importação. |
| `config/my-portfolio.txt` | Arquivo informativo de carteira; não é carregado pela implementação atual. |
| `requirements.txt` | Dependências Python: NumPy, bancos, dotenv, scikit-learn, yfinance, XGBoost, LightGBM e TensorFlow. |

## Testes e documentação

| Arquivo | Papel |
|---|---|
| `test_analysis.py` | Ranking, validação do artefato, ordenação e relatório. |
| `test_http.py` | Rotas, payloads, erros, origem e estado de treino. |
| `test_market_api.py` | Normalização, importação brapi e contrato HTTP. |
| `test_midas.py` | Expurgo temporal, fatores sem futuro, correlação e treinador. |
| `test_portfolio.py` | Cálculo de posição, P&L e rejeição de venda descoberta. |
| `test_portfolio_ledger.py` | Caso de uso do livro, edição/exclusão controladas e resumo. |
| `test_jobs.py` | Transições, worker, retry e recuperação de jobs. |
| `test_market_quality.py` | Fontes, frescor, coleta parcial e fundamentos Yahoo. |
| `test_model_artifacts.py` | Serialização, ensemble e bloqueio de run não serializável. |
| `README.md` | Instalação, importação, treino, avisos de risco e comandos. |
| `docs/architecture.md` | Camadas, fluxos e regras arquiteturais. |
| `docs/data-model.md` | Modelo lógico, invariantes e ligação entre bancos. |
| `docs/databases.md` | Operação dos bancos e persistência. |
| `docs/training-validation.md` | Validação temporal e limites metodológicos. |

## Achados transversais da auditoria

- Documentação histórica menciona apenas horizontes 12/24/36 em alguns trechos, mas código/schema aceitam 6 meses; usar o código como referência operacional atual.
- A arquitetura declarada é em camadas; a carteira e o livro de operações usam repositório/caso de uso, mas jobs ainda vivem na interface HTTP em memória.
- Há recursos experimentais/sem integração plena: macroeconomia, Alpha Vantage, indicadores auxiliares e modelos de árvore/rede.
- O RAG indexa resumos modulares e o catálogo, não arquivos-fonte brutos; esse é o mecanismo deliberado para reduzir contexto e tokens.
