# Midas

Painel de investimentos com PostgreSQL como fonte dos ativos, preços, favoritos e registros de experimentos. MongoDB armazena datasets, amostras de treinamento e parâmetros dos modelos. Não há catálogo fictício, geração aleatória de históricos, cache de dados ou persistência no navegador.

## Executar

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
python3 scripts/setup_env.py
docker compose up -d --build --wait
```

Abra http://localhost:8000. O Compose mantém a aplicação e os bancos ativos com reinício automático. Use `docker compose logs -f app` para acompanhar o servidor. Bancos vazios resultam em painel vazio; falhas de conexão retornam HTTP 503, sem fallback. O servidor é local e de desenvolvimento, sem autenticação multiusuário. Favoritos pertencem à lista compartilhada `Favoritos` no PostgreSQL.

## Importar ações da B3

O importador consulta a API pública [brapi.dev](https://brapi.dev/docs/acoes/historico) e grava ativos e históricos diários diretamente no PostgreSQL. PETR4, MGLU3, VALE3 e ITUB4 são os símbolos públicos documentados pela API e funcionam sem token:

```sh
.venv/bin/python market_api.py PETR4 VALE3 ITUB4 MGLU3 --range 10y
```

Configure o token sem exibi-lo no terminal:

```sh
.venv/bin/python scripts/set_brapi_token.py
```

Depois importe o universo inicial de 28 ativos:

```sh
.venv/bin/python market_api.py --file config/stock-universe.txt --range 10y
```

O arquivo `config/stock-universe.txt` é editável e não afirma representar uma carteira ou índice oficial. Para outros símbolos ou períodos que exijam autenticação, adicione `BRAPI_TOKEN=...` ao `.env`. O token é enviado no cabeçalho `Authorization` e não aparece na URL. O comando é idempotente: novas execuções atualizam o cadastro e as cotações da fonte `brapi.dev`, sem duplicá-las. O período realmente entregue depende do plano da API, que pode devolver uma janela menor que a solicitada.

## Gerar oportunidades

Depois de atualizar as cotações, publique um snapshot no MongoDB e treine o horizonte desejado:

```sh
.venv/bin/python dataset.py --horizon 12
```

O snapshot usa o último fechamento ajustado de cada mês. Para cada data são calculados momentum de 6 e 12 meses, volatilidade anualizada e distância da máxima ajustada de 12 meses. O alvo é o retorno ajustado acumulado nos 12 meses seguintes.

Um ativo só recebe a marca `Candidato` quando:

- está pelo menos 5% abaixo da máxima ajustada dos últimos 12 meses;
- o modelo estima retorno positivo;
- o modelo melhorou pelo menos 2% sobre a referência e obteve correlação de ranking mínima de 0,10.

A estimativa não é probabilidade nem garantia de alta. O universo atual de 28 ativos importados da brapi.dev continua limitado: as amostras mensais se sobrepõem e o modelo não considera fundamentos, notícias, custos, impostos ou liquidez. O ranking serve para priorizar pesquisa.

Os horizontes 24 e 36 meses permanecem sem sinais até que sejam treinados explicitamente:

```sh
.venv/bin/python dataset.py --horizon 24
.venv/bin/python dataset.py --horizon 36
```

## Módulo de treinamento das variáveis

O módulo `midas_core.training.VariableTrainer` recebe amostras em memória e devolve `TrainingResult` com modelo, métricas e parâmetros. Ele não acessa PostgreSQL, MongoDB, HTTP ou variáveis de ambiente. `VariableTrainingConfig` permite escolher nomes das variáveis, candidatos de regularização, frações temporais e tamanhos mínimos. O treinador v3 compara Ridge em NumPy, Ridge/Lasso/ElasticNet/Huber em scikit-learn quando disponível, escolhe pelo MAE da validação temporal expurgada e mede o vencedor no teste final. O caso de uso `application.training` apenas carrega as amostras e persiste o resultado.

## Treinamento manual

Também é possível treinar novamente um snapshot existente:

```sh
.venv/bin/python training.py ID_DO_DATASET --horizon 12
```

Os modelos usam padronização ajustada somente no treino. A seleção compara os candidatos em um período de validação separado; as últimas 20% das datas ficam intocadas para o teste final. Qualquer amostra cujo alvo alcance o próximo período é expurgada. Artefatos ficam no MongoDB e métricas no PostgreSQL.

## Verificar

```sh
.venv/bin/python -m unittest -v
python3 scripts/check_databases.py
node --check web/app.js
```

[Arquitetura](docs/architecture.md), [MER e DER](docs/data-model.md), [validação temporal](docs/training-validation.md) e [configuração dos bancos](docs/databases.md). O painel mostra o fechamento diário; o treinamento usa o fechamento ajustado retornado pela API. A integração entre bancos não é transacional: em caso de falha ao registrar a execução no PostgreSQL, pode restar um artefato órfão no MongoDB, que o painel ignora.
