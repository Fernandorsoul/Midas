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

export const startTraining = horizon => request('/api/training', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ horizon }),
});

export const removeFromPortfolio = ticker => request('/api/portfolio/remove', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ ticker }),
});

export const getPortfolioDividends = () => request('/api/portfolio/dividends');

export const getJob = jobId => request(`/api/jobs?job_id=${jobId}`);

export const listJobs = (type, limit = 10) => request(
  `/api/jobs?limit=${limit}${type ? `&type=${encodeURIComponent(type)}` : ''}`
);

export const cancelJob = jobId => request('/api/jobs/cancel', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id: jobId }),
});

export const retryJob = jobId => request('/api/jobs/retry', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id: jobId }),
});

export const createJob = payload => request('/api/jobs', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const getPortfolioOperations = ticker => request(
  `/api/portfolio/operations${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ''}`
);

export const getPortfolioPositions = ticker => request(
  `/api/portfolio/positions${ticker ? `?ticker=${encodeURIComponent(ticker)}` : ''}`
);

export const getWealthDashboard = () => request('/api/wealth/dashboard');

export const createPortfolioOperation = payload => request('/api/portfolio/operations', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const updatePortfolioOperation = payload => request('/api/portfolio/operations', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(payload),
});

export const deletePortfolioOperation = id => request('/api/portfolio/operations/delete', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ id }),
});

export const saveFavorite = (assetId, saved) => request('/api/favorites', {
  method: 'PUT',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ asset_id: assetId, saved }),
});

export const getTrainingStatus = () => request('/api/training/status');
