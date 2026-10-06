import { saveFavorite } from './api.js';
import { sparkline } from './charts.js';
import { categories, cell, number, percent } from './format.js';

export function renderAssets({ assets, elements, onFavoriteError }) {
  const query = elements.search.value.trim().toLocaleLowerCase('pt-BR');
  const filtered = assets.filter(asset =>
    (!query || `${asset.ticker} ${asset.name}`.toLocaleLowerCase('pt-BR').includes(query)) &&
    (!elements.category.value || categories[asset.category] === elements.category.value) &&
    (!elements.sector.value || asset.sector === elements.sector.value) &&
    (!elements.saved.checked || asset.favorite) &&
    (!elements.candidates.checked || asset.opportunity?.candidate)
  );

  elements.assets.replaceChildren();
  for (const asset of filtered) {
    const row = document.createElement('tr');
    if (asset.opportunity?.candidate) row.classList.add('candidate-row');

    const title = cell(row, asset.ticker);
    const detail = document.createElement('small');
    detail.textContent = `${asset.name} · ${asset.sector}`;
    title.append(detail);

    cell(row, categories[asset.category] || asset.category);
    const chart = cell(row, '—');
    if (asset.chart.length > 1) {
      chart.textContent = '';
      chart.append(sparkline(asset.chart, `Histórico de fechamento de ${asset.ticker}`));
    }

    cell(row, number(asset.price));
    const drawdown = cell(row, percent(asset.opportunity?.drawdown));
    if (asset.opportunity?.drawdown < 0) drawdown.className = 'negative';

    const momentum = cell(row, percent(asset.opportunity?.momentum_12m));
    if (asset.opportunity) momentum.className = asset.opportunity.momentum_12m >= 0 ? 'positive' : 'negative';

    cell(row, percent(asset.opportunity?.volatility));
    const estimate = cell(row, percent(asset.opportunity?.estimate));
    if (asset.opportunity) {
      estimate.className = asset.opportunity.estimate >= 0 ? 'positive' : 'negative';
      const range = document.createElement('small');
      range.textContent = `Faixa: ${percent(asset.opportunity.estimate_low)} a ${percent(asset.opportunity.estimate_high)}`;
      estimate.append(range);
    }

    const reading = cell(row, asset.opportunity?.candidate ? 'Candidato' : 'Sem sinal');
    reading.className = asset.opportunity?.candidate ? 'signal candidate' : 'signal';

    const button = document.createElement('button');
    button.className = 'star';
    button.textContent = asset.favorite ? '★' : '☆';
    button.setAttribute('aria-label', `Favoritar ${asset.ticker}`);
    button.setAttribute('aria-pressed', String(asset.favorite));
    button.onclick = async () => {
      button.disabled = true;
      try {
        asset.favorite = (await saveFavorite(asset.id, !asset.favorite)).saved;
        renderAssets({ assets, elements, onFavoriteError });
      } catch {
        onFavoriteError();
        button.disabled = false;
      }
    };
    cell(row, '').append(button);
    elements.assets.append(row);
  }

  const candidates = assets.filter(asset => asset.opportunity?.candidate).length;
  elements.opportunityCount.textContent = String(candidates);
  elements.status.textContent = filtered.length
    ? `${filtered.length} ativos exibidos · ${candidates} candidatos no universo analisado`
    : assets.length ? 'Nenhum ativo corresponde aos filtros.' : 'Nenhum ativo cadastrado. Importe dados para começar.';
}
