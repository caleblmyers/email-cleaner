// ===== Selection state =====
const selectedIds = new Set();

function onCheckboxChange(el) {
  if (el.checked) selectedIds.add(el.dataset.id);
  else selectedIds.delete(el.dataset.id);
  updateBulkBar();
}

function updateBulkBar() {
  const bar = document.getElementById('bulk-bar');
  const countEl = document.getElementById('bulk-count');
  if (selectedIds.size > 0) {
    bar.classList.remove('hidden');
    countEl.innerHTML = `<strong>${selectedIds.size} selected</strong>`;
  } else {
    bar.classList.add('hidden');
  }
}

function clearSelection() {
  selectedIds.clear();
  document.querySelectorAll('.email-select').forEach(cb => cb.checked = false);
  document.querySelectorAll('.group-select').forEach(cb => cb.checked = false);
  updateBulkBar();
}

// ===== Group-level selection =====
async function onGroupCheckChange(el) {
  const sid = el.dataset.sid;
  const checked = el.checked;
  const section = document.getElementById('section-' + sid);
  const body = document.getElementById('body-' + sid);

  if (checked) {
    // Check any visible checkboxes in the DOM
    const container = body || section;
    if (container) {
      container.querySelectorAll('.email-select').forEach(cb => {
        cb.checked = true;
        selectedIds.add(cb.dataset.id);
      });
    }
    // Also fetch IDs from the server for emails not yet in the DOM
    const hxEl = body || section?.querySelector('[hx-get]');
    const url = hxEl?.getAttribute('hx-get');
    if (url) {
      const jsonUrl = url.replace('/group/html', '/group').replace('/subgroup/html', '/subgroup');
      try {
        const resp = await fetch(jsonUrl);
        if (resp.ok) {
          const data = await resp.json();
          (data.emails || []).forEach(e => selectedIds.add(e.id));
        }
      } catch (e) { /* DOM selection is enough */ }
    }
  } else {
    const container = body || section;
    if (container) {
      container.querySelectorAll('.email-select').forEach(cb => {
        cb.checked = false;
        selectedIds.delete(cb.dataset.id);
      });
    }
  }
  updateBulkBar();
}

// ===== Toast =====
let toastTimer = null;
function showToast(msg, isError = false) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.className = 'toast' + (isError ? ' error' : '');
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = 'toast hidden'; }, 4000);
}

// ===== Loading overlay =====
function showLoading(show, msg = 'Loading...') {
  const overlay = document.getElementById('loading-overlay');
  const msgEl = document.getElementById('loading-msg');
  if (!overlay) return;
  if (show) {
    if (msgEl) msgEl.textContent = msg;
    overlay.showModal();
  } else {
    overlay.close();
  }
}

// ===== Generic JSON action =====
async function performAction(path, body) {
  try {
    const resp = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) throw new Error(await resp.text());
    return await resp.json();
  } catch (e) {
    showToast('Error: ' + e.message, true);
    throw e;
  }
}

// ===== Confirmation dialog =====
const LARGE_BATCH_THRESHOLD = 100;

function showConfirmModal(action, count, onConfirm) {
  const modal = document.getElementById('confirm-modal');
  const msgEl = document.getElementById('confirm-msg');
  const inputGroup = document.getElementById('confirm-input-group');
  const input = document.getElementById('confirm-input');
  const btn = document.getElementById('confirm-btn');
  const isLarge = count >= LARGE_BATCH_THRESHOLD;

  if (action === 'delete') {
    msgEl.textContent = `You are about to trash ${count.toLocaleString()} email(s). Gmail trash auto-empties after 30 days.`;
  } else if (action === 'archive') {
    msgEl.textContent = `You are about to archive ${count.toLocaleString()} email(s). They will be removed from your inbox.`;
  }

  if (isLarge) {
    inputGroup.classList.remove('hidden');
    input.value = '';
    input.placeholder = `Type "${action}" to confirm`;
    btn.disabled = true;
    input.oninput = () => { btn.disabled = input.value.trim().toLowerCase() !== action; };
  } else {
    inputGroup.classList.add('hidden');
    btn.disabled = false;
  }

  btn.onclick = () => { modal.close(); onConfirm(); };
  document.getElementById('confirm-cancel-btn').onclick = () => modal.close();

  modal.showModal();
  if (isLarge) input.focus();
}

// ===== Bulk actions =====
async function bulkAction(action) {
  if (selectedIds.size === 0) return;
  const ids = [...selectedIds];

  if (action === 'delete' || action === 'archive') {
    return new Promise(resolve => {
      showConfirmModal(action, ids.length, async () => {
        await _executeBulkAction(action, ids);
        resolve();
      });
    });
  }
  await _executeBulkAction(action, ids);
}

async function _executeBulkAction(action, ids) {
  showLoading(true, `${action.charAt(0).toUpperCase() + action.slice(1)}ing ${ids.length.toLocaleString()} emails...`);
  try {
    const result = await performAction('/emails/actions/' + action, { email_ids: ids });
    showLoading(false);
    const summary = action === 'save'
      ? `Saved ${result.success} emails to ${result.saved_to}`
      : `${result.success.toLocaleString()} ${action}d` + (result.failed ? `, ${result.failed} failed` : '');
    showToast(summary);
    if (action !== 'save') setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
  }
}

async function bulkMark(read) {
  if (selectedIds.size === 0) return;
  const ids = [...selectedIds];
  showLoading(true, read ? 'Marking read...' : 'Marking unread...');
  try {
    const result = await performAction('/emails/actions/mark', { email_ids: ids, read });
    showLoading(false);
    showToast(`Marked ${result.success} emails as ${read ? 'read' : 'unread'}`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
  }
}

// ===== Move dialog =====
function showMoveModal() {
  if (selectedIds.size === 0) return;
  document.getElementById('move-modal').showModal();
  htmx.trigger(document.getElementById('label-select'), 'load-move-labels');
}

function closeModal() {
  document.getElementById('move-modal').close();
}

async function confirmMove() {
  const labelId = document.getElementById('label-select').value;
  if (!labelId) { showToast('Please select a label', true); return; }
  closeModal();
  const ids = [...selectedIds];
  showLoading(true, `Moving ${ids.length} emails...`);
  try {
    const result = await performAction('/emails/actions/move', { email_ids: ids, label_id: labelId });
    showLoading(false);
    showToast(`Moved ${result.success} emails`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
  }
}

// ===== Fetch emails =====
async function fetchEmails() {
  const btn = document.getElementById('fetch-btn');
  if (btn) btn.disabled = true;
  const countSelect = document.getElementById('fetch-count');
  const val = countSelect ? countSelect.value : '50';
  const fetchAll = val === 'all';
  const maxResults = fetchAll ? 500 : parseInt(val, 10);

  showLoading(true, fetchAll ? 'Fetching all emails from Gmail...' : `Fetching up to ${maxResults} emails from Gmail...`);
  try {
    const result = await performAction('/emails/fetch', { max_results: maxResults, fetch_all: fetchAll });
    showLoading(false);
    if (result.fetched === 0) showToast('No new emails to fetch');
    else { showToast(`Fetched ${result.fetched} emails`); setTimeout(() => window.location.reload(), 1200); }
  } catch (e) {
    showLoading(false);
    if (btn) btn.disabled = false;
  }
}

// ===== Classify emails =====
async function classifyEmails() {
  const btn = document.getElementById('classify-btn');
  if (btn) btn.disabled = true;
  const countSelect = document.getElementById('classify-count');
  const limit = countSelect ? parseInt(countSelect.value, 10) : 0;
  const body = limit > 0 ? { limit } : {};

  showLoading(true, `Running AI classification on ${limit > 0 ? limit : 'all'} emails...`);
  try {
    const result = await performAction('/emails/classify', body);
    showLoading(false);
    const cost = result.usage ? ` ($${result.usage.total_cost.toFixed(4)})` : '';
    showToast(`Classified ${result.classified} emails${cost}`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
    if (btn) btn.disabled = false;
  }
}

// ===== Group by switcher =====
function changeGroupBy(value) {
  const url = new URL(window.location.href);
  url.searchParams.set('group_by', value);
  if (url.searchParams.get('then_by') === value) url.searchParams.delete('then_by');
  window.location.href = url.toString();
}

function changeThenBy(value) {
  const url = new URL(window.location.href);
  if (value) url.searchParams.set('then_by', value);
  else url.searchParams.delete('then_by');
  window.location.href = url.toString();
}

// ===== Open management dialogs =====
let pendingReload = false;

function openCategoriesModal() {
  const modal = document.getElementById('categories-modal');
  modal.showModal();
  htmx.trigger(document.getElementById('categories-list'), 'load-categories');
}

function openGmailLabelsModal() {
  const modal = document.getElementById('gmail-labels-modal');
  modal.showModal();
  htmx.trigger(document.getElementById('gmail-labels-list'), 'load-labels');
}

// Track HTMX mutations for reload on dialog close
document.body.addEventListener('htmx:afterRequest', e => {
  const method = (e.detail.requestConfig?.verb || '').toUpperCase();
  if (method === 'POST' || method === 'PUT' || method === 'DELETE') {
    pendingReload = true;
  }
});

// Reload when a dialog with pending changes is closed
document.querySelectorAll('dialog').forEach(dialog => {
  dialog.addEventListener('close', () => {
    if (pendingReload) {
      pendingReload = false;
      window.location.reload();
    }
  });
});

// ===== Keyboard shortcuts =====
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

  if (e.key === 'Escape') {
    if (selectedIds.size > 0) clearSelection();
  }

  if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
    e.preventDefault();
    document.querySelectorAll('.email-select').forEach(cb => {
      cb.checked = true;
      selectedIds.add(cb.dataset.id);
    });
    updateBulkBar();
  }
});
