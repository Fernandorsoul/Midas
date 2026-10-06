import { h } from './ui.js';

export function Sparkline({ values, label }) {
  if (!values || values.length < 2) return '—';
  const low = Math.min(...values);
  const range = Math.max(...values) - low || 1;
  const points = values.map((value, index) => `${index * 110 / (values.length - 1)},${30 - (value - low) / range * 27}`).join(' ');
  return h('svg', { viewBox: '0 0 110 32', role: 'img', 'aria-label': label },
    h('polyline', { points, fill: 'none', stroke: '#a7bd88', strokeWidth: '1.6' }),
  );
}
