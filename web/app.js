import { getAnalysis, getTrainingStatus } from './api.js';
import { AssetExplorer } from './AssetExplorer.js';
import { EvaluationPanel } from './EvaluationPanel.js';
import { Layout } from './layout.js';
import { createRoot, React, useEffect, useMemo, useState } from './react.js';
import { TrainingConsole } from './TrainingConsole.js';
import { ValidationHistory } from './ValidationHistory.js';
import { h, StatCard } from './ui.js';

function App() {
  const [horizon, setHorizon] = useState(12);
  const [data, setData] = useState(null);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState('Consultando dados...');
  const [job, setJob] = useState({ status: 'idle', message: 'Nenhum treinamento em execução.' });
  const [filters, setFilters] = useState({ query: '', category: '', sector: '', saved: false, candidates: false });

  async function load() {
    setLoading(true);
    setStatus('Consultando bancos de dados...');
    try {
      const next = await getAnalysis(horizon);
      setData(next);
      setAssets(next.assets || []);
      setStatus('');
    } catch {
      setData(null);
      setAssets([]);
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
    h('header', null, h('span', null, 'Seu observatório de investimentos'), h('span', { className: 'pill' }, '● Dados brapi.dev')),
    h('section', { className: 'intro' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'PREÇO, TENDÊNCIA E RISCO'),
        h('h1', null, 'Oportunidades com', h('br'), 'evidência visível', h('span', null, '.')),
        h('p', null, 'Treino temporal, previsão de 12 meses e comparação', h('br'), 'com o retorno real observado posteriormente.'),
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
    h(TrainingConsole, { horizon, job, setJob, onFinished: load }),
    h(ValidationHistory, { predictions: data?.metrics?.predictions || [] }),
    h(EvaluationPanel, { data }),
    h('footer', null, 'MIDAS ', h('span', null, 'Pesquisa antes da decisão. Paciência antes do resultado.')),
  );
}

createRoot(document.getElementById('root')).render(h(App));
