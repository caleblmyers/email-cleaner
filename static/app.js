// ===== Selection state =====
const selectedIds = new Set();

function onCheckboxChange(el) {
  if (el.checked) {
    selectedIds.add(el.dataset.id);
  } else {
    selectedIds.delete(el.dataset.id);
  }
  updateBulkBar();
}

function updateBulkBar() {
  const bar = document.getElementById('bulk-bar');
  const countEl = document.getElementById('bulk-count');
  if (selectedIds.size > 0) {
    bar.classList.remove('hidden');
    countEl.textContent = selectedIds.size + ' selected';
  } else {
    bar.classList.add('hidden');
  }
}

function clearSelection() {
  selectedIds.clear();
  document.querySelectorAll('.email-select').forEach(cb => cb.checked = false);
  updateBulkBar();
}

function selectCategory(cat, checked) {
  const tbody = document.getElementById('tbody-' + cat);
  if (!tbody) return;
  tbody.querySelectorAll('.email-select').forEach(cb => {
    cb.checked = checked;
    if (checked) selectedIds.add(cb.dataset.id);
    else selectedIds.delete(cb.dataset.id);
  });
  updateBulkBar();
}

// ===== Category toggle =====
function toggleSection(cat) {
  const body = document.getElementById('body-' + cat);
  const toggle = document.getElementById('toggle-' + cat);
  if (!body) return;
  body.classList.toggle('collapsed');
  toggle.textContent = body.classList.contains('collapsed') ? '▶' : '▼';
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

// ===== Loading =====
function showLoading(show, msg = 'Loading...') {
  const overlay = document.getElementById('loading-overlay');
  const msgEl = document.getElementById('loading-msg');
  if (overlay) {
    if (show) {
      overlay.classList.remove('hidden');
      if (msgEl) msgEl.textContent = msg;
    } else {
      overlay.classList.add('hidden');
    }
  }
}

// ===== Generic action =====
async function performAction(path, body) {
  try {
    const resp = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.text();
      throw new Error(err);
    }
    return await resp.json();
  } catch (e) {
    showToast('Error: ' + e.message, true);
    throw e;
  }
}

// ===== Bulk actions =====
async function bulkAction(action) {
  if (selectedIds.size === 0) return;
  const ids = [...selectedIds];

  showLoading(true, `${action.charAt(0).toUpperCase() + action.slice(1)}ing ${ids.length} emails...`);
  try {
    const result = await performAction('/emails/actions/' + action, { email_ids: ids });
    showLoading(false);

    if (action === 'save') {
      showToast(`Saved ${result.success} emails to ${result.saved_to}`);
      clearSelection();
      return;
    }

    // Remove rows from DOM
    (result.succeeded_ids || []).forEach(id => {
      const row = document.querySelector(`tr[data-id="${id}"]`);
      if (row) row.remove();
      selectedIds.delete(id);
    });
    updateBulkBar();
    updateCategoryCounts();
    showToast(`Done: ${result.success} succeeded${result.failed ? ', ' + result.failed + ' failed' : ''}`);
  } catch (e) {
    showLoading(false);
  }
}

async function bulkMark(read) {
  if (selectedIds.size === 0) return;
  const ids = [...selectedIds];
  showLoading(true, (read ? 'Marking read...' : 'Marking unread...'));
  try {
    const result = await performAction('/emails/actions/mark', { email_ids: ids, read });
    showLoading(false);
    // Update visual state
    (result.succeeded_ids || []).forEach(id => {
      const row = document.querySelector(`tr[data-id="${id}"]`);
      if (row) {
        if (read) row.classList.remove('unread');
        else row.classList.add('unread');
      }
    });
    showToast(`Marked ${result.success} emails as ${read ? 'read' : 'unread'}`);
    clearSelection();
  } catch (e) {
    showLoading(false);
  }
}

// ===== Category quick actions =====
async function selectAndDelete(cat) {
  selectCategory(cat, true);
  await bulkAction('delete');
}

async function selectAndArchive(cat) {
  selectCategory(cat, true);
  await bulkAction('archive');
}

// ===== Move modal =====
function showMoveModal() {
  if (selectedIds.size === 0) return;
  document.getElementById('move-modal').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('move-modal').classList.add('hidden');
}

async function confirmMove() {
  const labelId = document.getElementById('label-select').value;
  if (!labelId) {
    showToast('Please select a label', true);
    return;
  }
  closeModal();
  const ids = [...selectedIds];
  showLoading(true, `Moving ${ids.length} emails...`);
  try {
    const result = await performAction('/emails/actions/move', { email_ids: ids, label_id: labelId });
    showLoading(false);
    (result.succeeded_ids || []).forEach(id => {
      const row = document.querySelector(`tr[data-id="${id}"]`);
      if (row) row.remove();
      selectedIds.delete(id);
    });
    updateBulkBar();
    updateCategoryCounts();
    showToast(`Moved ${result.success} emails`);
  } catch (e) {
    showLoading(false);
  }
}

// Close modal on backdrop click
document.addEventListener('click', e => {
  const modal = document.getElementById('move-modal');
  if (modal && e.target === modal) closeModal();
});

// ===== Fetch + classify =====
async function fetchAndClassify() {
  const btn = document.getElementById('fetch-btn');
  if (btn) btn.disabled = true;

  showLoading(true, 'Fetching emails from Gmail...');
  try {
    const fetchResult = await performAction('/emails/fetch', {});
    showLoading(true, `Fetched ${fetchResult.fetched} emails. Running AI classification...`);

    const classifyResult = await performAction('/emails/classify', {});
    showLoading(false);
    showToast(`Fetched ${fetchResult.fetched}, classified ${classifyResult.classified} emails`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
    if (btn) btn.disabled = false;
  }
}

async function reclassify() {
  const btn = document.getElementById('classify-btn');
  if (btn) btn.disabled = true;
  showLoading(true, 'Running AI classification on all emails...');
  try {
    const result = await performAction('/emails/classify', {});
    showLoading(false);
    showToast(`Classified ${result.classified} emails`);
    setTimeout(() => window.location.reload(), 1200);
  } catch (e) {
    showLoading(false);
    if (btn) btn.disabled = false;
  }
}

// ===== Update category header counts after row removal =====
function updateCategoryCounts() {
  document.querySelectorAll('.category-section').forEach(section => {
    const id = section.id.replace('section-', '');
    const tbody = document.getElementById('tbody-' + id);
    const countEl = section.querySelector('.category-count');
    if (tbody && countEl) {
      const count = tbody.querySelectorAll('tr.email-row').length;
      countEl.textContent = count + ' emails';
      if (count === 0) section.style.display = 'none';
    }
  });
}
