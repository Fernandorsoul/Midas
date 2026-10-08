# Módulo: dados de mercado

## Responsabilidade

Cadastro de ativos, histórico diário de preços, fontes externas e importação.

## Estado atual

- PostgreSQL armazena ativos e preços diários.
- Fontes oficiais: `yahoo.finance` (primária) e `brapi.dev` (fallback) para preços.
- Dividendos e fundamentos pontuais: `yahoo.finance`.
- `enriched` e `macro` permanecem **experimentais e fora do pipeline principal**.
- Cada ticker exibe uma série de **fonte única**; a seleção prefere fonte oficial à experimental e, na mesma classe, a mais recente.

## Política de fontes

| Dado | Primária | Fallback | Experimental |
|---|---|---|---|
| Preços | `yahoo.finance` | `brapi.dev` | `enriched` |
| Dividendos | `yahoo.finance` | — | — |
| Fundamentos | `yahoo.finance` | — | `enriched` |

- Código: `midas_core/domain/market_quality.py` (`SOURCE_POLICY`, `resolve_price_source`).
- Relatório e `GET /api/market/quality` expõem `source`, `price_date`, `ingested_at`, `age_days`, `stale`, `quality`, `display_price_field` e `training_price_field`.
- Exibição usa `close`; treino usa `adjusted_close` quando existe (senão `close`).

## Fluxo de importação confirmado

1. A brapi valida tickers alfanuméricos de 4 a 12 caracteres e períodos permitidos (`1mo` a `max`).
2. Para compatibilidade com o plano gratuito, a importação brapi busca cotação e histórico um ticker por requisição.
3. Pontos sem data/fechamento válidos são ignorados; uma importação sem histórico válido falha para o ativo.
4. Yahoo normaliza tickers brasileiros com o sufixo `.SA`, baixa histórico sem ajuste automático e preserva `Close`, `Adj Close` e volume quando válidos.
5. `PostgresRepository.save_stocks` cria/atualiza o ativo e faz upsert por `(asset_id, price_date, source)`.

## Resultado de coleta (não mascarar falha)

`collection_outcome` produz `succeeded` / `partial` / `failed` com contagens. Importação parcial nunca é sucesso; falha integral não persiste. Jobs de importação registram `collection` no resultado.

## Seleção de preços para análise

`assets_with_prices()` escolhe a fonte da série com preferência oficial sobre experimental e recência dentro da classe; devolve até 1.260 pregões **dessa mesma fonte**, em ordem cronológica. A fonte pode variar por ativo, mas não dentro da série exibida.

## Falhas e cuidados conhecidos

- A brapi tenta novamente falhas de rede/timeout e HTTP 429 com backoff exponencial; erros 401/403 indicam token ausente ou sem acesso.
- A importação Yahoo continua os demais tickers se um falhar e devolve `warnings` + `collection.partial`; falha integralmente se nenhum ativo puder ser importado.
- Dividendos consultados pelo Yahoo são dados correntes de 12 meses, não eventos persistidos.
- `fetch_fundamentals` existe e devolve `FundamentalData` pontual; `fetch_historical_fundamentals` segue disponível para o enriquecimento.

## Regras importantes

- Sempre preservar `source`, `price_date` e, quando disponível, preço ajustado.
- Não apresentar dado sem informar ou conseguir determinar sua data de mercado.
- Não esconder erro de importação como se fosse atualização concluída.
- Antes de alterar fonte ou regra de prioridade, verificar impacto no dataset de treinamento.

## Alternativas gratuitas avaliadas (2026-10)

| Fonte | Custo | Dados B3 | Limites free | Papel no Midas |
|---|---|---|---|---|
| `yahoo.finance` (`yfinance`) | Free (não oficial) | Ações/FIIs com sufixo `.SA`; dividendos | Não documentado; throttle possível | **Primária de preços** |
| `brapi.dev` | Free + planos | Nativo: ações, FIIs, opções, TD, macro, câmbio, cripto | Key free com quota; sem key só `PETR4`/`VALE3`/`MGLU3`/`ITUB4`; 429 com `Retry-After` | **Fallback de preços** |
| BCB SGS (`api.bcb.gov.br`) | Free oficial | Macro (CDI, SELIC, IPCA) — não equities | Sem key | Benchmarks/macro |
| Alpha Vantage | Free key | Global; B3 inconsistente | ~25 req/dia; `outputsize=full` premium | Experimental (fundamentos) |
| Finnhub / Twelve Data / Marketstack | Free tier | B3 pobre ou ausente | 5–25 req/min, dezenas/dia | Não adotar para B3 |

### Decisão

- **Não trocar a brapi** agora: é a única free com FIIs, Tesouro Direto e macro brasileira de qualidade.
- Manter Yahoo primário + brapi fallback (política `SOURCE_POLICY`).
- BCB permanece para CDI/SELIC/IPCA (wealth/benchmarks).
- Não existe substituto gratuito **oficial** da B3 para cotações; dados em tempo real são pagos.

### Pontos de atenção

- Yahoo pode throttle/bloquear sem aviso — o fallback brapi e o outcome `partial` cobrem isso.
- Alpha Vantage não cobre B3 de forma confiável; não virar fonte principal.
- Qualquer nova fonte precisa de `source`/`price_date` e entrada em `SOURCE_POLICY` + testes de fallback.

## Pontos de código

- `midas_core/domain/market_quality.py`
- `midas_core/application/market_quality.py`
- `midas_core/infrastructure/brapi.py`
- `midas_core/infrastructure/yahoo.py`
- `midas_core/application/market_import.py`
- `midas_core/application/market_import_yahoo.py`
- `midas_core/infrastructure/repositories.py`
- `midas_core/application/analysis.py`
- `test_market_quality.py`
