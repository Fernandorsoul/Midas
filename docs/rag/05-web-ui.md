# Módulo: interface web

## Responsabilidade

Interface React sem JSX, navegação, componentes, estilos e feedback do usuário.

## Páginas atuais

- Minha Carteira
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
- Treinamento possui dois pollers independentes: 1,2 s no console e 2 s no botão da carteira.

## Inconsistências que devem ser preservadas como limitações até correção

- O estado inicial de horizonte é 6, mas o seletor de ativos só oferece 12, 24 e 36 meses.
- A introdução e a página de método possuem texto fixo de 6 ou 12 meses, independentemente do horizonte ativo.
- O cabeçalho afirma Yahoo Finance embora análise e treinamento também usem brapi e dados enriquecidos.
- Erros ao adicionar/remover ou iniciar treino são enviados apenas ao console, sem feedback visual.
- O menu é ocultado em telas pequenas, sem uma alternativa de navegação móvel.

## Regras de UX

- Exibir carregamento, vazio, sucesso e erro de forma explícita.
- Não prometer atualização em segundo plano se a chamada bloquear a interface.
- Indicar fonte e data de mercado perto de dados sensíveis a atraso.
- Manter linguagem de pesquisa, não recomendação.
- Preservar acessibilidade: foco visível, rótulos e controles operáveis por teclado.

## Atenção técnica

Existem textos com codificação incorreta em arquivos web. Novos arquivos e correções devem usar UTF-8 corretamente.

## Pontos de código

- `web/app.js`
- `web/AssetExplorer.js`
- `web/layout.js`
- `web/ui.js`
- `web/api.js`
- `web/style.css`
