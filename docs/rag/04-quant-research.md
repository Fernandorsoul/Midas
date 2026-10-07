# Módulo: pesquisa quantitativa

## Responsabilidade

Construir datasets, treinar modelos, salvar artefatos, validar temporalmente e gerar ranking de pesquisa.

## Estado atual

- Horizontes aceitos: 6, 12, 24 e 36 meses.
- Amostras usam preços mensais ajustados e fatores de momentum, volatilidade, drawdown e fatores adicionais quando disponíveis.
- O alvo é retorno ajustado acumulado no horizonte futuro.
- Há separação temporal entre treino, validação e teste, com expurgo de alvos que alcançam o próximo período.
- Artefatos e amostras ficam no MongoDB; métricas da execução ficam no PostgreSQL.

## Pipeline confirmado

1. `publish_dataset` lê preços por fonte, consolida cada ticker e transforma a série em fechamentos mensais ajustados.
2. Quando `source=all`, a ordem de consulta é `enriched`, `yahoo.finance`, `brapi.dev`; as linhas são acumuladas por ticker. A função não faz deduplicação entre fontes, portanto a mistura precisa ser tratada com cuidado ao evoluir essa regra.
3. Fundamentos históricos são buscados no Yahoo por ticker; falha nesse enriquecimento usa valores neutros para os fatores fundamentais.
4. `build_samples` começa no 13º fechamento mensal, exige que o alvo esteja no passado e cria retorno futuro para cada horizonte.
5. `VariableTrainer` separa datas em treino de seleção, validação, treino de avaliação e teste; a separação usa `label_end` para evitar visão do futuro.
6. Candidatos são escolhidos por menor MAE na validação; o escolhido é avaliado uma vez no teste final contra uma baseline de média do treino de avaliação.
7. Dataset e artefato vão ao MongoDB; após salvar artefato, o run é salvo no PostgreSQL. Se o segundo passo falhar, o artefato é removido como compensação.

## Fatores e métricas

- Fatores de preço: momentum de 3/6/12 meses, volatilidade anualizada, drawdown, RSI, MACD normalizado, razão com SMA, posição de Bollinger e ATR relativo.
- Fatores fundamentais: margem, ROE, P/L, dividend yield, dívida/patrimônio e crescimento de EPS, com valores neutros quando indisponíveis.
- Métricas expostas: MAE, MAE da baseline, melhora relativa, acerto direcional, correlação média de Spearman por data e previsões de teste linha a linha.
- A faixa da oportunidade é construída somando os quantis 10% e 90% dos resíduos do teste à estimativa pontual.

## Implementação e limitações relevantes

- A validação de relatório exige `model_version == 5`, não apenas boas métricas.
- O modelo de inferência persistido é lido como `RidgeModel`. Modelos de árvore ou deep learning não possuem o mesmo formato de artefato (`weights`) e não são reidratados por `from_artifact`; confirmar e corrigir a serialização antes de depender desses candidatos em produção.
- O ensemble avalia a média de modelos no teste, mas o modelo de produção usa somente o primeiro candidato selecionado para o artefato. Não descrever o artefato atual como ensemble persistido.
- A função `_best_source` existe, mas não é usada por `publish_dataset`.

## Regra de candidato

Um ativo é `Candidato` apenas quando há modelo validado, melhoria de MAE >= 2%, correlação de ranking >= 0,10, drawdown <= -5% e estimativa positiva.

## Comunicação obrigatória

Ao explicar um sinal, incluir horizonte, incerteza/faixa, data dos dados, métricas de validação e limitações. Não transformar sinal em recomendação.

## Pontos de código

- `midas_core/domain/features.py`
- `midas_core/domain/regression.py`
- `midas_core/training/variables.py`
- `midas_core/application/datasets.py`
- `midas_core/application/training.py`
- `midas_core/application/analysis.py`
- `web/EvaluationPanel.js`, `web/ValidationHistory.js`, `web/TrainingConsole.js`
