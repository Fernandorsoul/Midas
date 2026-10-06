import { React } from './react.js';

export const h = React.createElement;

export function SectionTitle({ eyebrow, title, children, action }) {
  return h('div', { className: 'section-title' },
    h('div', null,
      eyebrow ? h('div', { className: 'eyebrow' }, eyebrow) : null,
      h('h2', null, title),
      children ? h('p', null, children) : null,
    ),
    action || null,
  );
}

export function StatCard({ label, value, note }) {
  return h('article', null,
    h('small', null, label),
    h('strong', null, value),
    h('span', null, note),
  );
}

export function DataTable({ headers, children }) {
  return h('div', { className: 'table-wrap' },
    h('table', null,
      h('thead', null, h('tr', null, headers.map(header => h('th', { key: header }, header)))),
      h('tbody', null, children),
    ),
  );
}
