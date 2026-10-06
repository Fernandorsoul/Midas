async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(data.error || data.message || 'Falha na requisição.'), { response, data });
  }
  return data;
}

export const getAnalysis = horizon => request(`/api/analysis?horizon=${horizon}`);

export const getPortfolio = horizon => request(`/api/portfolio?horizon=${horizon}`);

export const getPortfolioList = () => request('/api/portfolio/list');

export const addToPortfolio = (ticker, quantity) => request('/api/portfolio/add', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ticker, quantity }),
});

export const removeFromPortfolio = ticker => request('/api/portfolio/remove', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ticker }),
});

export const saveFavorite = (assetId, saved) => request('/api/favorites', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ asset_id: assetId, saved }),
});

export const startTraining = horizon => request('/api/training', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ horizon }),
});

export const getTrainingStatus = () => request('/api/training/status');
