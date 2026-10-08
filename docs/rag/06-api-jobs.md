# Módulo: API HTTP e jobs

## Responsabilidade

Contratos HTTP locais, validação de entrada, status de tarefas e tratamento de erros.

## Rotas atuais

| Rota | Objetivo |
|---|---|
| `GET /api/analysis?horizon=` | Ranking e métricas do modelo |
| `GET /api/portfolio?horizon=` | Relatório da carteira atual |
| `GET /api/portfolio/list` | Tickers e quantidades persistidos |
| `POST /api/portfolio/add` | Enfileira job de importação (202) |
| `POST /api/portfolio/remove` | Remove ticker da lista |
| `GET /api/portfolio/dividends` | Consulta dividendos atuais |
| `GET /api/portfolio/operations` | Histórico do livro de operações |
| `POST /api/portfolio/operations` | Lança operação (201) |
| `PUT /api/portfolio/operations` | Edição controlada de operação |
| `POST /api/portfolio/operations/delete` | Exclui operação revalidando o livro |
| `GET /api/portfolio/positions` | Posição, custo, P&L e retorno total |
| `PUT /api/favorites` | Altera favorito |
| `POST /api/training` | Enfileira job de treinamento (202) |
| `GET /api/training/status` | Último job de treino persistido |
| `GET /api/jobs` | Lista jobs (`?type=`, `?limit=`) |
| `GET /api/jobs?job_id=` | Consulta um job |
| `POST /api/jobs` | Cria job `training` ou `import` (202) |
| `POST /api/jobs/cancel` | Cancela job queued/running |
| `POST /api/jobs/retry` | Reexecuta job failed/cancelled (202) |

## Jobs persistidos

- Estados: `queued` → `running` → `succeeded` | `failed` | `cancelled`.
- Tipos: `training` e `import`. Payload mínimo no JSONB; resultado em `result`.
- Um único treinamento ativo (fila ou execução) — índice parcial único; segundo pedido recebe 409.
- Importações concorrentes de tickers diferentes são permitidas.
- `cancel_requested` marca running; o worker interrompe no próximo checkpoint.
- `retry` cria um novo job a partir do payload do original.
- Erros persistidos são mensagens seguras (`safe_error_message`), sem stack/token.

## Worker

- `midas_core/worker.py` (serviço `worker` no compose) e thread embutida no `run_server`.
- Reivindicação com `FOR UPDATE SKIP LOCKED` — vários workers não duplicam execução.
- No start, jobs `running` órfãos são reenfileirados (`requeue_interrupted_jobs`).
- Passos de progresso: treino `dataset`/`training`; importação `import`/`portfolio`.

## Comportamento confirmado

- Respostas JSON usam `Cache-Control: no-store`; payloads mutáveis exigem JSON com até 4 KiB.
- Rotas mutáveis comparam o cabeçalho `Origin` com o próprio `Host`; origem diferente recebe 403.
- `POST /api/training` aceita 6, 12, 24 ou 36 meses; concorrência retorna 409 com mensagem segura.
- Job persiste no PostgreSQL e é consultável após reinício da aplicação.
- `POST /api/portfolio/add` não bloqueia: devolve 202 com job; a UI acompanha por polling.
- Operações de carteira validam tipo, data, moeda, ticker e valores; venda acima da posição retorna 400.
- Indisponibilidade do PostgreSQL retorna 503 nas rotas HTTP.

## Pontos de entrada auxiliares

- `midas.py` inicia o servidor HTTP (com worker embutido).
- `midas_core/worker.py` executa apenas o worker dedicado.
- `midas_core/interfaces/cli.py` oferece importação brapi/Yahoo, dataset e treino por CLI.

## Regras

- Validar tipo e faixa de todos os campos de entrada.
- Retornar JSON e códigos HTTP coerentes.
- Não expor exceções, tokens ou detalhes sensíveis ao cliente.
- Toda nova rota deve ter contrato documentado e teste correspondente.

## Pontos de código

- `midas_core/interfaces/http.py`
- `midas_core/application/jobs.py`
- `midas_core/domain/jobs.py`
- `midas_core/worker.py`
- `web/api.js`
- `web/TrainingConsole.js`
- `test_http.py`
- `test_jobs.py`
