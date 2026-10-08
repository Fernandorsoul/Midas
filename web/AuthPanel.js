import { getSessionUser, loginUser, logoutUser, registerUser } from './api.js';
import { React, useState } from './react.js';
import { h } from './ui.js';

export function AuthPanel({ user, onSuccess, onLogout }) {
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      if (mode === 'register') {
        await registerUser(email, password);
      }
      const data = await loginUser(email, password);
      onSuccess(data.user || getSessionUser());
    } catch (err) {
      setError(err.message || 'Falha na autenticação.');
    } finally {
      setSaving(false);
    }
  }

  if (user) {
    return h('div', { className: 'auth-bar' },
      h('span', { className: 'pill' }, '● ' + user.email),
      h('button', {
        type: 'button',
        className: 'ticker-remove',
        onClick: async () => {
          try { await logoutUser(); } catch { clearOnly(); }
          onLogout();
        },
      }, 'Sair'),
    );
  }

  return h('section', { className: 'auth-panel', 'aria-label': 'Autenticação' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'ACESSO'),
        h('h2', null, mode === 'login' ? 'Entrar no Midas' : 'Criar conta'),
        h('p', null, 'Carteira, operações e jobs são privados por usuário.'),
      ),
    ),
    error ? h('div', { className: 'notice error', role: 'alert' }, error) : null,
    h('form', { className: 'operation-form', onSubmit: submit },
      h('div', { className: 'operation-form-grid' },
        h('label', null, 'E-mail',
          h('input', {
            type: 'email', value: email, required: true, autoComplete: 'email',
            onChange: e => setEmail(e.target.value), disabled: saving,
          }),
        ),
        h('label', null, 'Senha (mín. 8 caracteres)',
          h('input', {
            type: 'password', value: password, required: true, minLength: 8,
            autoComplete: mode === 'login' ? 'current-password' : 'new-password',
            onChange: e => setPassword(e.target.value), disabled: saving,
          }),
        ),
      ),
      h('div', { className: 'operation-form-actions' },
        h('button', { type: 'submit', className: 'primary-action', disabled: saving },
          saving ? 'Enviando...' : (mode === 'login' ? 'Entrar' : 'Cadastrar e entrar'),
        ),
        h('button', {
          type: 'button',
          className: 'ticker-remove',
          onClick: () => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); },
          disabled: saving,
        }, mode === 'login' ? 'Criar conta' : 'Já tenho conta'),
      ),
    ),
  );
}

function clearOnly() {
  try {
    localStorage.removeItem('midas_token');
    localStorage.removeItem('midas_user');
  } catch { /* ignore */ }
}
