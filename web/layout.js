import { React } from './react.js';
import { h } from './ui.js';

export function Layout({ children }) {
  return h(React.Fragment, null,
    h('aside', null,
      h('a', { className: 'brand', href: '/' }, 'M', h('span', null, '✦'), ' MIDAS'),
      h('div', { className: 'subtitle' }, 'INTELIGÊNCIA PATRIMONIAL'),
      h('nav', null,
        h('a', { href: '#explorar', className: 'active' }, '◈   Oportunidades'),
        h('a', { href: '#validacao' }, '✓   Previsão × realidade'),
        h('a', { href: '#treinamento' }, '↻   Treinamento'),
        h('a', { href: '#metodo' }, '⌁   Laboratório de ML'),
      ),
      h('div', { className: 'aside-bottom' }, 'Visão de longo prazo.', h('br'), 'Decisões com contexto.', h('small', null, 'PROTÓTIPO · VERSÃO 0.4')),
    ),
    h('main', { id: 'explorar' }, children),
  );
}
