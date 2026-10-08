import { React, useState } from './react.js';
import { h } from './ui.js';

const PAGES = [
  { id: 'portfolio', label: 'Minha Carteira', icon: '◈' },
  { id: 'assets', label: 'Todos os Ativos', icon: '◉' },
  { id: 'screener', label: 'Screener', icon: '◐' },
  { id: 'training', label: 'Treinamento', icon: '↻' },
  { id: 'validation', label: 'Validação', icon: '✓' },
  { id: 'method', label: 'Método', icon: '⌁' },
];

export function Layout({ children, currentPage, onNavigate }) {
  const [menuOpen, setMenuOpen] = useState(false);

  function navigate(pageId) {
    setMenuOpen(false);
    onNavigate(pageId);
  }

  return h(React.Fragment, null,
    h('button', {
      type: 'button',
      className: 'nav-toggle',
      'aria-label': menuOpen ? 'Fechar menu' : 'Abrir menu',
      'aria-expanded': menuOpen,
      'aria-controls': 'primary-nav',
      onClick: () => setMenuOpen(open => !open),
    }, menuOpen ? '✕' : '☰'),
    menuOpen ? h('div', {
      className: 'nav-backdrop',
      onClick: () => setMenuOpen(false),
      'aria-hidden': 'true',
    }) : null,
    h('aside', { className: menuOpen ? 'nav-open' : '' },
      h('a', {
        className: 'brand',
        href: '/',
        onClick: (e) => { e.preventDefault(); navigate('portfolio'); },
      }, 'M', h('span', null, '✦'), ' MIDAS'),
      h('div', { className: 'subtitle' }, 'INTELIGÊNCIA PATRIMONIAL'),
      h('nav', { id: 'primary-nav', 'aria-label': 'Navegação principal' },
        PAGES.map(page =>
          h('a', {
            key: page.id,
            href: '#' + page.id,
            className: currentPage === page.id ? 'active' : '',
            'aria-current': currentPage === page.id ? 'page' : undefined,
            onClick: (e) => { e.preventDefault(); navigate(page.id); },
          }, page.icon + '   ' + page.label)
        ),
      ),
      h('div', { className: 'aside-bottom' }, 'Visão de longo prazo.', h('br'), 'Decisões com contexto.', h('small', null, 'PROTÓTIPO · VERSÃO 0.5')),
    ),
    h('main', { id: currentPage }, children),
  );
}
