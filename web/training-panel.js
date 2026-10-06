import { getTrainingStatus, startTraining } from './api.js';

let pollHandle = null;

function setRunning(elements, running) {
  elements.trainButton.disabled = running;
  elements.trainingPanel.classList.toggle('is-running', running);
}

function renderJob(elements, job) {
  elements.trainingState.textContent = job.status || 'idle';
  elements.trainingMessage.textContent = job.error ? `${job.message} ${job.error}` : (job.message || 'Aguardando ação.');
  elements.trainingDataset.textContent = job.dataset_id || '—';
  elements.trainingRun.textContent = job.run_id || '—';
  elements.trainingSamples.textContent = job.sample_count == null ? '—' : String(job.sample_count);
  setRunning(elements, job.status === 'queued' || job.status === 'running');
}

export async function refreshTrainingStatus(elements) {
  const job = await getTrainingStatus();
  renderJob(elements, job);
  return job;
}

export async function triggerTraining(elements, horizon, onFinished) {
  setRunning(elements, true);
  renderJob(elements, { status: 'queued', message: 'Enviando treinamento...', horizon });
  try {
    renderJob(elements, await startTraining(horizon));
  } catch (error) {
    renderJob(elements, error.data || { status: 'failed', message: error.message });
    return;
  }

  clearInterval(pollHandle);
  pollHandle = setInterval(async () => {
    try {
      const job = await refreshTrainingStatus(elements);
      if (job.status === 'succeeded' || job.status === 'failed') {
        clearInterval(pollHandle);
        pollHandle = null;
        if (job.status === 'succeeded') onFinished();
      }
    } catch {
      renderJob(elements, { status: 'unknown', message: 'Não foi possível consultar o status do treinamento.' });
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }, 1200);
}
