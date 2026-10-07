# Midas — Contexto de Produto e RAG

> Documento de referência amplo para respostas consistentes sobre o Midas. Para uso por RAG, comece em [`rag/00-router.md`](rag/00-router.md) e recupere apenas o módulo relevante. Atualizar quando a arquitetura, as fontes de dados ou o escopo do produto mudarem.

## O que é o Midas

Midas é uma aplicação local de pesquisa de investimentos brasileiros. O produto combina:

- histórico de preços de mercado;
- carteira acompanhada pelo usuário;
- indicadores de preço, risco e retorno;
- treinamento de modelos quantitativos para ranking de ativos;
- validação temporal dos modelos.

O propósito é apoiar pesquisa e acompanhamento patrimonial. O Midas **não é uma corretora**, não envia ordens, não garante retornos e não deve apresentar previsões como recomendação de compra ou venda.

## Estado atual

### Capacidades existentes

- Importação de ações brasileiras a partir de `brapi.dev` e Yahoo Finance.
- Persistência de ativos e preços diários no PostgreSQL.
- Persistência de datasets, amostras de treinamento e artefatos de modelo no MongoDB.
- Cálculo de momentum, volatilidade, drawdown e outros fatores de preço.
- Modelos de regressão treinados com separação temporal, expurgo de amostras e validação fora do treino.
- Ranking de oportunidades; um ativo só é candidato se o modelo estiver validado, a estimativa for positiva e o drawdown atingir o critério definido.
- Interface web com carteira, explorador de ativos, treinamento, validação e método.
- Favoritos persistidos no PostgreSQL.
- Consulta de dividendos e uma simulação simples de reinvestimento usando Yahoo Finance.

### Limitações atuais importantes

- A carteira atual fica em memória do processo (`PORTFOLIO_TICKERS`) e é perdida ao reiniciar a aplicação.
- Não há histórico de compras, vendas, aportes, retiradas, custos ou impostos.
- Quantidade de cotas não equivale a uma posição financeira auditável: não há preço médio nem custo de aquisição.
- Dividendos são uma consulta ao vivo e não eventos persistidos por data-com/pagamento.
- A adição de um ativo executa a importação de forma síncrona, apesar do comentário indicar processamento em segundo plano.
- Há mais de uma fonte de dados no produto, mas a interface deve informar claramente origem e data de atualização dos dados exibidos.
- Alguns textos da interface apresentam codificação incorreta e precisam ser armazenados em UTF-8.
- O universo de ativos e a cobertura histórica ainda são limitados.
- O modelo não considera notícias, custos, impostos, liquidez operacional ou eventos corporativos como parte do sinal.

## Arquitetura atual

```text
Interface web (React sem JSX)
        |
        v
Servidor HTTP Python
        |
        +--> PostgreSQL: ativos, preços, favoritos, execuções de modelo
        |
        +--> MongoDB: datasets, amostras e artefatos de modelo
        |
        +--> Provedores externos: brapi.dev e Yahoo Finance
```

Principais diretórios:

- `web/`: interface web e estilos.
- `midas_core/domain/`: entidades, fatores e regressão.
- `midas_core/application/`: casos de uso de análise, datasets, treinamento e importação.
- `midas_core/infrastructure/`: bancos de dados e adaptadores de provedores.
- `midas_core/interfaces/http.py`: rotas HTTP e execução atual de tarefas.
- `infra/`: inicialização dos bancos.
- `docs/`: documentação técnica.

## Regras do ranking quantitativo

Os modelos estimam retorno acumulado ajustado para horizontes de 6, 12, 24 ou 36 meses. O modelo é uma ferramenta de priorização de pesquisa, não uma previsão garantida.

Um ativo pode ser marcado como `Candidato` somente se:

1. existir artefato de modelo compatível;
2. o modelo for considerado validado;
3. a melhora de MAE contra a referência for de pelo menos 2%;
4. a correlação de ranking for de pelo menos 0,10;
5. o drawdown de 12 meses for de pelo menos 5% abaixo da máxima;
6. a estimativa de retorno for positiva.

Ao explicar o ranking, sempre comunicar:

- horizonte analisado;
- data/cobertura dos dados;
- métricas de validação;
- incerteza da estimativa;
- limitações da base e do modelo;
- ausência de recomendação financeira individual.

## Visão de produto desejada

O Midas deve evoluir de painel de ativos para uma plataforma de acompanhamento patrimonial e pesquisa de investimentos. A proposta é composta por três pilares:

1. **Carteira real e persistente:** operações, posições, custo, resultado e proventos.
2. **Análise de mercado confiável:** dados identificáveis, atuais, comparáveis e visualmente claros.
3. **Pesquisa quantitativa explicável:** modelos auditáveis, métricas visíveis e sinais contextualizados.

## Modelo-alvo de carteira

O núcleo da evolução é substituir a lista em memória por operações persistidas.

Tabelas recomendadas:

| Tabela | Finalidade | Campos principais |
|---|---|---|
| `users` | Identidade do usuário | `id`, `email`, `password_hash`, `created_at` |
| `portfolios` | Carteiras do usuário | `id`, `user_id`, `name`, `currency`, `created_at` |
| `portfolio_transactions` | Livro razão de operações | `id`, `portfolio_id`, `asset_id`, `type`, `trade_date`, `quantity`, `unit_price`, `fees`, `notes` |
| `cash_movements` | Aportes, retiradas e taxas gerais | `id`, `portfolio_id`, `date`, `amount`, `type` |
| `corporate_events` | Proventos e eventos societários | `asset_id`, `type`, `ex_date`, `payment_date`, `amount_per_share` |
| `alerts` | Regras de notificação | `user_id`, `asset_id`, `type`, `threshold`, `enabled` |

Tipos mínimos de operação:

- `buy` e `sell`;
- `dividend` e `interest_on_equity` (JCP);
- `deposit` e `withdrawal`;
- `fee` e `tax`;
- `split`, `reverse_split` e `subscription`.

Posições devem ser derivadas das operações. Não usar apenas um campo editável de quantidade como fonte da verdade.

## Métricas de carteira esperadas

Para cada ativo e para a carteira consolidada, o produto deve ser capaz de mostrar:

- quantidade atual;
- preço médio;
- custo total;
- cotação e data de atualização;
- valor de mercado;
- lucro/prejuízo não realizado;
- lucro/prejuízo realizado;
- proventos brutos e líquidos;
- retorno total em valor e percentual;
- peso na carteira;
- comparação com CDI e Ibovespa.

Para períodos com aportes e retiradas, usar métricas adequadas:

- retorno ponderado no tempo (TWR) para medir estratégia;
- taxa interna de retorno / XIRR para medir a experiência do investidor.

## Dados e transparência

Para todo preço, provento ou fundamento mostrado, preferir registrar e informar:

- fonte;
- data e hora de coleta;
- data de mercado;
- moeda;
- se é preço ajustado;
- atraso conhecido;
- condição de qualidade do dado.

Definir uma política explícita de fonte primária e fallback. Nunca ocultar uma falha de coleta com um dado antigo sem comunicar a data ao usuário.

## Experiência recomendada

### Dashboard

- patrimônio atual;
- resultado do dia e resultado total;
- evolução de patrimônio versus aportes;
- retorno versus CDI e Ibovespa;
- alocação por ativo, setor e classe;
- concentração;
- proventos dos últimos 12 meses;
- alertas e dados que precisam de atualização.

### Página de ativo

- gráfico de preço e volume por período;
- marcações de compras, vendas e proventos próprios;
- dados fundamentalistas e calendário de eventos;
- histórico de dividendos;
- indicadores técnicos opcionais;
- posição do usuário;
- score quantitativo com explicação e riscos.

### Exploração e pesquisa

- filtros por setor, liquidez, valor de mercado, indicadores fundamentalistas, risco e sinais;
- ordenação de colunas;
- colunas configuráveis;
- filtros salvos;
- exportação CSV;
- comparação entre ativos.

### Alertas

- preço ou variação;
- mudança de ranking ou de sinal;
- concentração acima do limite;
- provento declarado ou pago;
- evento de resultado;
- falha de atualização ou dado desatualizado.

## Processamento assíncrono

Importação, enriquecimento de dados e treinamento não devem bloquear requisições HTTP. O fluxo recomendado é:

```text
ação do usuário -> job persistido -> worker executa -> status/progresso salvo -> interface consulta/recebe atualização
```

O registro de job deve conter pelo menos `id`, `type`, `status`, `progress`, `created_at`, `started_at`, `finished_at`, `error` e referência ao usuário/carteira quando necessário.

## Segurança e multiusuário

Antes de disponibilizar o produto para terceiros:

- implementar autenticação;
- vincular carteiras, favoritos, alertas e operações a um usuário;
- autorizar cada rota por proprietário do recurso;
- guardar senhas apenas com hash seguro;
- registrar auditoria de operações financeiras;
- manter segredos fora do repositório;
- oferecer exportação e exclusão de dados pessoais.

## Prioridades de implementação

### Fase 1 — fundação confiável

1. Corrigir codificação UTF-8 e mensagens da interface.
2. Criar carteiras e operações persistidas no PostgreSQL.
3. Calcular posições, preço médio, custo e P&L.
4. Converter importações em jobs assíncronos.
5. Exibir fonte e horário de atualização dos dados.
6. Criar testes de carteira, falhas de provedores e reinicialização.

### Fase 2 — valor diário ao usuário

1. Dashboard patrimonial.
2. Benchmark CDI e Ibovespa.
3. Gráficos de patrimônio, alocação e proventos.
4. Página detalhada de ativo.
5. Histórico persistido de dividendos e calendário.
6. Importação de operações por CSV.

### Fase 3 — profundidade analítica

1. Screener avançado e comparação de ativos.
2. Métricas de liquidez, fundamentos e risco.
3. Explicabilidade de fatores do modelo.
4. Histórico de sinais e modelos.
5. Backtests que incluam custos e regras explícitas.

### Fase 4 — produto multiusuário

1. Usuários, autenticação e autorização.
2. Múltiplas carteiras e objetivos.
3. Alertas externos com consentimento.
4. Observabilidade, backup e recuperação.
5. Política de privacidade e segurança.

## Diretrizes de resposta para o RAG

- Responder em português, salvo solicitação contrária.
- Diferenciar fato atual, proposta de melhoria e suposição.
- Não afirmar que o Midas executa ordens, integra corretoras ou oferece recomendação financeira se isso não estiver implementado.
- Tratar previsões como estimativas experimentais, sujeitas a erro.
- Quando falar de carteira atual, explicar que a persistência de operações é uma prioridade de evolução se ela ainda não tiver sido implementada.
- Privilegiar clareza sobre fonte, data de atualização, limitações e riscos.
- Para questões de implementação, sugerir mudanças incrementais e testáveis, começando pelo modelo de dados de carteira.
