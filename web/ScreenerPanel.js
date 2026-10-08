import { getScreener } from './api.js';
import { React, useEffect, useState } from './react.js';
import { DataTable, h, SectionTitle } from './ui.js';

function pct(value) {
  if (value === null || value === undefined) return '—';
  return (Number(value) * 100).toFixed(1) + '%';
}

function money(value) {
  if (value === null || value === undefined) return '—';
  return 'R$ ' + Number(value).toFixed(2);
}

export function ScreenerPanel() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('');
  const [minVolume, setMinVolume] = useState('');

  async function load(params = {}) {
    setLoading(true);
    setError('');
    try {
      const mv = params.minVolume !== undefined ? params.minVolume : minVolume;
      setData(await getScreener({
        query: params.query || query,
        category: params.category || category,
        min_volume: mv,
      }));
    } catch (err) {
      setError(err.message || 'Falha ao carregar o screener.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  function applyFilters(event) {
    event.preventDefault();
    load({ query, category, minVolume });
  }

  return h('section', { className: 'screener' },
    h(SectionTitle, {
      eyebrow: 'TRIAGEM DE OPORTUNIDADES',
      title: 'Screener de pesquisa',
    }, 'Score transparente por critérios (momento, risco, volatilidade, liquidez e qualidade dos dados). Não é recomendação de compra/venda.'),
    error ? h('div', { className: 'notice error', role: 'alert' }, error) : null,
    h('form', { className: 'filters', onSubmit: applyFilters },
      h('label', { className: 'search' }, 'Buscar ativo',
        h('input', {
          type: 'search',
          value: query,
          placeholder: 'Ticker ou nome',
          onChange: e => setQuery(e.target.value),
        }),
      ),
      h('label', null, 'Categoria',
        h('select', { value: category, onChange: e => setCategory(e.target.value) },
          h('option', { value: '' }, 'Todas'),
          h('option', { value: 'stock' }, 'Ações'),
          h('option', { value: 'fii' }, 'FIIs'),
          h('option', { value: 'fiagro' }, 'Fiagros'),
        ),
      ),
      h('label', null, 'Volume mínimo',
        h('input', {
          type: 'number',
          min: '0',
          value: minVolume,
          placeholder: 'ex: 100000',
          onChange: e => setMinVolume(e.target.value),
        }),
      ),
      h('button', { type: 'submit', className: 'primary-action' }, 'Filtrar'),
    ),
    loading ? h('div', { className: 'loading' }, 'Calculando scores...') : null,
    data ? h('div', null,
      h('div', { className: 'notice' },
        h('strong', null, 'Como ler: '),
        'score 0–1 pondera critérios explícitos. ',
        h('em', null, data.disclaimer),
      ),
      h('p', { className: 'muted' },
        `${data.total_scored} ativos pontuados de ${data.universe ?? data.total_scored} no universo. ` +
        'Pesos: ' + Object.entries(data.criteria_weights || {}).map(([k, v]) => `${k} ${Math.round(v * 100)}%`).join(', '),
      ),
      data.results?.length ? h(DataTable, {
        headers: ['Score', 'Ativo', 'Preço', 'Fonte', 'Por quê'],
      }, data.results.map(item =>
        h('tr', { key: item.ticker },
          h('td', null, h('strong', null, item.score.toFixed(3))),
          h('td', { className: 'ticker-name' }, item.ticker),
          h('td', null, money(item.price)),
          h('td', null, item.source || '—', h('br'), h('small', null, item.price_date || '')),
          h('td', null,
            (item.explanation?.criteria || []).slice(0, 3).map(c =>
              h('div', { key: c.name, className: 'muted' }, `${c.note} (${Math.round(c.weight * 100)}%)`)
            ),
          ),
        )
      )) : h('div', { className: 'portfolio-empty' }, 'Nenhum ativo corresponde aos filtros.'),
    ) : null,
  );
}
