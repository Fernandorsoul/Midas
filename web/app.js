import { getAnalysis, getPortfolio, getTrainingStatus } from './api.js';
import { AssetExplorer } from './AssetExplorer.js';
import { EvaluationPanel } from './EvaluationPanel.js';
import { Layout } from './layout.js';
import { createRoot, React, useEffect, useMemo, useState } from './react.js';
import { TrainingConsole } from './TrainingConsole.js';
import { ValidationHistory } from './ValidationHistory.js';
import { h, StatCard } from './ui.js';

function PortfolioView({ portfolio, loading, horizon }) {
  if (loading) return h('div', { className: 'loading' }, 'Carregando carteira...');
  if (!portfolio || !portfolio.portfolio) return h('div', { className: 'notice' }, 'Nenhum ativo na carteira. Edite config/my-portfolio.txt');
  
  const assets = portfolio.portfolio;
  const validated = portfolio.model_validated;
  
  return h('section', { className: 'portfolio' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'MINHA CARTEIRA'),
        h('h2', null, 'Análise dos seus ativos'),
        h('p', null, `Horizonte de ${horizon} meses. ${assets.length} ativos analisados.`),
      ),
    ),
    h('div', { className: 'portfolio-grid' },
      assets.map((asset, index) => {
        const opp = asset.opportunity;
        const est = opp ? (opp.estimate * 100).toFixed(1) : '—';
        const low = opp ? (opp.estimate_low * 100).toFixed(1) : '—';
        const high = opp ? (opp.estimate_high * 100).toFixed(1) : '—';
        const dd = opp ? (opp.drawdown * 100).toFixed(1) : '—';
        const mom = opp ? (opp.momentum_12m * 100).toFixed(1) : '—';
        const vol = opp ? (opp.volatility * 100).toFixed(1) : '—';
        const isCandidate = opp?.candidate;
        const isValidated = opp?.validated;
        
        return h('div', { key: asset.ticker, className: `portfolio-card ${isCandidate ? 'candidate' : ''}` },
          h('div', { className: 'portfolio-header' },
            h('div', { className: 'portfolio-ticker' }, asset.ticker),
            h('div', { className: 'portfolio-price' }, `R$ ${asset.price?.toFixed(2) || '—'}`),
          ),
          h('div', { className: 'portfolio-name' }, asset.name),
          h('div', { className: 'portfolio-metrics' },
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Estimativa'),
              h('span', { className: `value ${opp?.estimate >= 0 ? 'positive' : 'negative'}` }, `${est}%`),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Faixa'),
              h('span', { className: 'value' }, `${low}% a ${high}%`),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Drawdown'),
              h('span', { className: `value ${dd < 0 ? 'negative' : ''}` }, `${dd}%`),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Momentum 12m'),
              h('span', { className: `value ${mom >= 0 ? 'positive' : 'negative'}` }, `${mom}%`),
            ),
            h('div', { className: 'metric' },
              h('span', { className: 'label' }, 'Volatilidade'),
              h('span', { className: 'value' }, `${vol}%`),
            ),
          ),
          h('div', { className: 'portfolio-status' },
            isCandidate ? h('span', { className: 'badge candidate' }, 'Candidato') : null,
            isValidated ? h('span', { className: 'badge validated' }, 'Validado') : null,
            !isValidated ? h('span', { className: 'badge not-validated' }, 'Não validado') : null,
          ),
        );
      }),
    ),
  );
}

function App() {
  const [horizon, setHorizon] = useState(6);
  const [data, setData] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('Consultando dados...');
  const [job, setJob] = useState({ status: 'idle', message: 'Nenhum treinamento em execução.' });
  const [filters, setFilters] = useState({ query: '', category: '', sector: '', saved: false, candidates: false });
  const [view, setView] = useState('portfolio'); // 'portfolio' ou 'all'

  async function load() {
    setLoading(true);
    setStatus('Consultando bancos de dados...');
    try {
      const [analysis, portfolioData] = await Promise.all([
        getAnalysis(horizon),
        getPortfolio(horizon),
      ]);
      setData(analysis);
      setAssets(analysis.assets || []);
      setPortfolio(portfolioData);
      setStatus('');
    } catch {
      setData(null);
      setAssets([]);
      setPortfolio(null);
      setStatus('Falha ao acessar os bancos. Verifique os serviços e recarregue.');
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

  return h(Layout, null,
    h('header', null, 
      h('span', null, 'Seu observatório de investimentos'), 
      h('div', { className: 'header-actions' },
        h('span', { className: 'pill' }, '● Dados Yahoo Finance'),
        h('div', { className: 'view-toggle' },
          h('button', { 
            className: `toggle-btn ${view === 'portfolio' ? 'active' : ''}`,
            onClick: () => setView('portfolio')
          }, 'Minha Carteira'),
          h('button', { 
            className: `toggle-btn ${view === 'all' ? 'active' : ''}`,
            onClick: () => setView('all')
          }, 'Todos os Ativos'),
        ),
      ),
    ),
    view === 'portfolio' ? 
      h(PortfolioView, { portfolio, loading, horizon }) :
      h(React.Fragment, null,
        h('section', { className: 'intro' },
          h('div', null,
            h('div', { className: 'eyebrow' }, 'PREÇO, TENDÊNCIA E RISCO'),
            h('h1', null, 'Oportunidades com', h('br'), 'evidência visível', h('span', null, '.')),
            h('p', null, 'Treino temporal, previsão de 6 meses e comparação', h('br'), 'com o retorno real observado posteriormente.'),
          ),
          h('div', { className: 'orbit', 'aria-hidden': 'true' }, h('span', null, '✦'), h('small', null, 'MÉDIO & LONGO PRAZO')),
        ),
        h('div', { className: 'notice' }, h('strong', null, 'Ranking experimental, não recomendação.'), ' O modelo não vê o retorno futuro durante o treino. Um sinal só é liberado quando supera a referência por pelo menos 2% e apresenta correlação de ranking mínima de 0,10.'),
        h('section', { className: 'stats' },
          h(StatCard, { label: 'Ativos analisados', value: loading ? '—' : String(assets.length), note: 'Universo atual do PostgreSQL' }),
          h(StatCard, { label: 'Horizonte do modelo', value: `${horizon} meses`, note: 'Retorno ajustado acumulado' }),
          h(StatCard, { label: 'Candidatos atuais', value: loading ? '—' : String(candidateCount), note: 'Somente modelo validado' }),
        ),
        h(AssetExplorer, { assets, filters, setFilters, horizon, setHorizon, status, setStatus, onFavoriteChange: updateFavorite }),
      ),
    h(TrainingConsole, { horizon, job, setJob, onFinished: load }),
    h(ValidationHistory, { predictions: data?.metrics?.predictions || [] }),
    h(EvaluationPanel, { data }),
    h('footer', null, 'MIDAS ', h('span', null, 'Pesquisa antes da decisão. Paciência antes do resultado.')),
  );
}

createRoot(document.getElementById('root')).render(h(App));
