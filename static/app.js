/* ================================================================
   app.js — Spreetail SPA Logic
   Vanilla JS, no frameworks. Every function has a clear purpose.
   ================================================================ */

// ── State ─────────────────────────────────────────────────────────
const state = {
  currentUser: null,
  activeGroup: null,
  groups: [],
  users: [],
  expenses: [],
  settlements: [],
  balances: {},
  suggestedSettlements: [],
  editingExpenseId: null,
  currentImportSession: null,
  currentGroupDetailId: null,
};

// ── API Helper ────────────────────────────────────────────────────
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

async function apiUpload(path, formData) {
  const res = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    body: formData,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ── Toasts ────────────────────────────────────────────────────────
function toast(message, type = 'success') {
  const icon = { success: '✅', error: '❌', warning: '⚠️' }[type] || 'ℹ️';
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function showError(id, msg) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideError(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('hidden');
}

// ── Formatters ────────────────────────────────────────────────────
function fmt(amount) {
  const n = parseFloat(amount) || 0;
  return '₹' + Math.abs(n).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(d) {
  if (!d) return '–';
  return new Date(d).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function today() {
  return new Date().toISOString().split('T')[0];
}

// ── Auth ──────────────────────────────────────────────────────────
async function init() {
  try {
    const data = await api('GET', '/api/auth/me');
    if (data.user) {
      state.currentUser = data.user;
      await afterLogin();
    } else {
      showScreen('auth');
    }
  } catch {
    showScreen('auth');
  }
}

function switchAuthTab(tab) {
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
}

async function doLogin() {
  hideError('login-error');
  const username = document.getElementById('login-username').value.trim();
  const password = document.getElementById('login-password').value.trim();
  try {
    const data = await api('POST', '/api/auth/login', { username, password });
    state.currentUser = data.user;
    await afterLogin();
  } catch (e) {
    showError('login-error', e.message);
  }
}

async function doRegister() {
  hideError('register-error');
  const username = document.getElementById('reg-username').value.trim();
  const display_name = document.getElementById('reg-displayname').value.trim();
  const password = document.getElementById('reg-password').value.trim();
  try {
    const data = await api('POST', '/api/auth/register', { username, display_name, password });
    state.currentUser = data.user;
    await afterLogin();
  } catch (e) {
    showError('register-error', e.message);
  }
}

async function doLogout() {
  await api('POST', '/api/auth/logout');
  state.currentUser = null;
  state.activeGroup = null;
  showScreen('auth');
}

async function afterLogin() {
  // Update sidebar
  document.getElementById('sidebar-username').textContent = state.currentUser.display_name;
  document.getElementById('sidebar-avatar').textContent = state.currentUser.display_name[0].toUpperCase();
  document.getElementById('dash-name').textContent = state.currentUser.display_name;

  // Load data
  await Promise.all([loadGroups(), loadUsers()]);
  showScreen('app');
  showPage('dashboard');
}

// ── Screens & Navigation ──────────────────────────────────────────
function showScreen(name) {
  document.getElementById('auth-screen').style.display = name === 'auth' ? 'flex' : 'none';
  document.getElementById('app-screen').style.display  = name === 'app'  ? 'block' : 'none';
}

async function showPage(name) {
  // Deactivate all nav items and pages
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.page').forEach(el => el.classList.remove('active'));

  const navEl = document.getElementById(`nav-${name}`);
  if (navEl) navEl.classList.add('active');

  const pageEl = document.getElementById(`page-${name}`);
  if (pageEl) pageEl.classList.add('active');

  // Page-specific data loading
  if (name === 'dashboard')   await loadDashboard();
  if (name === 'groups')      await renderGroups();
  if (name === 'expenses')    await loadExpenses();
  if (name === 'balances')    await loadBalances();
  if (name === 'settlements') await loadSettlements();
  if (name === 'import')      await populateImportGroupSelect();
}

// ── Modals ────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).classList.add('open'); }
function closeModal(id) { document.getElementById(id).classList.remove('open'); }

// Close on overlay click
document.addEventListener('click', e => {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// ── Groups ────────────────────────────────────────────────────────
async function loadGroups() {
  const data = await api('GET', '/api/groups/');
  state.groups = data.groups || [];
  if (state.groups.length > 0 && !state.activeGroup) {
    state.activeGroup = state.groups[0];
  }
}

async function renderGroups() {
  await loadGroups();
  const grid = document.getElementById('groups-grid');
  if (state.groups.length === 0) {
    grid.innerHTML = `<div class="empty-state">
      <div class="empty-state-icon">👥</div>
      <h3>No groups yet</h3>
      <p>Create your first group to start splitting expenses.</p>
    </div>`;
    return;
  }
  grid.innerHTML = state.groups.map(g => `
    <div class="card" style="cursor:pointer;" onclick="openGroupDetail(${g.id})">
      <div class="flex-between mb-8">
        <div style="font-size:1.1rem;font-weight:700;">${esc(g.name)}</div>
        <div class="badge badge-purple">${g.id === state.activeGroup?.id ? 'Active' : ''}</div>
      </div>
      <div class="text-muted text-small">${esc(g.description || 'No description')}</div>
      <div class="mt-16 flex gap-8">
        <button class="btn btn-secondary btn-sm" onclick="event.stopPropagation();setActiveGroup(${g.id})">
          ${g.id === state.activeGroup?.id ? '✓ Active' : 'Set Active'}
        </button>
      </div>
    </div>
  `).join('');
}

function setActiveGroup(id) {
  state.activeGroup = state.groups.find(g => g.id === id);
  toast(`Active group: ${state.activeGroup.name}`);
  renderGroups();
}

function openGroupModal() {
  document.getElementById('group-name').value = '';
  document.getElementById('group-desc').value = '';
  hideError('group-error');
  openModal('group-modal');
}

async function createGroup() {
  hideError('group-error');
  const name = document.getElementById('group-name').value.trim();
  const description = document.getElementById('group-desc').value.trim();
  if (!name) { showError('group-error', 'Group name is required'); return; }
  try {
    const data = await api('POST', '/api/groups/', { name, description });
    state.groups.push(data.group);
    if (!state.activeGroup) state.activeGroup = data.group;
    closeModal('group-modal');
    toast(`Group "${name}" created`);
    renderGroups();
  } catch (e) {
    showError('group-error', e.message);
  }
}

async function openGroupDetail(groupId) {
  state.currentGroupDetailId = groupId;
  const data = await api('GET', `/api/groups/${groupId}`);
  document.getElementById('gd-title').textContent = data.group.name;
  document.getElementById('gd-members-list').innerHTML = data.members.map(m => `
    <div class="flex-between" style="padding:10px 0;border-bottom:1px solid var(--border);">
      <div>
        <span style="font-weight:600;">${esc(m.user_display_name)}</span>
        <span class="text-muted text-small"> · Joined ${fmtDate(m.joined_at)}</span>
        ${m.left_at ? `<span class="badge badge-red" style="margin-left:8px;">Left ${fmtDate(m.left_at)}</span>` : '<span class="badge badge-green" style="margin-left:8px;">Active</span>'}
      </div>
      ${!m.left_at ? `<button class="btn btn-danger btn-sm" onclick="removeMember(${groupId}, ${m.user_id})">Remove</button>` : ''}
    </div>
  `).join('');
  openModal('group-detail-modal');
}

function openAddMemberModal() {
  document.getElementById('member-join-date').value = today();
  const sel = document.getElementById('member-user-select');
  sel.innerHTML = state.users.map(u => `<option value="${u.id}">${esc(u.display_name)}</option>`).join('');
  hideError('add-member-error');
  openModal('add-member-modal');
}

async function addMember() {
  hideError('add-member-error');
  const user_id = parseInt(document.getElementById('member-user-select').value);
  const joined_at = document.getElementById('member-join-date').value;
  try {
    await api('POST', `/api/groups/${state.currentGroupDetailId}/members`, { user_id, joined_at });
    toast('Member added');
    closeModal('add-member-modal');
    openGroupDetail(state.currentGroupDetailId);
  } catch (e) {
    showError('add-member-error', e.message);
  }
}

async function removeMember(groupId, userId) {
  if (!confirm('Remove this member? Their expenses will remain.')) return;
  const left_at = today();
  await api('POST', `/api/groups/${groupId}/members/${userId}/leave`, { left_at });
  toast('Member removed');
  openGroupDetail(groupId);
}

// ── Users ─────────────────────────────────────────────────────────
async function loadUsers() {
  const data = await api('GET', '/api/auth/users');
  state.users = data.users || [];
}

// ── Expenses ──────────────────────────────────────────────────────
async function loadExpenses() {
  if (!state.activeGroup) {
    document.getElementById('no-group-warning').classList.remove('hidden');
    document.getElementById('expenses-empty').classList.remove('hidden');
    return;
  }
  document.getElementById('no-group-warning').classList.add('hidden');
  const data = await api('GET', `/api/expenses/group/${state.activeGroup.id}`);
  state.expenses = data.expenses || [];
  renderExpensesTable();
}

function renderExpensesTable() {
  const tbody = document.getElementById('expenses-tbody');
  const empty = document.getElementById('expenses-empty');

  if (state.expenses.length === 0) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  tbody.innerHTML = state.expenses.map(e => `
    <tr>
      <td>${fmtDate(e.date)}</td>
      <td>
        <span style="font-weight:500;">${esc(e.description)}</span>
        ${e.notes ? `<div class="text-muted text-small">${esc(e.notes.substring(0,60))}${e.notes.length>60?'…':''}</div>` : ''}
      </td>
      <td>${fmt(e.amount_inr)}</td>
      <td>
        ${e.original_currency !== 'INR'
          ? `<span class="badge badge-blue">${e.original_currency}</span> ${e.original_amount} @ ${e.fx_rate_used}`
          : '<span class="badge badge-gray">INR</span>'}
      </td>
      <td>${esc(e.paid_by_name)}</td>
      <td><span class="badge badge-purple">${e.split_type}</span></td>
      <td class="text-muted text-small">${e.import_source === 'csv_import' ? '📂 CSV' : '✏️ Manual'}</td>
      <td>
        <div class="flex gap-8">
          <button class="btn btn-secondary btn-sm" onclick="editExpense(${e.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteExpense(${e.id})">Del</button>
        </div>
      </td>
    </tr>
  `).join('');
}

function openExpenseModal() {
  if (!state.activeGroup) { toast('Please select a group first', 'warning'); showPage('groups'); return; }
  state.editingExpenseId = null;
  document.getElementById('expense-modal-title').textContent = 'Add Expense';
  document.getElementById('exp-description').value = '';
  document.getElementById('exp-amount').value = '';
  document.getElementById('exp-date').value = today();
  document.getElementById('exp-currency').value = 'INR';
  document.getElementById('exp-split-type').value = 'equal';
  hideError('expense-error');
  populateExpensePaidBy();
  onSplitTypeChange();
  openModal('expense-modal');
}

function populateExpensePaidBy() {
  const sel = document.getElementById('exp-paid-by');
  // Members active in the group
  const members = state.users; // simplified — show all users
  sel.innerHTML = members.map(u =>
    `<option value="${u.id}" ${u.id === state.currentUser?.id ? 'selected' : ''}>${esc(u.display_name)}</option>`
  ).join('');
}

function onSplitTypeChange() {
  updateSplitPreview();
}

function updateSplitPreview() {
  const splitType = document.getElementById('exp-split-type').value;
  const amount = parseFloat(document.getElementById('exp-amount').value) || 0;
  const currency = document.getElementById('exp-currency').value;
  const fxRate = currency === 'USD' ? 83 : 1;
  const amountInr = amount * fxRate;

  const container = document.getElementById('split-members-list');
  const preview = document.getElementById('split-total-preview');
  const builder = document.getElementById('split-builder');

  if (splitType === 'equal') {
    const n = state.users.length;
    const perPerson = n > 0 ? amountInr / n : 0;
    container.innerHTML = state.users.map(u => `
      <div class="split-member-row">
        <div class="split-member-name">${esc(u.display_name)}</div>
        <div class="split-member-amount">${fmt(perPerson)}</div>
      </div>
    `).join('');
    preview.textContent = '';
    builder.style.display = 'block';
    return;
  }

  if (splitType === 'percentage') {
    const even = state.users.length > 0 ? (100 / state.users.length).toFixed(1) : 0;
    container.innerHTML = state.users.map(u => `
      <div class="split-member-row">
        <div class="split-member-name">${esc(u.display_name)}</div>
        <input class="split-member-input" type="number" step="0.1" value="${even}"
          data-uid="${u.id}" data-type="pct" oninput="recalcSplits()" />
        <div class="split-member-amount" id="pct-amt-${u.id}">${fmt(amountInr / state.users.length)}</div>
      </div>
    `).join('');
    preview.textContent = 'Must sum to 100%';
    recalcSplits();
    builder.style.display = 'block';
    return;
  }

  if (splitType === 'exact') {
    const even = state.users.length > 0 ? (amountInr / state.users.length).toFixed(2) : 0;
    container.innerHTML = state.users.map(u => `
      <div class="split-member-row">
        <div class="split-member-name">${esc(u.display_name)}</div>
        <input class="split-member-input" type="number" step="0.01" value="${even}"
          data-uid="${u.id}" data-type="exact" oninput="recalcSplits()" />
      </div>
    `).join('');
    preview.textContent = 'Must sum to total amount';
    recalcSplits();
    builder.style.display = 'block';
    return;
  }

  if (splitType === 'shares') {
    container.innerHTML = state.users.map(u => `
      <div class="split-member-row">
        <div class="split-member-name">${esc(u.display_name)}</div>
        <input class="split-member-input" type="number" step="1" value="1"
          data-uid="${u.id}" data-type="shares" oninput="recalcSplits()" />
        <div class="split-member-amount" id="shares-amt-${u.id}">${fmt(amountInr / state.users.length)}</div>
      </div>
    `).join('');
    preview.textContent = 'Proportional by share count';
    recalcSplits();
    builder.style.display = 'block';
  }
}

function recalcSplits() {
  const splitType = document.getElementById('exp-split-type').value;
  const amount = parseFloat(document.getElementById('exp-amount').value) || 0;
  const currency = document.getElementById('exp-currency').value;
  const fxRate = currency === 'USD' ? 83 : 1;
  const amountInr = amount * fxRate;

  const inputs = document.querySelectorAll('[data-type]');
  const preview = document.getElementById('split-total-preview');

  if (splitType === 'percentage') {
    let total = 0;
    inputs.forEach(inp => {
      const uid = inp.dataset.uid;
      const pct = parseFloat(inp.value) || 0;
      total += pct;
      const amtEl = document.getElementById(`pct-amt-${uid}`);
      if (amtEl) amtEl.textContent = fmt(amountInr * pct / 100);
    });
    preview.textContent = `Total: ${total.toFixed(1)}% ${Math.abs(total - 100) < 0.01 ? '✅' : '⚠️ Must be 100%'}`;
  }

  if (splitType === 'exact') {
    let total = 0;
    inputs.forEach(inp => { total += parseFloat(inp.value) || 0; });
    preview.textContent = `Total: ${fmt(total)} of ${fmt(amountInr)} ${Math.abs(total - amountInr) < 0.01 ? '✅' : '⚠️ Must match'}`;
  }

  if (splitType === 'shares') {
    let totalShares = 0;
    inputs.forEach(inp => { totalShares += parseFloat(inp.value) || 0; });
    inputs.forEach(inp => {
      const uid = inp.dataset.uid;
      const shares = parseFloat(inp.value) || 0;
      const amtEl = document.getElementById(`shares-amt-${uid}`);
      if (amtEl) amtEl.textContent = fmt(totalShares > 0 ? amountInr * shares / totalShares : 0);
    });
    preview.textContent = `Total shares: ${totalShares}`;
  }
}

function getSplitDetails() {
  const splitType = document.getElementById('exp-split-type').value;
  const inputs = document.querySelectorAll('[data-type]');
  if (inputs.length === 0 || splitType === 'equal') return {};
  const details = {};
  inputs.forEach(inp => { details[inp.dataset.uid] = parseFloat(inp.value) || 0; });
  return details;
}

async function saveExpense() {
  hideError('expense-error');
  const description = document.getElementById('exp-description').value.trim();
  const amount = parseFloat(document.getElementById('exp-amount').value);
  const currency = document.getElementById('exp-currency').value;
  const date = document.getElementById('exp-date').value;
  const paid_by_id = parseInt(document.getElementById('exp-paid-by').value);
  const split_type = document.getElementById('exp-split-type').value;
  const split_details = getSplitDetails();

  if (!description || !amount || !date) {
    showError('expense-error', 'Description, amount, and date are required');
    return;
  }

  try {
    if (state.editingExpenseId) {
      await api('PUT', `/api/expenses/${state.editingExpenseId}`, {
        description, amount, currency, date, paid_by_id, split_type, split_details
      });
      toast('Expense updated');
    } else {
      await api('POST', '/api/expenses/', {
        group_id: state.activeGroup.id,
        description, amount, currency, date, paid_by_id, split_type, split_details
      });
      toast('Expense added');
    }
    closeModal('expense-modal');
    await loadExpenses();
  } catch (e) {
    showError('expense-error', e.message);
  }
}

async function editExpense(id) {
  const expense = state.expenses.find(e => e.id === id);
  if (!expense) return;
  state.editingExpenseId = id;
  document.getElementById('expense-modal-title').textContent = 'Edit Expense';
  document.getElementById('exp-description').value = expense.description;
  document.getElementById('exp-amount').value = expense.original_amount || expense.amount_inr;
  document.getElementById('exp-currency').value = expense.original_currency || 'INR';
  document.getElementById('exp-date').value = expense.date;
  document.getElementById('exp-split-type').value = expense.split_type;
  populateExpensePaidBy();
  document.getElementById('exp-paid-by').value = expense.paid_by_id;
  hideError('expense-error');
  onSplitTypeChange();
  openModal('expense-modal');
}

async function deleteExpense(id) {
  if (!confirm('Delete this expense? This cannot be undone.')) return;
  await api('DELETE', `/api/expenses/${id}`);
  toast('Expense deleted');
  await loadExpenses();
}

// ── Balances ──────────────────────────────────────────────────────
async function loadBalances() {
  if (!state.activeGroup) {
    document.getElementById('balances-grid').innerHTML = `
      <div class="empty-state"><div class="empty-state-icon">⚖️</div>
      <h3>No active group</h3><p>Select a group first.</p></div>`;
    return;
  }
  const data = await api('GET', `/api/settlements/group/${state.activeGroup.id}/balances`);
  state.balances = data.balances;
  state.suggestedSettlements = data.suggested_settlements;
  renderBalances();
}

function renderBalances() {
  const grid = document.getElementById('balances-grid');
  const entries = Object.entries(state.balances).sort((a, b) => b[1].net - a[1].net);

  grid.innerHTML = entries.map(([uid, b]) => {
    const cls = b.net > 0.01 ? 'owed-to-you' : b.net < -0.01 ? 'you-owe' : 'settled';
    const label = b.net > 0.01 ? 'Gets back' : b.net < -0.01 ? 'Owes' : 'Settled up';
    return `
      <div class="balance-card" onclick="showBreakdown(${uid})">
        <div>
          <div class="balance-name">${esc(b.display_name)}</div>
          <div class="balance-sub">Paid: ${fmt(b.paid)} · Owes: ${fmt(b.owed)}</div>
        </div>
        <div>
          <div class="balance-amount ${cls}">${b.net < 0 ? '−' : '+'}${fmt(Math.abs(b.net))}</div>
          <div class="text-small text-muted text-right">${label}</div>
        </div>
      </div>
    `;
  }).join('');

  // Append suggested settlements
  if (state.suggestedSettlements.length > 0) {
    grid.innerHTML += `
      <div class="card mt-16">
        <h3 style="font-size:1rem;font-weight:600;margin-bottom:16px;">💡 Suggested Settlements</h3>
        ${state.suggestedSettlements.map(s => `
          <div class="settlement-flow">
            <span style="font-weight:600;">${esc(s.from_user_name)}</span>
            <span class="arrow">→</span>
            <span style="font-weight:600;">${esc(s.to_user_name)}</span>
            <span class="amount">${fmt(s.amount_inr)}</span>
            <button class="btn btn-success btn-sm" onclick="quickSettle(${s.from_user_id},${s.to_user_id},${s.amount_inr})">
              Record
            </button>
          </div>
        `).join('')}
      </div>
    `;
  }
}

function showBreakdown(uid) {
  const b = state.balances[uid];
  if (!b) return;
  document.getElementById('breakdown-title').textContent = `${b.display_name}'s Breakdown`;
  document.getElementById('breakdown-stats').innerHTML = `
    <div class="stat-card"><div class="stat-label">PAID</div><div class="stat-value positive">${fmt(b.paid)}</div></div>
    <div class="stat-card"><div class="stat-label">OWED</div><div class="stat-value negative">${fmt(b.owed)}</div></div>
    <div class="stat-card"><div class="stat-label">NET</div>
      <div class="stat-value ${b.net >= 0 ? 'positive' : 'negative'}">${b.net >= 0 ? '+' : ''}${fmt(b.net)}</div>
    </div>
  `;
  const breakdown = b.expense_breakdown || [];
  if (breakdown.length === 0) {
    document.getElementById('breakdown-list').innerHTML = '<div class="text-muted text-center" style="padding:24px;">No expense details available.</div>';
  } else {
    document.getElementById('breakdown-list').innerHTML = breakdown.map(item => `
      <div class="breakdown-item">
        <div class="breakdown-desc">${esc(item.description)}</div>
        <div class="breakdown-date">${fmtDate(item.date)}</div>
        <div class="breakdown-amt ${item.net >= 0 ? 'positive' : 'negative'}">
          ${item.net >= 0 ? '+' : ''}${fmt(item.net)}
        </div>
      </div>
    `).join('');
  }
  openModal('breakdown-modal');
}

// ── Settlements ───────────────────────────────────────────────────
async function loadSettlements() {
  if (!state.activeGroup) return;
  const data = await api('GET', `/api/settlements/group/${state.activeGroup.id}`);
  state.settlements = data.settlements || [];
  renderSettlementsTable();
}

function renderSettlementsTable() {
  const tbody = document.getElementById('settlements-tbody');
  const empty = document.getElementById('settlements-empty');
  if (state.settlements.length === 0) {
    tbody.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');
  tbody.innerHTML = state.settlements.map(s => `
    <tr>
      <td>${fmtDate(s.date)}</td>
      <td style="font-weight:500;">${esc(s.payer_name)}</td>
      <td style="font-weight:500;">${esc(s.payee_name)}</td>
      <td style="color:var(--success);font-weight:700;">${fmt(s.amount_inr)}</td>
      <td class="text-muted">${esc(s.notes || '–')}</td>
      <td><button class="btn btn-danger btn-sm" onclick="deleteSettlement(${s.id})">Del</button></td>
    </tr>
  `).join('');
}

function openSettlementModal() {
  if (!state.activeGroup) { toast('Please select a group first', 'warning'); showPage('groups'); return; }
  const payerSel = document.getElementById('set-payer');
  const payeeSel = document.getElementById('set-payee');
  payerSel.innerHTML = state.users.map(u => `<option value="${u.id}">${esc(u.display_name)}</option>`).join('');
  payeeSel.innerHTML = state.users.map(u => `<option value="${u.id}">${esc(u.display_name)}</option>`).join('');
  document.getElementById('set-amount').value = '';
  document.getElementById('set-date').value = today();
  document.getElementById('set-notes').value = '';
  hideError('settlement-error');
  openModal('settlement-modal');
}

async function quickSettle(fromId, toId, amount) {
  const payerSel = document.getElementById('set-payer');
  const payeeSel = document.getElementById('set-payee');
  payerSel.innerHTML = state.users.map(u => `<option value="${u.id}">${esc(u.display_name)}</option>`).join('');
  payeeSel.innerHTML = state.users.map(u => `<option value="${u.id}">${esc(u.display_name)}</option>`).join('');
  payerSel.value = fromId;
  payeeSel.value = toId;
  document.getElementById('set-amount').value = amount.toFixed(2);
  document.getElementById('set-date').value = today();
  document.getElementById('set-notes').value = 'Quick settle from suggestion';
  openModal('settlement-modal');
}

async function saveSettlement() {
  hideError('settlement-error');
  const payer_id = parseInt(document.getElementById('set-payer').value);
  const payee_id = parseInt(document.getElementById('set-payee').value);
  const amount = parseFloat(document.getElementById('set-amount').value);
  const date = document.getElementById('set-date').value;
  const notes = document.getElementById('set-notes').value.trim();

  if (payer_id === payee_id) { showError('settlement-error', 'Payer and payee cannot be the same'); return; }
  if (!amount || amount <= 0) { showError('settlement-error', 'Amount must be positive'); return; }

  try {
    await api('POST', '/api/settlements/', {
      group_id: state.activeGroup.id, payer_id, payee_id, amount, date, notes
    });
    toast('Payment recorded');
    closeModal('settlement-modal');
    await loadSettlements();
    await loadBalances();
  } catch (e) {
    showError('settlement-error', e.message);
  }
}

async function deleteSettlement(id) {
  if (!confirm('Delete this settlement?')) return;
  await api('DELETE', `/api/settlements/${id}`);
  toast('Settlement deleted');
  await loadSettlements();
}

// ── Dashboard ─────────────────────────────────────────────────────
async function loadDashboard() {
  await loadGroups();
  const dashGroup = document.getElementById('dash-group');
  if (!state.activeGroup) {
    dashGroup.textContent = 'No group';
    return;
  }
  dashGroup.textContent = state.activeGroup.name;

  try {
    const data = await api('GET', `/api/settlements/group/${state.activeGroup.id}/balances`);
    state.balances = data.balances;
    state.suggestedSettlements = data.suggested_settlements;

    const me = data.balances[state.currentUser.id];
    if (me) {
      document.getElementById('dash-net').textContent = (me.net >= 0 ? '+' : '') + fmt(me.net);
      document.getElementById('dash-net').className = 'stat-value ' + (me.net > 0 ? 'positive' : me.net < 0 ? 'negative' : 'neutral');
      document.getElementById('dash-paid').textContent = fmt(me.paid);
      document.getElementById('dash-owed').textContent = fmt(me.owed);
    }

    const flowEl = document.getElementById('dash-settlements');
    if (state.suggestedSettlements.length === 0) {
      flowEl.innerHTML = '<div class="text-muted text-small text-center" style="padding:16px;">🎉 All settled up!</div>';
    } else {
      flowEl.innerHTML = state.suggestedSettlements.map(s => `
        <div class="settlement-flow">
          <span style="font-weight:600;">${esc(s.from_user_name)}</span>
          <span class="arrow">→</span>
          <span style="font-weight:600;">${esc(s.to_user_name)}</span>
          <span class="amount">${fmt(s.amount_inr)}</span>
        </div>
      `).join('');
    }
  } catch { /* group may have no expenses yet */ }
}

// ── Import CSV ────────────────────────────────────────────────────
async function populateImportGroupSelect() {
  const sel = document.getElementById('import-group-select');
  await loadGroups();
  sel.innerHTML = state.groups.length === 0
    ? '<option value="">No groups — create one first</option>'
    : state.groups.map(g => `<option value="${g.id}">${esc(g.name)}</option>`).join('');
}

function handleDragOver(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.add('drag-over');
}
function handleDragLeave(e) {
  document.getElementById('upload-zone').classList.remove('drag-over');
}
function handleDrop(e) {
  e.preventDefault();
  document.getElementById('upload-zone').classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) processCSVFile(file);
}
function handleFileSelect(e) {
  const file = e.target.files[0];
  if (file) processCSVFile(file);
}

async function processCSVFile(file) {
  const groupId = document.getElementById('import-group-select').value;
  if (!groupId) { toast('Please select a target group first', 'warning'); return; }

  document.getElementById('import-loading').classList.remove('hidden');
  document.getElementById('upload-zone').classList.add('hidden');

  const formData = new FormData();
  formData.append('file', file);
  formData.append('group_id', groupId);

  try {
    const data = await apiUpload('/api/imports/upload', formData);
    state.currentImportSession = data.session;
    renderImportReport(data);
  } catch (e) {
    toast('Import failed: ' + e.message, 'error');
    resetImport();
  } finally {
    document.getElementById('import-loading').classList.add('hidden');
  }
}

function renderImportReport(data) {
  const session = data.session;
  const anomalies = data.anomalies || [];

  document.getElementById('import-upload-section').classList.add('hidden');
  document.getElementById('import-report-section').classList.remove('hidden');

  document.getElementById('import-stats').innerHTML = `
    <div class="import-stat">
      <div class="import-stat-value" style="color:var(--success)">${session.imported_count}</div>
      <div class="import-stat-label">Imported</div>
    </div>
    <div class="import-stat">
      <div class="import-stat-value" style="color:var(--warning)">${session.pending_review_count}</div>
      <div class="import-stat-label">Pending Review</div>
    </div>
    <div class="import-stat">
      <div class="import-stat-value" style="color:var(--danger)">${session.skipped_count}</div>
      <div class="import-stat-label">Skipped</div>
    </div>
  `;

  if (anomalies.length === 0) {
    document.getElementById('anomalies-list').innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">✅</div>
        <h3>No anomalies detected</h3>
        <p>The CSV was clean!</p>
      </div>`;
    return;
  }

  const severityClass = (action) => {
    if (['SKIP', 'PENDING_REVIEW'].some(s => action.includes(s))) return 'severity-skip';
    if (action.includes('AUTO')) return 'severity-auto';
    return 'severity-review';
  };

  const badgeClass = (type) => {
    const map = {
      DUPLICATE: 'badge-yellow', NEGATIVE_AMOUNT: 'badge-red', CURRENCY_USD: 'badge-blue',
      SETTLEMENT_AS_EXPENSE: 'badge-purple', POST_DEPARTURE: 'badge-yellow', PRE_JOIN: 'badge-yellow',
      MISSING_PAID_BY: 'badge-red', UNKNOWN_MEMBER: 'badge-blue', INCONSISTENT_DATE: 'badge-gray',
      AMOUNT_WITH_SYMBOL: 'badge-gray', WRONG_SPLIT_LABEL: 'badge-gray', ZERO_AMOUNT: 'badge-red',
      FUTURE_DATE: 'badge-yellow', BAD_PERCENTAGE_SUM: 'badge-yellow',
    };
    return map[type] || 'badge-gray';
  };

  document.getElementById('anomalies-list').innerHTML = anomalies.map(a => `
    <div class="anomaly-row ${severityClass(a.suggested_action)}" id="anomaly-${a.id}">
      <div class="anomaly-header">
        <span class="badge ${badgeClass(a.anomaly_type)} anomaly-type">${a.anomaly_type}</span>
        <span class="anomaly-row-num">Row ${a.row_number}</span>
        <span class="badge ${a.resolved ? 'badge-green' : 'badge-gray'}" id="status-${a.id}">
          ${a.user_decision || 'PENDING'}
        </span>
      </div>
      <div class="anomaly-desc">${esc(a.description)}</div>
      <div class="anomaly-desc text-small" style="color:var(--text-muted);">
        Suggested: <strong>${a.suggested_action}</strong>
      </div>
      ${!a.resolved ? `
        <div class="anomaly-actions">
          <button class="btn btn-success btn-sm" onclick="resolveAnomaly(${a.id}, 'APPROVED')">✅ Approve</button>
          <button class="btn btn-danger btn-sm" onclick="resolveAnomaly(${a.id}, 'REJECTED')">❌ Reject</button>
          <button class="btn btn-secondary btn-sm" onclick="resolveAnomaly(${a.id}, 'MODIFIED')">✏️ Modified</button>
        </div>` : ''}
    </div>
  `).join('');
}

async function resolveAnomaly(id, decision) {
  await api('POST', `/api/imports/anomalies/${id}/resolve`, { decision });
  const el = document.getElementById(`status-${id}`);
  if (el) {
    el.textContent = decision;
    el.className = 'badge ' + (decision === 'APPROVED' ? 'badge-green' : decision === 'REJECTED' ? 'badge-red' : 'badge-yellow');
  }
  // Hide action buttons
  const row = document.getElementById(`anomaly-${id}`);
  if (row) {
    const actions = row.querySelector('.anomaly-actions');
    if (actions) actions.remove();
  }
  toast(`Anomaly ${decision.toLowerCase()}`);
}

async function approveAllAnomalies() {
  const buttons = document.querySelectorAll('.anomaly-actions button');
  for (const btn of buttons) {
    if (btn.textContent.includes('Approve')) btn.click();
    await new Promise(r => setTimeout(r, 50));
  }
}

async function copyReport() {
  if (!state.currentImportSession) return;
  try {
    const data = await api('GET', `/api/imports/sessions/${state.currentImportSession.id}/report`);
    await navigator.clipboard.writeText(data.report_text);
    toast('Report copied to clipboard');
  } catch {
    toast('Failed to copy report', 'error');
  }
}

function resetImport() {
  state.currentImportSession = null;
  document.getElementById('import-upload-section').classList.remove('hidden');
  document.getElementById('import-report-section').classList.add('hidden');
  document.getElementById('upload-zone').classList.remove('hidden');
  document.getElementById('import-loading').classList.add('hidden');
  document.getElementById('csv-file-input').value = '';
}

// ── Utilities ─────────────────────────────────────────────────────
function esc(s) {
  if (!s) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// Enter key on auth forms
document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('login-password')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
  document.getElementById('reg-password')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doRegister();
  });
});

// ── Boot ──────────────────────────────────────────────────────────
init();
