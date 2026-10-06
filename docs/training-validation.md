# Treinamento e validação temporal

## Objetivo

Prever o retorno ajustado dos próximos 12 meses usando somente informações disponíveis na data da previsão e comparar a estimativa com o retorno real quando o horizonte terminar.

## Formação de uma amostra

~~~mermaid
timeline
    title Amostra com horizonte de 12 meses
    T-12 até T : calcula momentum, volatilidade e drawdown
    T : modelo produz a previsão
    T até T+12 : período desconhecido pelo modelo
    T+12 : retorno real vira o alvo observado
~~~

Para uma amostra datada em T:

- momentum de 6 meses usa preços entre T-6 e T;
- momentum de 12 meses usa preços entre T-12 e T;
- volatilidade e drawdown usam a janela encerrada em T;
- target usa adjusted_close em T+12 dividido por adjusted_close em T;
- nenhum preço posterior a T participa das variáveis.

## Separação temporal

~~~mermaid
flowchart LR
    Train[Seleção: rótulos terminam antes da validação]
    Validation[Validação: escolhe alpha e termina antes do teste]
    Test[Teste final: nunca escolhe parâmetros]
    Train --> Validation --> Test
~~~

O expurgo usa label_end, não apenas as_of. Uma linha iniciada antes do teste é removida do treino se seu retorno de 12 meses terminar dentro do teste.

## Processo

1. Importar dez anos de fechamentos diários reais.
2. Selecionar o último fechamento ajustado de cada mês.
3. Criar variáveis com a janela anterior de 12 meses.
4. Criar o retorno real dos 12 meses seguintes.
5. Comparar modelos e hiperparâmetros somente na validação expurgada.
6. Ajustar o modelo vencedor com dados encerrados antes do teste.
7. Gerar previsões para o teste sem usar seus resultados.
8. Comparar predicted e actual após os retornos reais já estarem disponíveis.
9. Ajustar o modelo de produção com todos os rótulos conhecidos somente depois da avaliação.


## Modelos candidatos

O treinamento v3 compara candidatos reais de Python sem mudar a separação temporal:

| Família | Biblioteca | Parâmetros testados |
|---|---|---|
| Ridge | NumPy interno | alpha em `0.1`, `1.0`, `10.0`, `100.0` |
| Ridge | scikit-learn | alpha em `0.1`, `1.0`, `10.0`, `100.0` |
| Lasso | scikit-learn | alpha em `0.0005`, `0.001`, `0.005`, `0.01` |
| ElasticNet | scikit-learn | alpha e `l1_ratio` |
| Huber | scikit-learn | regressão robusta contra outliers |

O vencedor é escolhido apenas pelo MAE da validação. Depois disso, o teste final mede o vencedor uma única vez. O artefato salvo continua no formato `mean`, `scale` e `weights`, então a inferência do painel segue compatível.

## Critérios para validar o modelo

O painel só libera candidatos quando:

- a melhora relativa do MAE sobre a referência é de pelo menos 2%;
- a correlação média de ranking é de pelo menos 0,10;
- o ativo está 5% ou mais abaixo da máxima ajustada de 12 meses;
- a estimativa pontual de retorno é positiva.

Superar a referência por uma margem menor é registrado, mas não considerado evidência suficiente.

## Auditoria

Cada previsão do teste guarda:

| Campo | Significado |
|---|---|
| ticker | Ativo previsto |
| as_of | Data em que a previsão poderia ser produzida |
| label_end | Data final do horizonte de 12 meses |
| predicted | Retorno previsto |
| actual | Retorno ajustado realmente observado |
| absolute_error | Distância absoluta entre previsão e realidade |

Esses registros aparecem na seção “Previsões históricas × resultados reais” e também dentro de metrics.predictions no model_run mais recente.

## Limitações atuais

- Universo com28 ativos importados da brapi.dev.
- Amostras mensais sobrepostas não são independentes.
- Fundamentos, inflação, juros, notícias, custos e liquidez ainda não entram nas variáveis.
- O backtest mede previsão de retorno, não desempenho de uma carteira executável.
