import { cancelJob, getJob, getTrainingStatus, retryJob, startTraining } from './api.js';
import { h, SectionTitle } from './ui.js';

const ACTIVE = new Set(['queued', 'running']);

export function TrainingConsole({ horizon, job, setJob, onFinished }) {
  const running = job && ACTIVE.has(job.status);
  const failed = job && (job.status === 'failed' || job.status === 'cancelled');

  async function pollJob(jobId) {
    const timer = setInterval(async () => {
      try {
        const next = await getJob(jobId);
        setJob(next.job);
        if (!ACTIVE.has(next.job.status)) {
          clearInterval(timer);
          if (next.job.status === 'succeeded') onFinished();
        }
      } catch {
        // Polling resiliente: mantém a UI e tenta novamente no próximo ciclo.
      }
    }, 1500);
    return timer;
  }

  async function trigger() {
    setJob({ status: 'queued', step: 'queued', message: 'Enviando treinamento...', horizon });
    try {
      const result = await startTraining(horizon);
      setJob(result);
      if (result.id) pollJob(result.id);
      else {
        // Compat: se a API devolver snapshot sem id, consulta o status.
        const timer = setInterval(async () => {
          try {
            const next = await getTrainingStatus();
            setJob(next);
            if (!ACTIVE.has(next.status)) {
              clearInterval(timer);
              if (next.status === 'succeeded') onFinished();
            }
          } catch {
            clearInterval(timer);
            setJob({ status: 'unknown', message: 'Não foi possível consultar o status do treinamento.' });
          }
        }, 1500);
      }
    } catch (error) {
      setJob(error.data || { status: 'failed', message: error.message });
    }
  }

  async function handleCancel() {
    if (!job?.id) return;
    try {
      const result = await cancelJob(job.id);
      setJob(result.job || result);
    } catch (error) {
      setJob({ ...job, message: error.message });
    }
  }

  async function handleRetry() {
    if (!job?.id) return;
    try {
      const result = await retryJob(job.id);
      setJob(result.job || result);
      if (result.job?.id) pollJob(result.job.id);
    } catch (error) {
      setJob({ ...job, message: error.message });
    }
  }

  const progress = job?.progress == null ? 0 : Number(job.progress);

  return h('section', { id: 'treinamento', className: 'training-console' },
    h(SectionTitle, {
      eyebrow: 'TREINAMENTO CONTROLADO',
      title: 'Rodar novo experimento',
      action: h('div', { className: 'operation-form-actions' },
        h('button', {
          className: 'primary-action',
          type: 'button',
          disabled: running,
          onClick: trigger,
        }, running ? 'Treinando...' : 'Treinar horizonte atual'),
        running && job?.id ? h('button', {
          className: 'ticker-remove',
          type: 'button',
          onClick: handleCancel,
        }, 'Cancelar') : null,
        failed && job?.id ? h('button', {
          className: 'primary-action',
          type: 'button',
          onClick: handleRetry,
        }, 'Reexecutar') : null,
      ),
    }, 'Cria um snapshot no MongoDB, treina os modelos candidatos e atualiza as métricas quando terminar. O job fica no PostgreSQL e sobrevive a reinícios.'),
    running ? h('div', { className: 'notice', role: 'status' },
      `Progresso ${progress}% — etapa ${job.step || 'queued'}.`,
    ) : null,
    job?.error ? h('div', { className: 'notice error', role: 'alert' }, job.error) : null,
    h('div', { className: `training-panel ${running ? 'is-running' : ''}` },
      h(JobCard, { label: 'Status', value: job?.status || 'idle', note: job?.message || 'Aguardando ação.' }),
      h(JobCard, { label: 'Etapa', value: job?.step || '—', note: 'Progresso do job persistido' }),
      h(JobCard, { label: 'Amostras', value: job?.sample_count == null ? '—' : String(job.sample_count), note: 'Dataset publicado para treino' }),
      h(JobCard, { label: 'Dataset', value: job?.dataset_id || '—', note: 'MongoDB' }),
      h(JobCard, { label: 'Modelo', value: job?.run_id || '—', note: 'Execução salva' }),
    ),
  );
}

function JobCard({ label, value, note }) {
  return h('article', null, h('small', null, label), h('strong', null, value), h('span', null, note));
}
