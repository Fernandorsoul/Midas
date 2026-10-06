import { date, percent } from './format.js';
import { DataTable, h, SectionTitle } from './ui.js';

export function ValidationHistory({ predictions = [] }) {
  const ordered = [...predictions].sort((a, b) => b.as_of.localeCompare(a.as_of) || a.ticker.localeCompare(b.ticker));
  return h('section', { id: 'validacao', className: 'explorer validation-history' },
    h(SectionTitle, { eyebrow: 'BACKTEST SEM VISÃO DO FUTURO', title: 'Previsões históricas × resultados reais' },
      ordered.length ? `${ordered.length} previsões fora do treino comparadas com retornos reais já observados.` : 'Nenhuma previsão histórica disponível para este horizonte.',
    ),
    h(DataTable, { headers: ['Ativo', 'Data da previsão', 'Fim do horizonte', 'Previsão', 'Retorno real', 'Erro absoluto', 'Resultado'] },
      ordered.map(prediction => {
        const directionCorrect = (prediction.predicted >= 0) === (prediction.actual >= 0);
        return h('tr', { key: `${prediction.ticker}-${prediction.as_of}` },
          h('td', null, prediction.ticker),
          h('td', null, date(prediction.as_of)),
          h('td', null, date(prediction.label_end)),
          h('td', { className: prediction.predicted >= 0 ? 'positive' : 'negative' }, percent(prediction.predicted)),
          h('td', { className: prediction.actual >= 0 ? 'positive' : 'negative' }, percent(prediction.actual)),
          h('td', null, percent(prediction.absolute_error)),
          h('td', { className: directionCorrect ? 'positive' : 'negative' }, directionCorrect ? 'Direção correta' : 'Direção incorreta'),
        );
      }),
    ),
  );
}
