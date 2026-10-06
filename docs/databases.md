# Bancos do Midas

Consulte também o [MER e os DERs](data-model.md).

## Iniciar

```sh
python3 scripts/setup_env.py
docker compose up -d --wait
python3 scripts/check_databases.py
```

As senhas aleatórias estão no `.env` ignorado pelo Git, com permissão 600. O gerador nunca substitui um arquivo existente. Não compartilhe esse arquivo. Os usuários da aplicação são separados dos administradores.

| Serviço | Endereço local | Banco | Usuário da aplicação | Senha no .env |
|---|---|---|---|---|
| PostgreSQL 18 | 127.0.0.1:5432 | midas | midas_app | POSTGRES_APP_PASSWORD |
| MongoDB 8.0 | 127.0.0.1:27017 | midas_training | midas_app | MONGO_APP_PASSWORD |

MongoDB usa `authSource=midas_training`. Contêineres na rede do Compose usam os hosts `postgres` e `mongodb`. As portas externas escutam somente em loopback. Imagens oficiais: https://hub.docker.com/_/postgres e https://hub.docker.com/_/mongo . Tags fixam a versão principal; um deploy de produção deve fixar também o digest.

## Responsabilidades

PostgreSQL: cadastro de ativos (`assets`), preços diários com origem (`daily_prices`), listas (`watchlists`, `watchlist_assets`) e registro de experimentos (`model_runs`). Valores monetários usam `numeric`.

MongoDB: catálogo de snapshots versionados (`datasets`), documentos individuais de treino (`training_samples`) e parâmetros de modelos (`model_artifacts`). As amostras armazenam a data da observação e do fim do alvo, permitindo expurgo temporal. Há validadores de estrutura e índices únicos para evitar duplicação. Conjuntos grandes são divididos em documentos; não se armazena um dataset inteiro em um documento.

O `dataset_id` em ambos os bancos identifica o mesmo snapshot. Não há chave estrangeira ou transação automática entre PostgreSQL e MongoDB: a aplicação deve validar referências, datas, integridade e imutabilidade de snapshots publicados. Os esquemas ainda não implementam autenticação de usuários ou isolamento entre contas.

## Operação

```sh
docker compose ps
docker compose stop
docker compose start --wait
```

Volumes nomeados preservam os dados ao recriar os contêineres. `docker compose down` preserva volumes; **`docker compose down -v` apaga os bancos**. Persistência não substitui backup; antes de dados reais, configurar backup e testar restauração.

Scripts `infra/` são executados somente na primeira inicialização de volumes vazios. Alterações futuras de esquema exigem migrações; alterar `.env` não troca senhas de bancos existentes. Não apague volumes para aplicar uma alteração.

## Integração com a aplicação

O painel consulta ativos e preços no PostgreSQL. Favoritos são persistidos na lista compartilhada `Favoritos`, sem localStorage. Métricas vêm de `model_runs`, verificando o dataset e o artefato correspondente no MongoDB. Registros marcados como demonstração são excluídos das consultas. O treinamento explícito em `training.py` lê exclusivamente amostras do MongoDB e grava artefatos e métricas nos bancos. Sem dados, a interface permanece vazia. Sem conexão, a API retorna 503. A importação de ações e históricos da brapi.dev é feita por `market_api.py`. `dataset.py` publica snapshots e amostras no MongoDB antes do treinamento.
