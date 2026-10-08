# Módulo: interface web

## Responsabilidade

Interface React sem JSX, navegação, componentes, estilos e feedback do usuário.

## Páginas atuais

- Minha Carteira (inclui livro de operações: formulário, histórico e resumo de posição/P&L)
- Todos os Ativos
- Treinamento
- Validação
- Método

## Fluxo e estado confirmados

- `App` mantém página, horizonte, análise, carteira, favoritos/filtros, dividendos e job no estado local React.
- O carregamento inicial e toda troca de horizonte executam em paralelo análise, relatório da carteira, lista da carteira e dividendos.
- A navegação é estado local; hashes são alterados em links, mas não existe roteamento nem restauração de página pelo URL.
- O explorador permite busca por ticker/nome, categoria, setor, candidatos e favoritos; não há ordenação de colunas nem paginação.
- Favoritar atualiza somente `assets` em memória; a página de carteira não é recarregada por essa ação.
- A tela de validação renderiza as previsões que vêm nas métricas do relatório de análise para o horizonte ativo.
- Treinamento e importação usam jobs persistidos: a UI não bloqueia, faz polling resiliente por `job_id`, mostra progresso e oferece cancelar/reexecutar.

## Inconsistências que devem ser preservadas como limitações até correção

- Favoritar atualiza somente `assets` em memória; a página de carteira não é recarregada por essa ação.
- Não há ordenação de colunas nem paginação no explorador.
- Hashes mudam em links, mas não há roteamento completo por URL.

## Fluxos corrigidos (issue #5)

- Arquivos web salvos em UTF-8 válido (inclusive `style.css`, que tinha bytes Latin-1).
- Toasts para sucesso/erro de carteira, importação e treino; status também visível na página.
- Navegação móvel com botão hamburger, backdrop e `aside` deslizante; `aria-label`/`aria-expanded`.
- Horizonte unificado: seletor inclui 6/12/24/36 e textos usam o horizonte ativo.
- Cabeçalho informa fontes do pipeline (Yahoo Finance · brapi.dev).

## Regras de UX

- Exibir carregamento, vazio, sucesso e erro de forma explícita.
- Não prometer atualização em segundo plano se a chamada bloquear a interface.
- Indicar fonte e data de mercado perto de dados sensíveis a atraso.
- Manter linguagem de pesquisa, não recomendação.
- Preservar acessibilidade: foco visível, rótulos e controles operáveis por teclado.

## Atenção técnica

Novos arquivos e correções devem usar UTF-8 sem BOM. Verificar `style.css` após appends no Windows (PowerShell pode gravar Latin-1).

## Pontos de código

- `web/app.js`
- `web/AssetExplorer.js`
- `web/OperationsLedger.js`
- `web/TrainingConsole.js`
- `web/layout.js`
- `web/ui.js`
- `web/api.js`
- `web/style.css`
