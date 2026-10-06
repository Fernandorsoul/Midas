export const categories = { stock: 'Ações', fii: 'FIIs', fiagro: 'Fiagros' };

export const number = value => value == null ? '—' : value.toLocaleString('pt-BR', { maximumFractionDigits: 2 });

export const percent = value => value == null ? '—' : (value * 100).toLocaleString('pt-BR', {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
}) + '%';

export const date = value => value ? new Date(value).toLocaleDateString('pt-BR', { timeZone: 'UTC' }) : '—';

export function cell(row, text) {
  const element = document.createElement('td');
  element.textContent = text;
  row.append(element);
  return element;
}
