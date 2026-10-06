import { React } from './react.js';
import { h } from './ui.js';

export function Layout({ children, currentPage, onNavigate }) {
  const pages = [
    { id: 'portfolio', label: 'Minha Carteira', icon: '◈' },
    { id: 'assets', label: 'Todos os Ativos', icon: '◉' },
    { id: 'training', label: 'Treinamento', icon: '↻' },
    { id: 'validation', label: 'Validação', icon: '✓' },
    { id: 'method', label: 'Método', icon: '⌁' },
  ];

  return h(React.Fragment, null,
    h('aside', null,
      h('a', { className: 'brand', href: '/', onClick: (e) => { e.preventDefault(); onNavigate('portfolio'); } }, 'M', h('span', null, '✦'), ' MIDAS'),
      h('div', { className: 'subtitle' }, 'INTELIGÊNCIA PATRIMONIAL'),
      h('nav', null,
        pages.map(page =>
          h('a', {
            key: page.id,
            href: '#' + page.id,
            className: currentPage === page.id ? 'active' : '',
            onClick: (e) => { e.preventDefault(); onNavigate(page.id); },
          }, page.icon + '   ' + page.label)
        ),
      ),
      h('div', { className: 'aside-bottom' }, 'Visão de longo prazo.', h('br'), 'Decisões com contexto.', h('small', null, 'PROTÓTIPO · VERSÃO 0.5')),
    ),
    h('main', { id: currentPage }, children),
  );
}