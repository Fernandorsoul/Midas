# Arquitetura do Midas

## Objetivo

O Midas importa cotações reais, produz snapshots de treinamento, avalia modelos temporais e apresenta sinais quantitativos. A arquitetura separa regras financeiras, orquestração, persistência e interfaces.

## Visão geral

~~~mermaid
flowchart LR
    User[Usuário] --> Web[Interface web]
    User --> CLI[Comandos CLI]
    Web --> HTTP[Interface HTTP]
    CLI --> UseCases[Casos de uso]
    HTTP --> UseCases
    UseCases --> Domain[Domínio financeiro]
    UseCases --> Trainer[Módulo de treinamento]
    UseCases --> Repositories[Repositórios]
    Repositories --> PG[(PostgreSQL)]
    Repositories --> Mongo[(MongoDB)]
    Repositories --> Brapi[brapi.dev]
    Trainer --> Domain
~~~

A direção das dependências é das bordas para o núcleo. O domínio e o módulo de treinamento não importam código de banco, rede ou interface.

## Estrutura

~~~text
midas_core/
├── config.py
├── domain/
│   ├── entities.py
│   ├── features.py
│   └── regression.py
├── training/
│   └── variables.py
├── application/
│   ├── analysis.py
│   ├── datasets.py
│   ├── market_import.py
│   └── training.py
├── infrastructure/
│   ├── brapi.py
│   ├── database.py
│   └── repositories.py
└── interfaces/
    ├── cli.py
    └── http.py
~~~

| Camada | Responsabilidade | Não deve conhecer |
|---|---|---|
| domain | Entidades, variáveis, regressão e métricas puras | HTTP, SQL, MongoDB, ambiente |
| training | Seleção de variáveis, regularização, validação temporal e ajuste | Bancos, API externa, interface |
| application | Coordenar importação, snapshots, treinamento e análise | Detalhes de protocolo e SQL |
| infrastructure | Adaptar brapi.dev, PostgreSQL e MongoDB | HTML e decisões de apresentação |
| interfaces | Validar entrada e apresentar saída HTTP ou CLI | Regras financeiras |
| config.py | Traduzir variáveis de ambiente em configuração tipada | Regras de negócio |

Os scripts da raiz são fachadas compatíveis:

| Script | Delegação |
|---|---|
| midas.py | servidor em interfaces.http |
| market_api.py | importação em application.market_import |
| dataset.py | snapshot e treino em application.datasets |
| training.py | treino em application.training |

## Fluxos principais

### Importação de mercado

~~~mermaid
sequenceDiagram
    participant CLI
    participant Import as MarketImport
    participant API as brapi.dev
    participant Repo as PostgresRepository
    participant PG as PostgreSQL
    CLI->>Import: tickers e período
    Import->>API: cotação e histórico
    API-->>Import: JSON real
    Import->>Import: validar e normalizar
    Import->>Repo: ImportedStock[]
    Repo->>PG: upsert assets e daily_prices
    PG-->>CLI: quantidades persistidas
~~~

### Treinamento

~~~mermaid
sequenceDiagram
    participant CLI
    participant Dataset as DatasetService
    participant PG as PostgreSQL
    participant Mongo as MongoDB
    participant App as TrainingUseCase
    participant Trainer as VariableTrainer
    CLI->>Dataset: horizonte
    Dataset->>PG: fechamentos ajustados
    Dataset->>Dataset: variáveis e alvos mensais
    Dataset->>Mongo: dataset e training_samples
    Dataset->>App: dataset_id e horizonte
    App->>Mongo: carregar amostras
    App->>Trainer: train rows
    Trainer->>Trainer: treino, validação e teste temporal
    Trainer-->>App: TrainingResult
    App->>Mongo: model_artifact
    App->>PG: model_run e métricas
~~~

### Consulta de oportunidades

~~~mermaid
sequenceDiagram
    participant Browser
    participant HTTP
    participant Analysis
    participant PG as PostgreSQL
    participant Mongo as MongoDB
    Browser->>HTTP: GET /api/analysis
    HTTP->>Analysis: horizonte
    Analysis->>PG: ativos, preços e model_runs
    Analysis->>Mongo: dataset e model_artifact
    Analysis->>Analysis: variáveis atuais e estimativa
    Analysis-->>Browser: ranking, métricas e incerteza
~~~

## Regras arquiteturais

1. Cálculos financeiros recebem dados por argumento e permanecem determinísticos.
2. SQL, drivers e chamadas HTTP ficam em infrastructure.
3. Casos de uso dependem de repositórios injetáveis.
4. A interface não implementa regra financeira.
5. Dados externos são validados antes de chegar ao domínio.
6. Nenhum teste temporal usa rótulos que terminam após o início do período avaliado.
7. Métricas de teste não participam da escolha de parâmetros.
8. Uma nova fonte de mercado deve usar outro adaptador.

## Persistência

O [modelo de dados](data-model.md) contém o MER, os DERs e as relações lógicas entre PostgreSQL e MongoDB. A [operação dos bancos](databases.md) descreve inicialização, credenciais, volumes e cuidados operacionais.
