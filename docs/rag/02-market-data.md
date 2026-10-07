# Módulo: dados de mercado

## Responsabilidade

Cadastro de ativos, histórico diário de preços, fontes externas e importação.

## Estado atual

- PostgreSQL armazena ativos e preços diários.
- `brapi.dev` e Yahoo Finance são fontes usadas pelo projeto.
- O relatório escolhe a fonte mais recente disponível por ativo para exibição.
- Preço mostrado no painel é fechamento diário; treinamento prioriza fechamento ajustado.

## Fluxo de importação confirmado

1. A brapi valida tickers alfanuméricos de 4 a 12 caracteres e períodos permitidos (`1mo` a `max`).
2. Para compatibilidade com o plano gratuito, a importação brapi busca cotação e histórico um ticker por requisição.
3. Pontos sem data/fechamento válidos são ignorados; uma importação sem histórico válido falha para o ativo.
4. Yahoo normaliza tickers brasileiros com o sufixo `.SA`, baixa histórico sem ajuste automático e preserva `Close`, `Adj Close` e volume quando válidos.
5. `PostgresRepository.save_stocks` cria/atualiza o ativo e faz upsert por `(asset_id, price_date, source)`.

## Seleção de preços para análise

`assets_with_prices()` seleciona, para cada ativo, a fonte cujo registro mais recente possui a maior combinação de `price_date`, `ingested_at` e nome da fonte; então devolve até 1.260 pregões dessa mesma fonte, em ordem cronológica. Portanto, a fonte pode variar por ativo, mas não dentro da série exibida.

## Falhas e cuidados conhecidos

- A brapi tenta novamente falhas de rede/timeout e HTTP 429 com backoff exponencial; erros 401/403 indicam token ausente ou sem acesso.
- A importação Yahoo continua os demais tickers se um falhar e devolve `warnings`; falha integralmente se nenhum ativo puder ser importado.
- Dividendos consultados pelo Yahoo são dados correntes de 12 meses, não eventos persistidos.
- `yahoo.py` contém lógica de fundamentos após o retorno de `fetch_dividends`; ela está inalcançável e não há uma função pública `fetch_fundamentals` definida. Não assumir que fundamentos pontuais estejam disponíveis até esse defeito ser corrigido.

## Regras importantes

- Sempre preservar `source`, `price_date` e, quando disponível, preço ajustado.
- Não apresentar dado sem informar ou conseguir determinar sua data de mercado.
- Não esconder erro de importação como se fosse atualização concluída.
- Antes de alterar fonte ou regra de prioridade, verificar impacto no dataset de treinamento.

## Pontos de código

- `midas_core/infrastructure/brapi.py`
- `midas_core/infrastructure/yahoo.py`
- `midas_core/application/market_import.py`
- `midas_core/application/market_import_yahoo.py`
- `midas_core/infrastructure/repositories.py`
- `midas_core/application/analysis.py`

## Evolução desejada

Definir fonte primária/fallback por tipo de dado e persistir metadados de coleta, qualidade e atraso.
