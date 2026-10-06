import { saveFavorite } from './api.js';
import { categories, number, percent } from './format.js';
import { Sparkline } from './Sparkline.js';
import { DataTable, h, SectionTitle } from './ui.js';

export function AssetExplorer({ assets, filters, setFilters, horizon, setHorizon, status, setStatus, onFavoriteChange }) {
  const sectors = [...new Set(assets.map(asset => asset.sector))].sort();
  const query = filters.query.trim().toLocaleLowerCase('pt-BR');
  const filtered = assets.filter(asset =>
    (!query || `${asset.ticker} ${asset.name}`.toLocaleLowerCase('pt-BR').includes(query)) &&
    (!filters.category || categories[asset.category] === filters.category) &&
    (!filters.sector || asset.sector === filters.sector) &&
    (!filters.saved || asset.favorite) &&
    (!filters.candidates || asset.opportunity?.candidate)
  );
  const candidateCount = assets.filter(asset => asset.opportunity?.candidate).length;
  const computedStatus = filtered.length
    ? `${filtered.length} ativos exibidos · ${candidateCount} candidatos no universo analisado`
    : assets.length ? 'Nenhum ativo corresponde aos filtros.' : 'Nenhum ativo cadastrado. Importe dados para começar.';

  return h('section', { className: 'explorer' },
    h(SectionTitle, {
      title: 'Potenciais oportunidades',
      action: h('label', null, 'Horizonte', h('select', { value: horizon, onChange: event => setHorizon(Number(event.target.value)) },
        [12, 24, 36].map(value => h('option', { key: value, value }, `${value} meses`)),
      )),
    }, 'Ordenadas pelo sinal validado e pela estimativa do modelo.'),
    h('div', { className: 'filters' },
      h('label', { className: 'search' }, 'Buscar ativo', h('input', { value: filters.query, placeholder: 'Nome ou código do ativo', type: 'search', onChange: event => setFilters({ ...filters, query: event.target.value }) })),
      h('label', null, 'Categoria', h('select', { value: filters.category, onChange: event => setFilters({ ...filters, category: event.target.value }) },
        h('option', { value: '' }, 'Todas as categorias'),
        h('option', null, 'Ações'),
        h('option', null, 'FIIs'),
        h('option', null, 'Fiagros'),
      )),
      h('label', null, 'Setor', h('select', { value: filters.sector, onChange: event => setFilters({ ...filters, sector: event.target.value }) },
        h('option', { value: '' }, 'Todos os setores'),
        sectors.map(sector => h('option', { key: sector, value: sector }, sector)),
      )),
      h('label', { className: 'check' }, h('input', { checked: filters.candidates, type: 'checkbox', onChange: event => setFilters({ ...filters, candidates: event.target.checked }) }), ' Apenas candidatos'),
      h('label', { className: 'check' }, h('input', { checked: filters.saved, type: 'checkbox', onChange: event => setFilters({ ...filters, saved: event.target.checked }) }), ' Favoritos'),
    ),
    h('p', { id: 'status', role: 'status', 'aria-live': 'polite' }, status || computedStatus),
    h(DataTable, { headers: ['Ativo / setor', 'Categoria', 'Histórico', 'Preço', 'Desconto da máxima · 12m', 'Retorno passado · 12m', 'Volatilidade', 'Estimativa do modelo', 'Leitura', 'Salvar'] },
      filtered.map(asset => h(AssetRow, { key: asset.id, asset, onFavoriteChange, setStatus })),
    ),
  );
}

function AssetRow({ asset, onFavoriteChange, setStatus }) {
  async function toggleFavorite() {
    try {
      const result = await saveFavorite(asset.id, !asset.favorite);
      onFavoriteChange(asset.id, result.saved);
    } catch {
      setStatus('Não foi possível salvar o favorito no banco. Tente novamente.');
    }
  }
  const opportunity = asset.opportunity;
  return h('tr', { className: opportunity?.candidate ? 'candidate-row' : undefined },
    h('td', null, asset.ticker, h('small', null, `${asset.name} · ${asset.sector}`)),
    h('td', null, categories[asset.category] || asset.category),
    h('td', null, h(Sparkline, { values: asset.chart, label: `Histórico de fechamento de ${asset.ticker}` })),
    h('td', null, number(asset.price)),
    h('td', { className: opportunity?.drawdown < 0 ? 'negative' : undefined }, percent(opportunity?.drawdown)),
    h('td', { className: opportunity ? opportunity.momentum_12m >= 0 ? 'positive' : 'negative' : undefined }, percent(opportunity?.momentum_12m)),
    h('td', null, percent(opportunity?.volatility)),
    h('td', { className: opportunity ? opportunity.estimate >= 0 ? 'positive' : 'negative' : undefined }, percent(opportunity?.estimate), opportunity ? h('small', null, `Faixa: ${percent(opportunity.estimate_low)} a ${percent(opportunity.estimate_high)}`) : null),
    h('td', { className: opportunity?.candidate ? 'signal candidate' : 'signal' }, opportunity?.candidate ? 'Candidato' : 'Sem sinal'),
    h('td', null, h('button', { className: 'star', onClick: toggleFavorite, 'aria-label': `Favoritar ${asset.ticker}`, 'aria-pressed': String(asset.favorite) }, asset.favorite ? '★' : '☆')),
  );
}
