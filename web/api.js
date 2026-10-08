const TOKEN_KEY = 'midas_token';
const USER_KEY = 'midas_user';

export function getSessionToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; }
}

export function getSessionUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

export function setSession(token, user) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch { /* ignore */ }
}

export function clearSession() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch { /* ignore */ }
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getSessionToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const response = await fetch(path, { ...options, headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = data.error || data.message || 'Falha na requisição.';
    const error = Object.assign(new Error(message), { response, data, status: response.status });
    if (response.status === 401 && !path.startsWith('/api/auth/')) {
      error.requiresAuth = true;
    }
    throw error;
  }
  return data;
}

export const registerUser = (email, password) => request('/api/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password }),
});

export const loginUser = async (email, password) => {
  const data = await request('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  setSession(data.token, data.user);
  return data;
};

export const logoutUser = async () => {
  try {
    await request('/api/auth/logout', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
  } finally {
    clearSession();
  }
};

export const getCurrentUser = () => request('/api/auth/me');

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

export const getScreener = (params = {}) => {
  const qs = new URLSearchParams();
  if (params.query) qs.set('query', params.query);
  if (params.category) qs.set('category', params.category);
  if (params.min_volume) qs.set('min_volume', String(params.min_volume));
  if (params.limit) qs.set('limit', String(params.limit));
  const suffix = qs.toString() ? `?${qs}` : '';
  return request(`/api/screener${suffix}`);
};

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
