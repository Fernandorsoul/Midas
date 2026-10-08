import { getWealthDashboard } from './api.js';
import { React, useEffect, useState } from './react.js';
import { h, StatCard } from './ui.js';

function money(value) {
  if (value === null || value === undefined) return '—';
  return 'R$ ' + Number(value).toFixed(2);
}

function pct(value) {
  if (value === null || value === undefined) return '—';
  return (Number(value) * 100).toFixed(2) + '%';
}

function MiniChart({ points, label }) {
  if (!points || points.length < 2) {
    return h('div', { className: 'chart-empty' }, label + ': sem pontos suficientes.');
  }
  const values = points.map(p => p.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const width = 280;
  const height = 72;
  const step = width / Math.max(1, points.length - 1);
  const path = points.map((p, i) => {
    const x = i * step;
    const y = height - ((p.value - min) / span) * (height - 8) - 4;
    return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
  }).join(' ');
  return h('div', { className: 'mini-chart', title: label },
    h('svg', { viewBox: `0 0 ${width} ${height}`, width: '100%', height: height, role: 'img', 'aria-label': label },
      h('path', { d: path, fill: 'none', stroke: '#dbbd79', strokeWidth: '2' }),
    ),
    h('small', null, label),
  );
}

export function WealthDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    setError('');
    try {
      setData(await getWealthDashboard());
    } catch (err) {
      setError(err.message || 'Falha ao carregar dashboard patrimonial.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) return h('div', { className: 'loading' }, 'Carregando patrimônio...');
  if (error) return h('div', { className: 'notice error', role: 'alert' }, error);
  if (!data) return null;

  const wealth = data.wealth || {};
  const returns = data.returns || {};
  const benchmarks = data.benchmarks || {};
  const alloc = Object.entries(data.allocation || {}).sort((a, b) => b[1] - a[1]).slice(0, 6);

  return h('section', { className: 'wealth-dashboard' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'PATRIMÔNIO'),
        h('h2', null, 'Evolução e comparação'),
        h('p', null, 'Aportes não distorcem o retorno da estratégia (TWR). O retorno pessoal (XIRR) considera o fluxo de caixa.'),
      ),
    ),
    h('div', { className: 'stats' },
      h(StatCard, { label: 'Valor de mercado', value: money(wealth.market_value), note: 'Posições a preço de mercado' }),
      h(StatCard, { label: 'Aportes líquidos', value: money(wealth.net_contribution), note: 'Depósitos − retiradas' }),
      h(StatCard, { label: 'Retorno da estratégia (TWR)', value: pct(returns.twr), note: 'Sem efeito de aportes' }),
      h(StatCard, { label: 'Retorno pessoal (XIRR)', value: pct(returns.xirr), note: returns.has_cash_flow ? 'Com fluxo de caixa' : 'Sem fluxo de caixa' }),
    ),
    h('div', { className: 'wealth-grid' },
      h('div', { className: 'wealth-panel' },
        h('h3', null, 'Alocação atual'),
        alloc.length === 0 ? h('p', null, 'Sem posições abertas.') :
          h('ul', { className: 'alloc-list' }, alloc.map(([ticker, weight]) =>
            h('li', { key: ticker },
              h('span', { className: 'ticker-name' }, ticker),
              h('span', null, (Number(weight) * 100).toFixed(1) + '%'),
            )
          )),
        h('p', { className: 'muted' }, 'Proventos: ' + money(data.income?.gross_income) + ' · Despesas: ' + money(data.income?.expenses)),
      ),
      h('div', { className: 'wealth-panel' },
        h('h3', null, 'Patrimônio vs benchmarks (rebased 100)'),
        h(MiniChart, { points: data.equity_curve, label: 'Carteira' }),
        h(MiniChart, { points: benchmarks.cdi?.points, label: 'CDI — ' + (benchmarks.cdi?.source || 'indisponível') }),
        h(MiniChart, { points: benchmarks.ibovespa?.points, label: 'Ibovespa — ' + (benchmarks.ibovespa?.source || 'indisponível') }),
        h('p', { className: 'muted' },
          'Período ' + (benchmarks.period?.start || '—') + ' a ' + (benchmarks.period?.end || '—') +
          ' · atualizado em ' + (benchmarks.updated_at || '—') + '. ' + (benchmarks.note || ''),
        ),
      ),
    ),
    h('div', { className: 'notice' },
      h('strong', null, 'Reconciliação: '),
      'P&L das posições ' + money(data.reconciliation?.positions_total_pnl) +
      ' · valor de mercado ' + money(data.reconciliation?.positions_market_value) +
      '. Valores consolidados a partir do livro de operações.',
    ),
  );
}
