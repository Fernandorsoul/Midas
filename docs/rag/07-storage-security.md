# Módulo: persistência e segurança

## Responsabilidade

PostgreSQL, MongoDB, segredos, isolamento de dados e controles de acesso.

## Estado atual

- PostgreSQL: ativos, preços, favoritos e execuções de modelo.
- MongoDB: datasets, amostras e artefatos de modelo.
- PostgreSQL com pgvector (`rag-postgres`): índice RAG reconstruível de chunks e embeddings.
- O produto é local/de desenvolvimento e não possui autenticação multiusuário.
- Favoritos usam a watchlist compartilhada chamada `Favoritos`.

## Persistência confirmada

- `assets` contém ticker único, nome, categoria, setor, marca de demo e criação.
- `daily_prices` usa chave primária `(asset_id, price_date, source)` e armazena fechamento, fechamento ajustado, volume e instante de ingestão.
- `model_runs` armazena métricas e parâmetros em JSONB; a ligação com o dataset MongoDB é lógica, não transacional.
- `portfolios` e `portfolio_assets` persistem a lista de ativos e quantidade; a migração `001-persistent-portfolio.sql` é necessária para bancos já existentes.
- MongoDB valida as coleções `datasets`, `training_samples` e `model_artifacts`; amostras têm índice único por dataset, ticker, data e horizonte.
- Ao publicar um dataset, a aplicação tenta compensar uma falha de inserção de amostras removendo dataset e amostras do MongoDB. Não há transação entre MongoDB e PostgreSQL.
- Favoritos usam lock transacional consultivo PostgreSQL para evitar corrida na criação da watchlist compartilhada.

## Conexões

- PostgreSQL operacional: banco `midas`, usuário de aplicação `midas_app`, conexão com timeout de 5 segundos e linhas em formato de dicionário.
- MongoDB operacional: banco e autenticação `midas_training`, usuário `midas_app`, seleção de servidor com timeout de 5 segundos e datas timezone-aware.
- RAG: serviço separado `rag-postgres`, banco `midas_rag`, usuário `midas_rag`, porta local padrão 5433. A tabela `rag_chunks` suporta busca textual em português e embeddings sem dimensão fixa; o índice vetorial depende do modelo de embedding escolhido. `scripts/index_rag.py` compara hashes por documento e reindexa somente módulos RAG novos ou alterados.

## Regras de segurança

- Nunca incluir `.env`, senhas ou tokens em contexto de RAG, logs ou respostas.
- Segredos devem ser lidos por ambiente e não aparecer em URLs.
- Não afirmar isolamento entre usuários até implementar `user_id`, autenticação e autorização.
- Ao criar persistência de carteira, modelar propriedade desde o início.

## Pontos de código

- `infra/postgres/01-init.sh`
- `infra/mongo/01-init.js`
- `midas_core/infrastructure/database.py`
- `midas_core/infrastructure/repositories.py`
- `midas_core/config.py`
- `compose.yaml`
- `infra/rag-postgres/01-init.sql`
- `scripts/index_rag.py`
