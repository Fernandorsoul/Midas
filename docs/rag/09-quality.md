# Módulo: qualidade e validação

## Responsabilidade

Testes, critérios de aceite, dados inválidos, observabilidade e regressões.

## Cobertura existente

Há testes de regras de análise, HTTP, importação e treinamento. Endpoints básicos possuem cobertura, incluindo validação de payload e origem em algumas rotas.

## Lacunas prioritárias

- Operações parciais, preço médio, taxas e P&L.
- Eventos de dividendos/JCP e data-com.
- Falhas, timeout e lacunas de provedores.
- Importações duplicadas e concorrência.
- Fluxos de interface: carregar, erro, vazio e sucesso.
- Contratos de novas rotas e autorização futura.

## Critérios de aceite transversais

- Não perder dados de usuário ao reiniciar.
- Não exibir cotação sem data/fonte verificável.
- Não mascarar falha como sucesso.
- Não criar sinais de investimento sem modelo validado.
- Não registrar nem expor segredos.
- Toda alteração de regra de negócio deve ter teste automatizado.

## Contratos cobertos para carteira

`test_http.py` isola PostgreSQL e Yahoo com mocks e cobre listagem, adição/importação, remoção, dividendos e relatório usando posições persistidas. A persistência real entre reinícios também deve ser validada no ambiente integrado antes de publicar uma versão.

## Pontos de código

- `test_analysis.py`
- `test_http.py`
- `test_market_api.py`
- `test_midas.py`
