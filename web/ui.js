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

export function Toast({ toasts, onDismiss }) {
  if (!toasts || toasts.length === 0) return null;
  return h('div', { className: 'toast-region', role: 'region', 'aria-label': 'Notificações' },
    toasts.map(toast =>
      h('div', {
        key: toast.id,
        className: `toast toast-${toast.tone || 'info'}`,
        role: toast.tone === 'error' ? 'alert' : 'status',
      },
        h('span', null, toast.message),
        h('button', {
          type: 'button',
          className: 'toast-dismiss',
          'aria-label': 'Dispensar notificação',
          onClick: () => onDismiss(toast.id),
        }, '×'),
      )
    ),
  );
}

let toastSeq = 0;
export function nextToastId() {
  toastSeq += 1;
  return toastSeq;
}
