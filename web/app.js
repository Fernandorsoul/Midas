import { getAnalysis, getPortfolio, getPortfolioList, addToPortfolio, removeFromPortfolio, getTrainingStatus } from './api.js';
import { AssetExplorer } from './AssetExplorer.js';
import { EvaluationPanel } from './EvaluationPanel.js';
import { Layout } from './layout.js';
import { createRoot, React, useEffect, useMemo, useState } from './react.js';
import { TrainingConsole } from './TrainingConsole.js';
import { ValidationHistory } from './ValidationHistory.js';
import { h, StatCard } from './ui.js';

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

function PortfolioView({ portfolio, loading, horizon, portfolioList, portfolioData, onAdd, onRemove }) {
  if (loading) return h('div', { className: 'loading' }, 'Carregando carteira...');
  
  const assets = portfolio?.portfolio || [];
  const validated = portfolio?.model_validated;
  
  return h('section', { className: 'portfolio' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'MINHA CARTEIRA'),
        h('h2', null, 'An\u00e1lise dos seus ativos'),
        h('p', null, 'Horizonte de ' + horizon + ' meses. ' + assets.length + ' ativos analisados.'),
      ),
    ),
    h(PortfolioManager, { portfolioList, portfolioData, onAdd, onRemove, loading }),
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
        
        return h('div', { key: asset.ticker, className: 'portfolio-card' + (isCandidate ? ' candidate' : '') },
          h('div', { className: 'portfolio-header' },
            h('div', { className: 'portfolio-ticker' }, asset.ticker),
            h('div', { className: 'portfolio-price' }, 'R$ ' + (asset.price?.toFixed(2) || '\u2014')),
          ),
          h('div', { className: 'portfolio-name' }, asset.name),
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

function App() {
  const [horizon, setHorizon] = useState(6);
  const [data, setData] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [portfolioList, setPortfolioList] = useState([]);
  const [portfolioData, setPortfolioData] = useState({});
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('Consultando dados...');
  const [job, setJob] = useState({ status: 'idle', message: 'Nenhum treinamento em execu\u00e7\u00e3o.' });
  const [filters, setFilters] = useState({ query: '', category: '', sector: '', saved: false, candidates: false });
  const [view, setView] = useState('portfolio');

  async function load() {
    setLoading(true);
    setStatus('Consultando bancos de dados...');
    try {
      const [analysis, portfolioResult, portfolioListData] = await Promise.all([
        getAnalysis(horizon),
        getPortfolio(horizon),
        getPortfolioList(),
      ]);
      setData(analysis);
      setAssets(analysis.assets || []);
      setPortfolio(portfolioResult);
      setPortfolioList(portfolioListData.tickers || []);
      setPortfolioData(portfolioListData.portfolio || {});
      setStatus('');
    } catch {
      setData(null);
      setAssets([]);
      setPortfolio(null);
      setPortfolioList([]);
      setPortfolioData({});
      setStatus('Falha ao acessar os bancos. Verifique os servi\u00e7os e recarregue.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [horizon]);
  useEffect(() => { getTrainingStatus().then(setJob).catch(() => {}); }, []);

  const candidateCount = useMemo(() => assets.filter(asset => asset.opportunity?.candidate).length, [assets]);

  function updateFavorite(assetId, saved) {
    setAssets(current => current.map(asset => asset.id === assetId ? { ...asset, favorite: saved } : asset));
  }

  async function handleAddTicker(ticker, quantity) {
    try {
      const result = await addToPortfolio(ticker, quantity);
      setPortfolioList(result.tickers || []);
      setPortfolioData(result.portfolio || {});
      const portfolioResult = await getPortfolio(horizon);
      setPortfolio(portfolioResult);
    } catch (error) {
      console.error('Erro ao adicionar ativo:', error);
    }
  }

  async function handleRemoveTicker(ticker) {
    try {
      const result = await removeFromPortfolio(ticker);
      setPortfolioList(result.tickers || []);
      const portfolioData = await getPortfolio(horizon);
      setPortfolio(portfolioData);
    } catch (error) {
      console.error('Erro ao remover ativo:', error);
    }
  }

  return h(Layout, null,
    h('header', null, 
      h('span', null, 'Seu observat\u00f3rio de investimentos'), 
      h('div', { className: 'header-actions' },
        h('span', { className: 'pill' }, '\u25cf Dados Yahoo Finance'),
        h('div', { className: 'view-toggle' },
          h('button', { 
            className: 'toggle-btn' + (view === 'portfolio' ? ' active' : ''),
            onClick: () => setView('portfolio')
          }, 'Minha Carteira'),
          h('button', { 
            className: 'toggle-btn' + (view === 'all' ? ' active' : ''),
            onClick: () => setView('all')
          }, 'Todos os Ativos'),
        ),
      ),
    ),
    view === 'portfolio' ? 
      h(PortfolioView, { portfolio, loading, horizon, portfolioList, portfolioData, onAdd: handleAddTicker, onRemove: handleRemoveTicker }) :
      h(React.Fragment, null,
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
        h(AssetExplorer, { assets, filters, setFilters, horizon, setHorizon, status, setStatus, onFavoriteChange: updateFavorite }),
      ),
    h(TrainingConsole, { horizon, job, setJob, onFinished: load }),
    h(ValidationHistory, { predictions: data?.metrics?.predictions || [] }),
    h(EvaluationPanel, { data }),
    h('footer', null, 'MIDAS ', h('span', null, 'Pesquisa antes da decis\u00e3o. Paci\u00eancia antes do resultado.')),
  );
}

createRoot(document.getElementById('root')).render(h(App));