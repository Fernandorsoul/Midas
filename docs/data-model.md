# Modelo de dados do Midas

## Escopo

O PostgreSQL armazena o estado operacional e os registros dos experimentos. O MongoDB armazena snapshots, amostras e artefatos de aprendizado de máquina.

- MER: visão conceitual das entidades e relações do negócio.
- DER: visão lógica e física com atributos, chaves e cardinalidades.
- Relações entre os bancos são referências lógicas verificadas pela aplicação.

## MER — Modelo Entidade-Relacionamento

~~~mermaid
erDiagram
    ATIVO ||--o{ COTACAO : possui
    LISTA ||--o{ ITEM_DA_LISTA : contem
    ATIVO ||--o{ ITEM_DA_LISTA : participa
    DATASET ||--|{ AMOSTRA_DE_TREINO : contem
    DATASET ||--o{ EXPERIMENTO : fundamenta
    DATASET ||--o{ ARTEFATO_DE_MODELO : produz
    EXPERIMENTO o|--o| ARTEFATO_DE_MODELO : descreve
~~~

| Entidade | Papel |
|---|---|
| Ativo | Instrumento acompanhado pelo Midas |
| Cotação | Preço diário de um ativo, identificado por fonte |
| Lista | Agrupamento de ativos, atualmente usado para favoritos |
| Dataset | Snapshot imutável usado em um treinamento |
| Amostra de treino | Variáveis conhecidas em uma data e retorno futuro observado |
| Experimento | Execução avaliada com algoritmo, horizonte, parâmetros e métricas |
| Artefato de modelo | Pesos e parâmetros necessários para inferência |

O dataset é derivado de cotações, mas não guarda uma chave para cada cotação. Ele registra a origem e materializa as amostras usadas.

## DER — PostgreSQL

~~~mermaid
erDiagram
    ASSETS {
        bigint id PK
        text ticker UK
        text name
        text category
        text sector
        boolean is_demo
        timestamptz created_at
    }
    DAILY_PRICES {
        bigint asset_id PK, FK
        date price_date PK
        text source PK
        numeric close
        numeric adjusted_close
        numeric volume
        timestamptz ingested_at
    }
    WATCHLISTS {
        bigint id PK
        text name
        timestamptz created_at
    }
    WATCHLIST_ASSETS {
        bigint watchlist_id PK, FK
        bigint asset_id PK, FK
    }
    MODEL_RUNS {
        uuid id PK
        text dataset_id
        text algorithm
        integer horizon_months
        jsonb metrics
        jsonb parameters
        timestamptz created_at
    }
    ASSETS ||--o{ DAILY_PRICES : tem
    WATCHLISTS ||--o{ WATCHLIST_ASSETS : contem
    ASSETS ||--o{ WATCHLIST_ASSETS : participa
~~~

### Chaves e restrições

| Tabela | Chave ou regra | Finalidade |
|---|---|---|
| assets | PK id | Identificador interno |
| assets | UNIQUE ticker | Um cadastro por código |
| assets | CHECK category | Somente stock, fii ou fiagro |
| daily_prices | PK composta asset_id, price_date, source | Uma cotação por ativo, pregão e fonte |
| daily_prices | FK asset_id para assets.id | Impede cotação sem ativo |
| daily_prices | Preços positivos e volume não negativo | Integridade numérica |
| watchlist_assets | PK composta watchlist_id, asset_id | Impede item duplicado |
| watchlist_assets | FKs para listas e ativos | Implementa N:N |
| model_runs | CHECK horizon_months | Somente 12, 24 ou 36 meses |

A remoção de uma lista apaga seus itens por cascata. A remoção de um ativo é bloqueada enquanto houver preços ou itens relacionados.

## DER — MongoDB

MongoDB não possui chaves estrangeiras. As cardinalidades abaixo são impostas pelo código e pelos índices.

~~~mermaid
erDiagram
    DATASETS {
        string _id PK
        string name
        string version
        string source
        boolean is_demo
        date created_at
        array horizons
        array tickers
        integer samples
    }
    TRAINING_SAMPLES {
        objectId _id PK
        string dataset_id FK
        string ticker
        date as_of
        date label_end
        integer horizon_months
        object features
        number target
    }
    MODEL_ARTIFACTS {
        string _id PK
        string dataset_id FK
        date created_at
        object parameters
        array mean
        array scale
        array weights
    }
    DATASETS ||--|{ TRAINING_SAMPLES : dataset_id
    DATASETS ||--o{ MODEL_ARTIFACTS : dataset_id
~~~

### Estrutura de features

~~~json
{
  "momentum_6m": 0.12,
  "momentum_12m": 0.18,
  "volatility": 0.24,
  "drawdown": -0.09
}
~~~

Os números acima ilustram o formato; não são registros usados pelo modelo.

### Índices e validações

| Coleção | Regra | Finalidade |
|---|---|---|
| datasets | UNIQUE name, version | Impede publicação duplicada da mesma versão |
| training_samples | UNIQUE dataset_id, ticker, as_of, horizon_months | Impede amostra duplicada |
| training_samples | INDEX dataset_id, as_of, label_end | Acelera seleção e expurgo temporal |
| training_samples | horizonte em 12, 24 ou 36 | Mantém horizontes suportados |
| model_artifacts | INDEX dataset_id, created_at descendente | Localiza modelos recentes |
| Todas | JSON Schema | Exige campos e tipos essenciais |

A aplicação também exige as_of anterior a label_end, valores finitos e label_end já observado. Essas condições não estão no JSON Schema atual.

## Relações entre PostgreSQL e MongoDB

~~~mermaid
erDiagram
    MONGO_DATASETS {
        string _id PK
    }
    MONGO_MODEL_ARTIFACTS {
        string _id PK
        string dataset_id
    }
    POSTGRES_MODEL_RUNS {
        uuid id PK
        text dataset_id
    }
    MONGO_DATASETS ||--o{ POSTGRES_MODEL_RUNS : dataset_id
    MONGO_MODEL_ARTIFACTS o|--o| POSTGRES_MODEL_RUNS : mesmo_id
~~~

As relações são lógicas:

1. model_runs.dataset_id deve apontar para datasets._id.
2. model_runs.id, convertido para texto, deve coincidir com model_artifacts._id.
3. O painel só usa uma execução quando encontra dataset e artefato.
4. Ao falhar a gravação do model_run, o caso de uso tenta remover o artefato recém-criado.
5. Não existe transação distribuída; auditoria e reconciliação continuam necessárias.

## Ciclo dos dados

~~~mermaid
flowchart LR
    API[brapi.dev] --> Assets[(assets)]
    API --> Prices[(daily_prices)]
    Prices --> Dataset[(datasets)]
    Dataset --> Samples[(training_samples)]
    Samples --> Artifact[(model_artifacts)]
    Artifact --> Run[(model_runs)]
    Run --> Ranking[Ranking]
    Prices --> Ranking
~~~

## Invariantes

- Registros is_demo=true não participam do painel ou do treinamento real.
- Retornos de treinamento usam adjusted_close.
- Gráficos exibem close.
- A origem integra a chave de daily_prices.
- Um snapshot publicado deve ser imutável; uma atualização gera outro dataset.
- Métricas ficam no PostgreSQL e pesos no MongoDB.
- A inferência exige os dois lados do experimento.
