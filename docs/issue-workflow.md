# Execução do roadmap por issues

Este documento define como implementar as issues do Midas sem misturar escopo, perder contexto ou deixar o RAG desatualizado.

## Ordem de execução

1. [#1 — Carteira persistente](https://github.com/Fernandorsoul/Midas/issues/1)
2. [#2 — Livro de operações e P&L](https://github.com/Fernandorsoul/Midas/issues/2)
3. [#3 — Jobs persistidos](https://github.com/Fernandorsoul/Midas/issues/3)
4. [#4 — Qualidade e proveniência de dados](https://github.com/Fernandorsoul/Midas/issues/4)
5. [#5 — Interface: UTF-8, feedback e mobile](https://github.com/Fernandorsoul/Midas/issues/5)
6. [#6 — Dashboard e benchmarks](https://github.com/Fernandorsoul/Midas/issues/6)
7. [#7 — Artefatos quantitativos](https://github.com/Fernandorsoul/Midas/issues/7)
8. [#8 — Usuários e isolamento](https://github.com/Fernandorsoul/Midas/issues/8)

As issues 4 e 5 podem avançar em paralelo após a issue 1. As issues 2, 3 e 6 têm dependências funcionais e devem respeitar a ordem apresentada.

## Fronteiras de responsabilidade

| Issue | Pode alterar | Não deve assumir |
|---|---|---|
| #1 | schema mínimo de carteira, repositório, rotas atuais e testes | custo, preço médio, transações ou usuários |
| #2 | operações, cálculo de posição/P&L, telas e APIs de operações | benchmark, corretora ou multiusuário |
| #3 | jobs, worker, importação e treino assíncronos | plataforma distribuída externa |
| #4 | adaptadores de dados, metadados e qualidade | intraday ou fornecedor pago |
| #5 | `web/`, UX e acessibilidade | regras financeiras do domínio |
| #6 | agregações de carteira, gráficos e benchmarks | recomendação de investimento |
| #7 | treino, serialização e explicabilidade | sinais sem validação temporal |
| #8 | identidade, autorização e ownership | SSO ou permissões corporativas complexas |

## Passo a passo obrigatório por issue

1. Abra a issue e confirme objetivo, escopo, fora de escopo, dependências e critérios de aceite.
2. Leia `AGENTS.md` e `docs/rag/00-router.md`.
3. Recupere no máximo dois módulos RAG de domínio; carregue um terceiro somente se houver dependência explícita.
4. Declare no comentário/PR os módulos afetados e os arquivos que serão modificados.
5. Crie ou ajuste a migração antes de alterar código que dependa de schema novo. Nunca altere apenas o script de bootstrap para atualizar banco já existente.
6. Implemente primeiro regras de domínio/casos de uso, depois repositório/API e por último UI.
7. Adicione ou ajuste testes para caminho feliz, validação e falha relevante.
8. Execute verificações proporcionais: testes Python, validação de sintaxe web, migração em banco de desenvolvimento e fluxo manual de UI quando houver tela.
9. Atualize o módulo RAG dono da mudança, além de API/persistência/qualidade quando aplicável.
10. Execute `python scripts/index_rag.py` com `rag-postgres` ativo para reindexar a documentação.
11. Faça commit pequeno com a referência da issue, por exemplo `feat(portfolio): persist positions (#1)`.
12. Abra PR ou envie o commit, registre evidências de teste e feche a issue somente quando todos os critérios de aceite forem atendidos.

## Definition of Done

Uma issue só está concluída quando:

- todas as fronteiras foram respeitadas;
- schema e migração são compatíveis com instalação nova e existente;
- testes novos e existentes relevantes passam;
- falhas não expõem segredos nem mascaram erro como sucesso;
- UI, API e documentação descrevem o mesmo comportamento;
- módulos RAG foram atualizados e indexados;
- o comentário final da issue contém resumo, testes executados, limitações remanescentes e links de PR/commit.
