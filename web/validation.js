import { cell, date, percent } from './format.js';

export function renderValidation(elements, predictions = []) {
  elements.validationRows.replaceChildren();
  const ordered = [...predictions].sort((a, b) =>
    b.as_of.localeCompare(a.as_of) || a.ticker.localeCompare(b.ticker)
  );

  for (const prediction of ordered) {
    const row = document.createElement('tr');
    cell(row, prediction.ticker);
    cell(row, date(prediction.as_of));
    cell(row, date(prediction.label_end));

    const predicted = cell(row, percent(prediction.predicted));
    predicted.className = prediction.predicted >= 0 ? 'positive' : 'negative';
    const actual = cell(row, percent(prediction.actual));
    actual.className = prediction.actual >= 0 ? 'positive' : 'negative';

    cell(row, percent(prediction.absolute_error));
    const directionCorrect = (prediction.predicted >= 0) === (prediction.actual >= 0);
    const result = cell(row, directionCorrect ? 'Direção correta' : 'Direção incorreta');
    result.className = directionCorrect ? 'positive' : 'negative';
    elements.validationRows.append(row);
  }

  elements.validationStatus.textContent = ordered.length
    ? `${ordered.length} previsões fora do treino comparadas com retornos reais já observados.`
    : 'Nenhuma previsão histórica disponível para este horizonte.';
}
