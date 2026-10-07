import {
  createPortfolioOperation,
  deletePortfolioOperation,
  getPortfolioOperations,
  getPortfolioPositions,
  updatePortfolioOperation,
} from './api.js';
import { React, useEffect, useState } from './react.js';
import { DataTable, h, StatCard } from './ui.js';

const OPERATION_TYPES = [
  { value: 'buy', label: 'Compra' },
  { value: 'sell', label: 'Venda' },
  { value: 'deposit', label: 'Aporte' },
  { value: 'withdrawal', label: 'Retirada' },
  { value: 'dividend', label: 'Dividendo' },
  { value: 'jcp', label: 'JCP' },
  { value: 'fee', label: 'Taxa' },
  { value: 'tax', label: 'Imposto' },
];

const TRADE_TYPES = new Set(['buy', 'sell']);
const CASH_TYPES = new Set(['deposit', 'withdrawal']);

function emptyForm() {
  return {
    id: null,
    ticker: '',
    operation_type: 'buy',
    occurred_on: new Date().toISOString().slice(0, 10),
    quantity: '',
    unit_price: '',
    amount: '',
    fees: '',
    taxes: '',
    notes: '',
  };
}

function formatMoney(value) {
  if (value === null || value === undefined) return '—';
  return 'R$ ' + Number(value).toFixed(2);
}

function formatQty(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toLocaleString('pt-BR', { maximumFractionDigits: 4 });
}

function pnlClass(value) {
  if (value === null || value === undefined) return '';
  return Number(value) >= 0 ? 'positive' : 'negative';
}

export function OperationsLedger() {
  const [form, setForm] = useState(emptyForm());
  const [operations, setOperations] = useState([]);
  const [positions, setPositions] = useState({});
  const [totals, setTotals] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  async function reload() {
    setLoading(true);
    setError('');
    try {
      const [ops, pos] = await Promise.all([getPortfolioOperations(), getPortfolioPositions()]);
      setOperations(ops.operations || []);
      setPositions(pos.positions || {});
      setTotals(pos.totals || null);
    } catch (err) {
      setError(err.message || 'Falha ao carregar operações.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { reload(); }, []);

  function updateField(field, value) {
    setForm(current => ({ ...current, [field]: value }));
  }

  function startEdit(operation) {
    setMessage('');
    setError('');
    setForm({
      id: operation.id,
      ticker: operation.ticker || '',
      operation_type: operation.operation_type,
      occurred_on: operation.occurred_on,
      quantity: operation.quantity || '',
      unit_price: operation.unit_price || '',
      amount: operation.amount || '',
      fees: operation.fees || '',
      taxes: operation.taxes || '',
      notes: operation.notes || '',
    });
  }

  function resetForm() {
    setForm(emptyForm());
  }

  function buildPayload() {
    const payload = {
      operation_type: form.operation_type,
      occurred_on: form.occurred_on,
      notes: form.notes || undefined,
    };
    if (form.id) payload.id = form.id;
    const ticker = form.ticker.trim().toUpperCase();
    if (!CASH_TYPES.has(form.operation_type)) payload.ticker = ticker;
    if (TRADE_TYPES.has(form.operation_type)) {
      payload.quantity = Number(form.quantity);
      payload.unit_price = Number(form.unit_price);
      if (form.fees !== '') payload.fees = Number(form.fees);
      if (form.taxes !== '') payload.taxes = Number(form.taxes);
    } else {
      payload.amount = Number(form.amount);
      if (form.fees !== '') payload.fees = Number(form.fees);
      if (form.taxes !== '') payload.taxes = Number(form.taxes);
    }
    return payload;
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    try {
      const payload = buildPayload();
      const result = form.id
        ? await updatePortfolioOperation(payload)
        : await createPortfolioOperation(payload);
      setMessage(result.message || 'Operação registrada.');
      resetForm();
      await reload();
    } catch (err) {
      setError(err.message || 'Falha ao salvar operação.');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(operationId) {
    setError('');
    setMessage('');
    try {
      const result = await deletePortfolioOperation(operationId);
      setMessage(result.message || 'Operação excluída.');
      if (form.id === operationId) resetForm();
      await reload();
    } catch (err) {
      setError(err.message || 'Não foi possível excluir. O livro ficaria inválido.');
    }
  }

  const isTrade = TRADE_TYPES.has(form.operation_type);
  const isCash = CASH_TYPES.has(form.operation_type);
  const needsTicker = !isCash;

  return h('section', { className: 'operations-ledger' },
    h('div', { className: 'section-title' },
      h('div', null,
        h('div', { className: 'eyebrow' }, 'LIVRO DE OPERAÇÕES'),
        h('h2', null, 'Posição, custo e P&L'),
        h('p', null, 'Compras, vendas, proventos e taxas alimentam o custo médio e o resultado auditável.'),
      ),
    ),
    error ? h('div', { className: 'notice error', role: 'alert' }, error) : null,
    message ? h('div', { className: 'notice success', role: 'status' }, message) : null,

    // Position summary
    totals ? h('div', { className: 'stats' },
      h(StatCard, { label: 'Custo total', value: formatMoney(totals.cost_basis), note: 'Preço médio acumulado' }),
      h(StatCard, { label: 'Resultado realizado', value: formatMoney(totals.realized_pnl), note: 'Vendas já fechadas' }),
      h(StatCard, { label: 'Resultado não realizado', value: formatMoney(totals.unrealized_pnl), note: 'Posição aberta a mercado' }),
      h(StatCard, { label: 'Retorno total', value: formatMoney(totals.total_pnl), note: 'Realizado + não realizado + proventos' }),
    ) : null,

    // Per-ticker positions
    Object.keys(positions).length > 0 ? h('div', { className: 'portfolio-list' },
      h('div', { className: 'portfolio-list-header' },
        h('span', null, 'Posições'),
        h('span', { className: 'portfolio-count' }, Object.keys(positions).length + ' ativos'),
      ),
      h(DataTable, {
        headers: ['Ativo', 'Qtd', 'Preço médio', 'Custo', 'Realizado', 'Não realizado', 'Total'],
      }, Object.values(positions).map(position =>
        h('tr', { key: position.ticker },
          h('td', { className: 'ticker-name' }, position.ticker),
          h('td', null, formatQty(position.quantity)),
          h('td', null, formatMoney(position.average_cost)),
          h('td', null, formatMoney(position.cost_basis)),
          h('td', { className: pnlClass(position.realized_pnl) }, formatMoney(position.realized_pnl)),
          h('td', { className: pnlClass(position.unrealized_pnl) }, formatMoney(position.unrealized_pnl)),
          h('td', { className: pnlClass(position.total_pnl) }, formatMoney(position.total_pnl)),
        )
      )),
    ) : null,

    // Entry form
    h('form', { className: 'operation-form', onSubmit: handleSubmit },
      h('h3', null, form.id ? 'Editar operação' : 'Lançar operação'),
      h('div', { className: 'operation-form-grid' },
        h('label', null,
          'Tipo',
          h('select', {
            value: form.operation_type,
            onChange: e => updateField('operation_type', e.target.value),
            disabled: saving,
          }, OPERATION_TYPES.map(item =>
            h('option', { key: item.value, value: item.value }, item.label)
          )),
        ),
        h('label', null,
          'Data',
          h('input', {
            type: 'date',
            value: form.occurred_on,
            onChange: e => updateField('occurred_on', e.target.value),
            required: true,
            disabled: saving,
          }),
        ),
        needsTicker ? h('label', null,
          'Ticker',
          h('input', {
            type: 'text',
            value: form.ticker,
            onChange: e => updateField('ticker', e.target.value),
            placeholder: 'PETR4',
            required: true,
            disabled: saving,
          }),
        ) : null,
        isTrade ? h('label', null,
          'Quantidade',
          h('input', {
            type: 'number',
            min: '0',
            step: 'any',
            value: form.quantity,
            onChange: e => updateField('quantity', e.target.value),
            required: true,
            disabled: saving,
          }),
        ) : null,
        isTrade ? h('label', null,
          'Preço unitário',
          h('input', {
            type: 'number',
            min: '0',
            step: 'any',
            value: form.unit_price,
            onChange: e => updateField('unit_price', e.target.value),
            required: true,
            disabled: saving,
          }),
        ) : null,
        !isTrade ? h('label', null,
          'Valor',
          h('input', {
            type: 'number',
            min: '0',
            step: 'any',
            value: form.amount,
            onChange: e => updateField('amount', e.target.value),
            required: true,
            disabled: saving,
          }),
        ) : null,
        h('label', null,
          'Taxas',
          h('input', {
            type: 'number',
            min: '0',
            step: 'any',
            value: form.fees,
            onChange: e => updateField('fees', e.target.value),
            disabled: saving,
          }),
        ),
        h('label', null,
          'Impostos',
          h('input', {
            type: 'number',
            min: '0',
            step: 'any',
            value: form.taxes,
            onChange: e => updateField('taxes', e.target.value),
            disabled: saving,
          }),
        ),
        h('label', { className: 'operation-notes' },
          'Observação',
          h('input', {
            type: 'text',
            value: form.notes,
            onChange: e => updateField('notes', e.target.value),
            maxLength: 500,
            disabled: saving,
          }),
        ),
      ),
      h('div', { className: 'operation-form-actions' },
        h('button', { type: 'submit', className: 'primary-action', disabled: saving },
          saving ? 'Salvando...' : (form.id ? 'Salvar edição' : 'Registrar operação'),
        ),
        form.id ? h('button', {
          type: 'button',
          className: 'ticker-remove',
          onClick: resetForm,
          disabled: saving,
        }, 'Cancelar') : null,
      ),
    ),

    // History
    h('div', { className: 'portfolio-list' },
      h('div', { className: 'portfolio-list-header' },
        h('span', null, 'Histórico'),
        h('span', { className: 'portfolio-count' }, operations.length + ' operações'),
      ),
      loading ? h('div', { className: 'loading' }, 'Carregando operações...')
        : operations.length === 0 ? h('div', { className: 'portfolio-empty' },
          h('p', null, 'Nenhuma operação lançada ainda.'),
        ) : h(DataTable, {
          headers: ['Data', 'Tipo', 'Ativo', 'Qtd', 'Preço', 'Valor', 'Taxas', 'Ações'],
        }, operations.map(operation =>
          h('tr', { key: operation.id },
            h('td', null, operation.occurred_on),
            h('td', null, (OPERATION_TYPES.find(t => t.value === operation.operation_type) || {}).label || operation.operation_type),
            h('td', { className: 'ticker-name' }, operation.ticker || '—'),
            h('td', null, operation.quantity ? formatQty(operation.quantity) : '—'),
            h('td', null, operation.unit_price ? formatMoney(operation.unit_price) : '—'),
            h('td', null, operation.amount ? formatMoney(operation.amount) : formatMoney((operation.quantity || 0) * (operation.unit_price || 0))),
            h('td', null, formatMoney((operation.fees || 0) + (operation.taxes || 0))),
            h('td', { className: 'operation-actions' },
              h('button', {
                type: 'button',
                className: 'ticker-remove',
                title: 'Editar operação',
                onClick: () => startEdit(operation),
              }, '✎'),
              h('button', {
                type: 'button',
                className: 'ticker-remove',
                title: 'Excluir operação',
                onClick: () => handleDelete(operation.id),
              }, '×'),
            ),
          )
        )),
    ),
  );
}
