import { getTrainingStatus, startTraining } from './api.js';
import { h, SectionTitle } from './ui.js';

export function TrainingConsole({ horizon, job, setJob, onFinished }) {
  const running = job.status === 'queued' || job.status === 'running';

  async function trigger() {
    setJob({ status: 'queued', message: 'Enviando treinamento...', horizon });
    try {
      setJob(await startTraining(horizon));
    } catch (error) {
      setJob(error.data || { status: 'failed', message: error.message });
      return;
    }
    const timer = setInterval(async () => {
      try {
        const next = await getTrainingStatus();
        setJob(next);
        if (next.status === 'succeeded' || next.status === 'failed') {
          clearInterval(timer);
          if (next.status === 'succeeded') onFinished();
        }
      } catch {
        clearInterval(timer);
        setJob({ status: 'unknown', message: 'Não foi possível consultar o status do treinamento.' });
      }
    }, 1200);
  }

  return h('section', { id: 'treinamento', className: 'training-console' },
    h(SectionTitle, {
      eyebrow: 'TREINAMENTO CONTROLADO',
      title: 'Rodar novo experimento',
      action: h('button', { className: 'primary-action', type: 'button', disabled: running, onClick: trigger }, running ? 'Treinando...' : 'Treinar horizonte atual'),
    }, 'Cria um snapshot no MongoDB, treina os modelos candidatos e atualiza as métricas quando terminar.'),
    h('div', { className: `training-panel ${running ? 'is-running' : ''}` },
      h(JobCard, { label: 'Status', value: job.status || 'idle', note: job.error ? `${job.message} ${job.error}` : job.message || 'Aguardando ação.' }),
      h(JobCard, { label: 'Amostras', value: job.sample_count == null ? '—' : String(job.sample_count), note: 'Dataset publicado para treino' }),
      h(JobCard, { label: 'Dataset', value: job.dataset_id || '—', note: 'MongoDB' }),
      h(JobCard, { label: 'Modelo', value: job.run_id || '—', note: 'Execução salva' }),
    ),
  );
}

function JobCard({ label, value, note }) {
  return h('article', null, h('small', null, label), h('strong', null, value), h('span', null, note));
}
