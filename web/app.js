import { getAnalysis, getPortfolio, getPortfolioList, addToPortfolio, removeFromPortfolio, getPortfolioDividends, startTraining, getTrainingStatus, getJob } from './api.js';
import { AssetExplorer } from './AssetExplorer.js';
import { EvaluationPanel } from './EvaluationPanel.js';
import { Layout } from './layout.js';
import { OperationsLedger } from './OperationsLedger.js';
import { createRoot, React, useEffect, useMemo, useState } from './react.js';
import { TrainingConsole } from './TrainingConsole.js';
import { ValidationHistory } from './ValidationHistory.js';
import { h, StatCard } from './ui.js';

// Portfolio Manager Component
function PortfolioManager({ portfolioList, portfolioData, onAdd, onRemove, loading }) {
  const [ticker, setTicker] = useState('');
  const [quantity, setQuantity] = useState(100);
  const [adding, setAdding] = useState(false);

  async function handleAdd() {
    if (!ticker.trim()) return;
    setAdding(true);
    try {
      await onAdd(ticker.trim().toUpperCase(), quantity);
      setTicker('');
      setQuantity(100);
    } finally {
      setAdding(false);
    }
  }

  return h('div', { className: 'portfolio-manager' },
    h('div', { className: 'portfolio-add' },
      h('input', {
        type: 'text',
        value: ticker,
        onChange: e => setTicker(e.target.value),
        placeholder: 'Ex: PETR4, VALE3, ITUB4',
        className: 'portfolio-input',
        onKeyPress: e => e.key === 'Enter' && handleAdd(),
      }),
      h('input', {
        type: 'number',
        value: quantity,
        onChange: e => setQuantity(Number(e.target.value)),
        min: 1,
        className: 'portfolio-input portfolio-quantity',
        placeholder: 'Quantidade',
      }),
      h('button', {
        className: 'primary-action',
        onClick: handleAdd,
        disabled: adding || !ticker.trim(),
      }, adding ? 'Adicionando...' : 'Adicionar à Carteira'),
    ),
    portfolioList.length > 0 ? h('div', { className: 'portfolio-list' },
      h('div', { className: 'portfolio-list-header' },
        h('span', null, 'Ativos na carteira'),
        h('span', { className: 'portfolio-count' }, portfolioList.length + ' ativos'),
      ),
      h('div', { className: 'portfolio-tickers' },
        portfolioList.map(t =>
          h('div', { key: t, className: 'portfolio-ticker-item' },
            h('span', { className: 'ticker-name' }, t),
            h('span', { className: 'ticker-qty' }, (portfolioData?.[t] || 100) + ' cotas'),
            h('button', {
              className: 'ticker-remove',
              onClick: () => onRemove(t),
              title: 'Remover da carteira',
            }, '\u00d7'),
          )
        ),
      ),
    ) : h('div', { className: 'portfolio-empty' },
      h('p', null, 'Nenhum ativo na carteira. Adicione ativos para análise.'),
    ),
  );
}

// Portfolio Page
function PortfolioPage({ portfolio, loading, horizon, portfolioList, portfolioData, dividends, onAdd, onRemove, onTrain, job }) {
  if (loading) return h('div', { className: 'loading' }, 'Carregando carteira...');
  
  const assets = portfolio?.portfolio || [];
  const validated = portfolio?.model_validated;
  const running = job?.status === 'queued' || job?.status === 'running';
  
  // Calcular totais de dividendos
  const totalDividends = Object.values(dividends || {}).reduce((sum, d) => sum + (d.total_dividends || 0), 0);
  const totalSharesFromDividends = Object.values(dividends || {}).reduce((sum, d) => sum + (d.shares_from_dividends || 0), 0);
  
  return h('section', { className: 'portfolio' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'MINHA CARTEIRA'),
        h('h2', null, 'An\u00e1lise dos seus ativos'),
        h('p', null, 'Horizonte de ' + horizon + ' meses. ' + assets.length + ' ativos analisados.'),
      ),
      h('div', { className: 'portfolio-actions' },
        h('button', {
          className: 'primary-action',
          onClick: () => onTrain(horizon),
          disabled: running || portfolioList.length === 0,
        }, running ? 'Treinando...' : 'Treinar com Carteira'),
      ),
    ),
    h(PortfolioManager, { portfolioList, portfolioData, onAdd, onRemove, loading }),
    h(OperationsLedger),
    // Dividend Summary
    totalDividends > 0 ? h('div', { className: 'dividend-summary' },
      h('div', { className: 'dividend-card' },
        h('div', { className: 'dividend-label' }, 'Total de Dividendos (12m)'),
        h('div', { className: 'dividend-value' }, 'R$ ' + totalDividends.toFixed(2)),
      ),
      h('div', { className: 'dividend-card' },
        h('div', { className: 'dividend-label' }, 'Cotas via Reinvestimento'),
        h('div', { className: 'dividend-value' }, totalSharesFromDividends + ' cotas'),
      ),
    ) : null,
    // Asset Cards
    assets.length > 0 ? h('div', { className: 'portfolio-grid' },
      assets.map((asset, index) => {
        const opp = asset.opportunity;
        const est = opp ? (opp.estimate * 100).toFixed(1) : '\u2014';
        const low = opp ? (opp.estimate_low * 100).toFixed(1) : '\u2014';
        const high = opp ? (opp.estimate_high * 100).toFixed(1) : '\u2014';
        const dd = opp ? (opp.drawdown * 100).toFixed(1) : '\u2014';
        const mom = opp ? (opp.momentum_12m * 100).toFixed(1) : '\u2014';
        const vol = opp ? (opp.volatility * 100).toFixed(1) : '\u2014';
        const isCandidate = opp?.candidate;
        const isValidated = opp?.validated;
        const div = dividends?.[asset.ticker];
        
        return h('div', { key: asset.ticker, className: 'portfolio-card' + (isCandidate ? ' candidate' : '') },
          h('div', { className: 'portfolio-header' },
            h('div', { className: 'portfolio-ticker' }, asset.ticker),
            h('div', { className: 'portfolio-price' }, 'R$ ' + (asset.price?.toFixed(2) || '\u2014')),
          ),
          h('div', { className: 'portfolio-name' }, asset.name),
          h('div', { className: 'market-meta', title: 'Fonte e data de mercado' },
            h('span', null, asset.source || 'sem fonte'),
            h('span', null, asset.price_date || 'sem data'),
            asset.market_data?.stale ? h('span', { className: 'badge not-validated' }, 'Atrasado') : null,
            asset.market_data?.quality === 'missing' ? h('span', { className: 'badge not-validated' }, 'Sem dados') : null,
          ),
          h('div', { className: 'portfolio-metrics' },
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Estimativa'),
              h('span', { className: 'value ' + (opp?.estimate >= 0 ? 'positive' : 'negative') }, est + '%'),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Faixa'),
              h('span', { className: 'value' }, low + '% a ' + high + '%'),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Drawdown'),
              h('span', { className: 'value ' + (dd < 0 ? 'negative' : '') }, dd + '%'),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Momentum 12m'),
              h('span', { className: 'value ' + (mom >= 0 ? 'positive' : 'negative') }, mom + '%'),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Volatilidade'),
              h('span', { className: 'value' }, vol + '%'),
            ),
          ),
          // Dividend Info
          div && div.status === 'ok' ? h('div', { className: 'dividend-info' },
            h('div', { className: 'dividend-row' },
              h('span', { className: 'label' }, 'Dividendo Anual'),
              h('span', { className: 'value' }, 'R$ ' + div.annual_dividend.toFixed(4)),
            ),
            h('div', { className: 'dividend-row' },
              h('span', { className: 'label' }, 'Dividend Yield'),
              h('span', { className: 'value' }, div.dividend_yield.toFixed(2) + '%'),
            ),
            h('div', { className: 'dividend-row' },
              h('span', { className: 'label' }, 'Total Dividendos'),
              h('span', { className: 'value' }, 'R$ ' + div.total_dividends.toFixed(2)),
            ),
            h('div', { className: 'dividend-row' },
              h('span', { className: 'label' }, 'Cotas via Reinvestimento'),
              h('span', { className: 'value' }, div.shares_from_dividends + ' cotas'),
            ),
          ) : null,
          h('div', { className: 'portfolio-status' },
            isCandidate ? h('span', { className: 'badge candidate' }, 'Candidato') : null,
            isValidated ? h('span', { className: 'badge validated' }, 'Validado') : null,
            !isValidated ? h('span', { className: 'badge not-validated' }, 'N\u00e3o validado') : null,
          ),
        );
      }),
    ) : null,
  );
}

// All Assets Page
function AssetsPage({ assets, loading, horizon, setHorizon, status, setStatus, onFavoriteChange, filters, setFilters }) {
  const candidateCount = useMemo(() => assets.filter(asset => asset.opportunity?.candidate).length, [assets]);

  return h(React.Fragment, null,
    h('section', { className: 'intro' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'PRE\u00c7O, TEND\u00caNCIA E RISCO'),
        h('h1', null, 'Oportunidades com', h('br'), 'evid\u00eancia vis\u00edvel', h('span', null, '.')),
        h('p', null, 'Treino temporal, previs\u00e3o de 6 meses e compara\u00e7\u00e3o', h('br'), 'com o retorno real observado posteriormente.'),
      ),
      h('div', { className: 'orbit', 'aria-hidden': 'true' }, h('span', null, '\u2726'), h('small', null, 'M\u00c9DIO & LONGO PRAZO')),
    ),
    h('div', { className: 'notice' }, h('strong', null, 'Ranking experimental, n\u00e3o recomenda\u00e7\u00e3o.'), ' O modelo n\u00e3o v\u00ea o retorno futuro durante o treino. Um sinal s\u00f3 \u00e9 liberado quando supera a refer\u00eancia por pelo menos 2% e apresenta correla\u00e7\u00e3o de ranking m\u00ednima de 0,10.'),
    h('section', { className: 'stats' },
      h(StatCard, { label: 'Ativos analisados', value: loading ? '\u2014' : String(assets.length), note: 'Universo atual do PostgreSQL' }),
      h(StatCard, { label: 'Horizonte do modelo', value: horizon + ' meses', note: 'Retorno ajustado acumulado' }),
      h(StatCard, { label: 'Candidatos atuais', value: loading ? '\u2014' : String(candidateCount), note: 'Somente modelo validado' }),
    ),
    h(AssetExplorer, { assets, filters, setFilters, horizon, setHorizon, status, setStatus, onFavoriteChange }),
  );
}

// Training Page
function TrainingPage({ horizon, job, setJob, onFinished }) {
  return h(TrainingConsole, { horizon, job, setJob, onFinished });
}

// Validation Page
function ValidationPage({ data }) {
  return h(React.Fragment, null,
    h(ValidationHistory, { predictions: data?.metrics?.predictions || [] }),
    h(EvaluationPanel, { data }),
  );
}

// Main App
function App() {
  const [currentPage, setCurrentPage] = useState('portfolio');
  const [horizon, setHorizon] = useState(6);
  const [data, setData] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioList, setPortfolioList] = useState([]);
  const [portfolioData, setPortfolioData] = useState({});
  const [dividends, setDividends] = useState({});
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('Consultando dados...');
  const [job, setJob] = useState({ status: 'idle', message: 'Nenhum treinamento em execu\u00e7\u00e3o.' });
  const [filters, setFilters] = useState({ query: '', category: '', sector: '', saved: false, candidates: false });

  async function load() {
    setLoading(true);
    setStatus('Consultando bancos de dados...');
    try {
      const [analysis, portfolioResult, portfolioListData, dividendsData] = await Promise.all([
        getAnalysis(horizon),
        getPortfolio(horizon),
        getPortfolioList(),
        getPortfolioDividends(),
      ]);
      setData(analysis);
      setAssets(analysis.assets || []);
      setPortfolio(portfolioResult);
      setPortfolioList(portfolioListData.tickers || []);
      setPortfolioData(portfolioListData.portfolio || {});
      setDividends(dividendsData.dividends || {});
      setStatus('');
    } catch {
      setData(null);
      setAssets([]);
      setPortfolio(null);
      setPortfolioList([]);
      setPortfolioData({});
      setDividends({});
      setStatus('Falha ao acessar os bancos. Verifique os servi\u00e7os e recarregue.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [horizon]);
  useEffect(() => { getTrainingStatus().then(setJob).catch(() => {}); }, []);

  function updateFavorite(assetId, saved) {
    setAssets(current => current.map(asset => asset.id === assetId ? { ...asset, favorite: saved } : asset));
  }

  async function handleAddTicker(ticker, quantity) {
    try {
      const result = await addToPortfolio(ticker, quantity);
      const job = result.job;
      if (!job?.id) return;
      setStatus(`Importando ${ticker}...`);
      const timer = setInterval(async () => {
        try {
          const next = await getJob(job.id);
          if (next.job.status === 'succeeded') {
            clearInterval(timer);
            const [listData, portfolioResult] = await Promise.all([
              getPortfolioList(),
              getPortfolio(horizon),
            ]);
            setPortfolioList(listData.tickers || []);
            setPortfolioData(listData.portfolio || {});
            setPortfolio(portfolioResult);
            setStatus('');
          } else if (next.job.status === 'failed' || next.job.status === 'cancelled') {
            clearInterval(timer);
            setStatus(next.job.error || 'Importação não concluída.');
          }
        } catch {
          clearInterval(timer);
          setStatus('Não foi possível acompanhar o job de importação.');
        }
      }, 1500);
    } catch (error) {
      console.error('Erro ao adicionar ativo:', error);
      setStatus(error.message || 'Falha ao enfileirar importação.');
    }
  }

  async function handleRemoveTicker(ticker) {
    try {
      const result = await removeFromPortfolio(ticker);
      setPortfolioList(result.tickers || []);
      setPortfolioData(result.portfolio || {});
      const portfolioResult = await getPortfolio(horizon);
      setPortfolio(portfolioResult);
    } catch (error) {
      console.error('Erro ao remover ativo:', error);
    }
  }

  async function handleTrainPortfolio(trainHorizon) {
    try {
      const result = await startTraining(trainHorizon);
      setJob(result);
      const jobId = result.id;
      const timer = setInterval(async () => {
        try {
          const next = jobId ? (await getJob(jobId)).job : await getTrainingStatus();
          setJob(next);
          if (next.status === 'succeeded' || next.status === 'finished') {
            clearInterval(timer);
            const portfolioResult = await getPortfolio(horizon);
            setPortfolio(portfolioResult);
          } else if (next.status === 'failed' || next.status === 'cancelled') {
            clearInterval(timer);
          }
        } catch {
          clearInterval(timer);
        }
      }, 2000);
    } catch (error) {
      console.error('Erro ao iniciar treinamento:', error);
    }
  }

  function renderPage() {
    switch (currentPage) {
      case 'portfolio':
        return h(PortfolioPage, { portfolio, loading, horizon, portfolioList, portfolioData, dividends, onAdd: handleAddTicker, onRemove: handleRemoveTicker, onTrain: handleTrainPortfolio, job });
      case 'assets':
        return h(AssetsPage, { assets, loading, horizon, setHorizon, status, setStatus, onFavoriteChange: updateFavorite, filters, setFilters });
      case 'training':
        return h(TrainingPage, { horizon, job, setJob, onFinished: load });
      case 'validation':
        return h(ValidationPage, { data });
      case 'method':
        return h(EvaluationPanel, { data });
      default:
        return h(PortfolioPage, { portfolio, loading, horizon, portfolioList, portfolioData, onAdd: handleAddTicker, onRemove: handleRemoveTicker, onTrain: handleTrainPortfolio, job });
    }
  }

  return h(Layout, { currentPage, onNavigate: setCurrentPage },
    h('header', null, 
      h('span', null, 'Seu observat\u00f3rio de investimentos'), 
      h('div', { className: 'header-actions' },
        h('span', { className: 'pill' }, '\u25cf Dados Yahoo Finance'),
      ),
    ),
    renderPage(),
    h('footer', null, 'MIDAS ', h('span', null, 'Pesquisa antes da decis\u00e3o. Paci\u00eancia antes do resultado.')),
  );
}

createRoot(document.getElementById('root')).render(h(App));