# Módulo: API HTTP e jobs

## Responsabilidade

Contratos HTTP locais, validação de entrada, status de tarefas e tratamento de erros.

## Rotas atuais

| Rota | Objetivo |
|---|---|
| `GET /api/analysis?horizon=` | Ranking e métricas do modelo |
| `GET /api/portfolio?horizon=` | Relatório da carteira atual |
| `GET /api/portfolio/list` | Tickers e quantidades persistidos |
| `POST /api/portfolio/add` | Adiciona/atualiza ticker e importa dados |
| `POST /api/portfolio/remove` | Remove ticker da lista |
| `GET /api/portfolio/dividends` | Consulta dividendos atuais |
| `PUT /api/favorites` | Altera favorito |
| `POST /api/training` | Enfileira treinamento em thread |
| `GET /api/training/status` | Estado em memória do treinamento |

## Limitações atuais

Status de treinamento e tarefas não sobrevivem a reinício. O processamento em threads serve ao protótipo, mas deve evoluir para jobs persistidos e worker separado. A carteira padrão já sobrevive a reinícios no PostgreSQL.

## Comportamento confirmado

- Respostas JSON usam `Cache-Control: no-store`; payloads mutáveis exigem JSON com até 4 KiB.
- Rotas mutáveis comparam o cabeçalho `Origin` com o próprio `Host`; origem diferente recebe 403.
- Treinamento aceita somente 6, 12, 24 ou 36 meses, rejeita treino concorrente com 409 e atualiza `TRAINING_JOB` protegido por lock.
- O job percorre os passos `queued`, `dataset`, `training`, `done` ou `failed`; o erro é mantido no estado em memória.
- Ao iniciar treino pela interface, a presença de carteira filtra os tickers do dataset; sem carteira, usa todo o universo.
- `POST /api/portfolio/add` importa o ticker no Yahoo de forma síncrona e persiste a posição somente após o sucesso da importação.
- `GET /api/portfolio/list`, `POST /api/portfolio/remove` e `GET /api/portfolio/dividends` leem as posições persistidas; indisponibilidade do PostgreSQL retorna 503 nas rotas HTTP.
- Dividendos são consultados sequencialmente no Yahoo a cada `GET /api/portfolio/dividends`; falhas do provedor são retornadas por ticker em vez de falhar a resposta completa.

## Pontos de entrada auxiliares

- `midas.py` apenas inicia o servidor HTTP.
- `midas_core/interfaces/cli.py` oferece importação brapi/Yahoo, publicação de dataset e treino de snapshot por linha de comando.

## Regras

- Validar tipo e faixa de todos os campos de entrada.
- Retornar JSON e códigos HTTP coerentes.
- Não expor exceções, tokens ou detalhes sensíveis ao cliente.
- Toda nova rota deve ter contrato documentado e teste correspondente.

## Pontos de código

- `midas_core/interfaces/http.py`
- `web/api.js`
- `test_http.py`
