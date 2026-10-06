async function request(path, options = {}) {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw Object.assign(new Error(data.error || data.message || 'Falha na requisição.'), { response, data });
  }
  return data;
}

export const getAnalysis = horizon => request(`/api/analysis?horizon=${horizon}`);

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
