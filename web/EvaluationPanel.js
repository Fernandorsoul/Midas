import { number, percent } from './format.js';
import { h } from './ui.js';

export function EvaluationPanel({ data }) {
  const metrics = data?.metrics;
  const note = metrics
    ? data.model_validated
      ? `Modelo passou os critérios: ${metrics.train} amostras de treino, ${metrics.validation} de validação e ${metrics.test} de teste.`
      : 'O ganho sobre a referência não atingiu o mínimo de 2% ou o ranking foi fraco. Nenhum ativo será marcado como candidato.'
    : data?.dataset_count
      ? 'Nenhum experimento salvo para este horizonte.'
      : 'Nenhum dataset real cadastrado no MongoDB.';

  return h('section', { id: 'metodo', className: 'method' },
    h('div', null,
      h('div', { className: 'eyebrow' }, 'COMO A VALIDAÇÃO FUNCIONA'),
      h('h2', null, 'Doze meses de contexto.', h('br'), 'Doze meses sem respostas.'),
      h('p', null, 'Cada amostra usa somente momentum, volatilidade e drawdown calculados até a data da previsão. O alvo é o retorno ajustado nos 12 meses seguintes.'),
      h('p', null, 'Treino e seleção aceitam apenas resultados que já teriam terminado antes do período avaliado. As previsões finais são comparadas linha a linha com retornos reais.'),
    ),
    h('div', { className: 'evaluation' },
      h('h3', null, 'Validação temporal mais recente'),
      h(MetricLine, { label: 'Erro absoluto médio do modelo', value: percent(metrics?.mae) }),
      h(MetricLine, { label: 'Erro da referência simples', value: percent(metrics?.baseline_mae) }),
      h(MetricLine, { label: 'Melhora relativa sobre a referência', value: percent(metrics?.mae_improvement) }),
      h(MetricLine, { label: 'Acerto da direção', value: percent(metrics?.directional_accuracy) }),
      h(MetricLine, { label: 'Correlação média do ranking', value: number(metrics?.rank_correlation) }),
      h('p', null, note),
      h('small', null, 'As amostras mensais se sobrepõem e o universo atual contém 28 ativos. A tabela permite auditar os números usados nas métricas. Custos, impostos e execução não são simulados.'),
    ),
  );
}

function MetricLine({ label, value }) {
  return h('div', null, label, h('strong', null, value));
}
