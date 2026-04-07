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
  document.querySelectorAll('.group-select').forEach(cb => cb.checked = false);
  updateBulkBar();
}

async function selectCategory(cat, checked) {
  const section = document.getElementById('section-' + cat);
  // Ensure group is loaded and expanded before selecting
  if (section && section.dataset.loaded === 'false') {
    section.dataset.loaded = 'true';
    const body = document.getElementById('body-' + cat);
    const toggle = document.getElementById('toggle-' + cat);
    if (body) { body.classList.remove('collapsed'); toggle.innerHTML = '&#9660;'; }
    await loadGroupEmails(cat);
  }
  const tbody = document.getElementById('tbody-' + cat);
  if (!tbody) return;
  tbody.querySelectorAll('.email-select').forEach(cb => {
    cb.checked = checked;
    if (checked) selectedIds.add(cb.dataset.id);
    else selectedIds.delete(cb.dataset.id);
  });
  updateBulkBar();
}

// ===== Group-level selection =====
async function onGroupCheckChange(el) {
  const sid = el.dataset.sid;
  const section = document.getElementById('section-' + sid);
  const checked = el.checked;

  if (checked) {
    // Ensure emails are loaded into cache
    if (!groupCache[sid]) {
      const groupName = section.dataset.groupName;
      const params = new URLSearchParams({ group_by: CURRENT_GROUP_BY, group_name: groupName });
      try {
        const resp = await fetch(`/emails/group?${params}`);
        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        groupCache[sid] = data.emails;
      } catch (e) {
        showToast('Error loading group: ' + e.message, true);
        el.checked = false;
        return;
      }
    }
    // Add all email IDs from this group
    groupCache[sid].forEach(e => selectedIds.add(e.id));
    // If group is expanded, check all row checkboxes too
    const tbody = document.getElementById('tbody-' + sid);
    if (tbody) {
      tbody.querySelectorAll('.email-select').forEach(cb => { cb.checked = true; });
    }
  } else {
    // Remove all email IDs from this group
    if (groupCache[sid]) {
      groupCache[sid].forEach(e => selectedIds.delete(e.id));
    }
    const tbody = document.getElementById('tbody-' + sid);
    if (tbody) {
      tbody.querySelectorAll('.email-select').forEach(cb => { cb.checked = false; });
    }
  }
  updateBulkBar();
}

// ===== Lazy loading + cache =====
const groupCache = {};

function renderEmailRow(email) {
  const unread = !email.is_read ? ' unread' : '';
  const sender = (email.sender || email.sender_email || 'Unknown').slice(0, 28);
  const subject = email.subject || '(no subject)';
  const snippet = email.snippet ? ` — ${email.snippet.slice(0, 80)}` : '';
  const dateFmt = email._date_fmt || '';
  const sizeFmt = email._size_fmt || '';
  const conf = email.confidence;
  const confPct = email._confidence_pct || 0;
  let badge;
  if (conf) {
    const cls = conf >= 0.8 ? 'badge-green' : conf >= 0.5 ? 'badge-yellow' : 'badge-red';
    badge = `<span class="badge ${cls}" title="${(email.reasoning || '').replace(/"/g, '&quot;')}">${confPct}%</span>`;
  } else {
    badge = '<span class="badge badge-gray">&mdash;</span>';
  }
  return `<tr class="email-row${unread}" data-id="${email.id}">
    <td class="col-check"><input type="checkbox" class="email-select" data-id="${email.id}" onchange="onCheckboxChange(this)"></td>
    <td class="col-sender" title="${(email.sender_email || '').replace(/"/g, '&quot;')}">${sender}</td>
    <td class="col-subject"><span class="subject-text">${subject}</span><span class="snippet-text">${snippet}</span></td>
    <td class="col-date">${dateFmt}</td>
    <td class="col-confidence">${badge}</td>
    <td class="col-size">${sizeFmt}</td>
  </tr>`;
}

async function loadGroupEmails(sid) {
  const section = document.getElementById('section-' + sid);
  const groupName = section.dataset.groupName;
  const tbody = document.getElementById('tbody-' + sid);

  // Check cache first
  if (groupCache[sid]) {
    tbody.innerHTML = groupCache[sid].map(renderEmailRow).join('');
    paginateCategory(sid);
    return;
  }

  // Fetch from server
  tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Loading...</td></tr>';
  try {
    const params = new URLSearchParams({ group_by: CURRENT_GROUP_BY, group_name: groupName });
    const resp = await fetch(`/emails/group?${params}`);
    if (!resp.ok) throw new Error(await resp.text());
    const data = await resp.json();
    groupCache[sid] = data.emails;
    tbody.innerHTML = data.emails.map(renderEmailRow).join('');
    paginateCategory(sid);
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="loading-cell">Failed to load emails</td></tr>`;
    showToast('Error loading group: ' + e.message, true);
  }
}

// ===== Category toggle =====
async function toggleSection(sid) {
  const body = document.getElementById('body-' + sid);
  const toggle = document.getElementById('toggle-' + sid);
  const section = document.getElementById('section-' + sid);
  if (!body) return;

  const isCollapsed = body.classList.contains('collapsed');
  if (isCollapsed) {
    body.classList.remove('collapsed');
    toggle.innerHTML = '&#9660;';
    if (section.dataset.loaded === 'false') {
      section.dataset.loaded = 'true';
      await loadGroupEmails(sid);
    }
  } else {
    body.classList.add('collapsed');
    toggle.innerHTML = '&#9654;';
  }
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

// ===== Confirmation modal =====
const LARGE_BATCH_THRESHOLD = 100;

function showConfirmModal(action, count, onConfirm) {
  const modal = document.getElementById('confirm-modal');
  const msgEl = document.getElementById('confirm-msg');
  const inputGroup = document.getElementById('confirm-input-group');
  const input = document.getElementById('confirm-input');
  const btn = document.getElementById('confirm-btn');
  const isLarge = count >= LARGE_BATCH_THRESHOLD;

  let msg = '';
  if (action === 'delete') {
    msg = `You are about to trash ${count.toLocaleString()} email(s). Gmail trash auto-empties after 30 days.`;
  } else if (action === 'archive') {
    msg = `You are about to archive ${count.toLocaleString()} email(s). They will be removed from your inbox.`;
  }

  msgEl.textContent = msg;

  if (isLarge) {
    inputGroup.classList.remove('hidden');
    input.value = '';
    input.placeholder = `Type "${action}" to confirm`;
    btn.disabled = true;
    input.oninput = () => {
      btn.disabled = input.value.trim().toLowerCase() !== action;
    };
  } else {
    inputGroup.classList.add('hidden');
    btn.disabled = false;
  }

  btn.onclick = () => {
    modal.classList.add('hidden');
    onConfirm();
  };
  document.getElementById('confirm-cancel-btn').onclick = () => {
    modal.classList.add('hidden');
  };

  modal.classList.remove('hidden');
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

    if (action === 'save') {
      showToast(`Saved ${result.success} emails to ${result.saved_to}`);
      clearSelection();
      return;
    }

    // Remove rows from DOM and invalidate cache
    const removedIds = new Set(result.succeeded_ids || []);
    removedIds.forEach(id => {
      document.querySelectorAll(`tr[data-id="${id}"]`).forEach(row => row.remove());
      selectedIds.delete(id);
    });
    // Remove from cache
    for (const sid in groupCache) {
      groupCache[sid] = groupCache[sid].filter(e => !removedIds.has(e.id));
    }
    // Uncheck group checkboxes
    document.querySelectorAll('.group-select').forEach(cb => cb.checked = false);
    updateBulkBar();
    updateCategoryCounts();

    const summary = `${result.success.toLocaleString()} ${action}d` +
      (result.failed ? `, ${result.failed} failed` : '');
    showToast(summary);
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
    const movedIds = new Set(result.succeeded_ids || []);
    movedIds.forEach(id => {
      document.querySelectorAll(`tr[data-id="${id}"]`).forEach(row => row.remove());
      selectedIds.delete(id);
    });
    for (const sid in groupCache) {
      groupCache[sid] = groupCache[sid].filter(e => !movedIds.has(e.id));
    }
    updateBulkBar();
    updateCategoryCounts();
    showToast(`Moved ${result.success} emails`);
  } catch (e) {
    showLoading(false);
  }
}

// Close modals on backdrop click
document.addEventListener('click', e => {
  const moveModal = document.getElementById('move-modal');
  if (moveModal && e.target === moveModal) closeModal();
  const confirmModal = document.getElementById('confirm-modal');
  if (confirmModal && e.target === confirmModal) confirmModal.classList.add('hidden');
});

// ===== Fetch emails (no classification) =====
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
    if (result.fetched === 0) {
      showToast('No new emails to fetch');
    } else {
      showToast(`Fetched ${result.fetched} emails`);
      setTimeout(() => window.location.reload(), 1200);
    }
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

// ===== Update category header counts after row removal =====
function updateCategoryCounts() {
  document.querySelectorAll('.category-section').forEach(section => {
    // Only update groups that have been loaded
    if (section.dataset.loaded !== 'true') return;
    const id = section.id.replace('section-', '');
    const cachedCount = groupCache[id] ? groupCache[id].length : null;
    const tbody = document.getElementById('tbody-' + id);
    const countEl = section.querySelector('.category-count');
    if (!countEl) return;

    const count = cachedCount !== null ? cachedCount : (tbody ? tbody.querySelectorAll('tr.email-row').length : 0);
    countEl.textContent = count + ' emails';

    if (count === 0 && tbody) {
      section.querySelector('.category-body').innerHTML =
        '<div class="empty-category">No emails in this group.</div>';
    }
  });
}

// ===== Group by switcher =====
function changeGroupBy(value) {
  const url = new URL(window.location.href);
  url.searchParams.set('group_by', value);
  window.location.href = url.toString();
}

// ===== Keyboard shortcuts =====
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;

  if (e.key === 'Escape') {
    const confirmModal = document.getElementById('confirm-modal');
    if (confirmModal && !confirmModal.classList.contains('hidden')) {
      confirmModal.classList.add('hidden');
      return;
    }
    const modal = document.getElementById('move-modal');
    if (modal && !modal.classList.contains('hidden')) {
      closeModal();
    } else if (selectedIds.size > 0) {
      clearSelection();
    }
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

// ===== Category pagination =====
const EMAILS_PER_PAGE = 50;
const categoryPages = {};

function paginateCategory(cat) {
  const tbody = document.getElementById('tbody-' + cat);
  if (!tbody) return;
  const rows = tbody.querySelectorAll('tr.email-row');
  if (rows.length <= EMAILS_PER_PAGE) return;

  if (!(cat in categoryPages)) categoryPages[cat] = 1;
  const page = categoryPages[cat];
  const start = (page - 1) * EMAILS_PER_PAGE;
  const end = start + EMAILS_PER_PAGE;
  const totalPages = Math.ceil(rows.length / EMAILS_PER_PAGE);

  rows.forEach((row, i) => {
    row.style.display = (i >= start && i < end) ? '' : 'none';
  });

  let pager = document.getElementById('pager-' + cat);
  if (!pager) {
    pager = document.createElement('div');
    pager.id = 'pager-' + cat;
    pager.className = 'category-pager';
    tbody.parentElement.after(pager);
  }
  pager.innerHTML = `
    <button class="btn btn-sm btn-ghost" ${page <= 1 ? 'disabled' : ''} onclick="changeCategoryPage('${cat}', -1)">&laquo; Prev</button>
    <span class="pager-info">Page ${page} of ${totalPages}</span>
    <button class="btn btn-sm btn-ghost" ${page >= totalPages ? 'disabled' : ''} onclick="changeCategoryPage('${cat}', 1)">Next &raquo;</button>
  `;
}

function changeCategoryPage(cat, delta) {
  categoryPages[cat] = (categoryPages[cat] || 1) + delta;
  paginateCategory(cat);
}

// Pagination is initialized when a group is expanded via loadGroupEmails()

// ===== Categories management =====
let categoriesCache = null;

async function fetchCategoriesData() {
  const resp = await fetch('/categories/');
  if (!resp.ok) throw new Error(await resp.text());
  categoriesCache = await resp.json();
  return categoriesCache;
}

function openCategoriesModal() {
  document.getElementById('categories-modal').classList.remove('hidden');
  renderCategories();
}

function closeCategoriesModal() {
  document.getElementById('categories-modal').classList.add('hidden');
}

async function renderCategories() {
  const container = document.getElementById('categories-list');
  container.innerHTML = '<div class="loading-cell">Loading...</div>';
  try {
    const cats = await fetchCategoriesData();
    if (cats.length === 0) {
      container.innerHTML = '<div class="empty-category">No categories defined.</div>';
      return;
    }
    container.innerHTML = cats.map(renderCategoryCard).join('');
  } catch (e) {
    container.innerHTML = '<div class="loading-cell">Failed to load categories</div>';
    showToast('Error loading categories: ' + e.message, true);
  }
}

function renderCategoryCard(cat) {
  const isUncategorized = cat.name === 'Uncategorized';
  const items = cat.description ? cat.description.split(',').map(s => s.trim()).filter(Boolean) : [];
  const itemsHtml = items.map(item =>
    `<span class="set-item">
      ${escapeHtml(item)}
      <button class="set-item-remove" onclick="removeSetItem(${cat.id}, '${escapeAttr(item)}')" title="Remove">&times;</button>
    </span>`
  ).join('');

  return `<div class="cat-card" data-id="${cat.id}">
    <div class="cat-card-header">
      <span class="cat-color-dot" style="background:${cat.color}"></span>
      <span class="cat-card-name" id="cat-name-${cat.id}">${escapeHtml(cat.name)}</span>
      <div class="cat-card-actions">
        <button class="btn btn-ghost btn-sm" onclick="editCategory(${cat.id})" title="Edit name/color">Edit</button>
        ${isUncategorized ? '' : `<button class="btn btn-ghost btn-sm btn-danger-text" onclick="deleteCategory(${cat.id}, '${escapeAttr(cat.name)}')" title="Delete">Delete</button>`}
      </div>
    </div>
    <div class="cat-set-items" id="set-items-${cat.id}">
      ${itemsHtml}
      <span class="set-item-add" onclick="showAddItemInput(${cat.id})">+ add item</span>
    </div>
    <div class="set-item-input-row hidden" id="add-item-row-${cat.id}">
      <input type="text" class="cat-input cat-input-sm" id="add-item-input-${cat.id}" placeholder="New descriptor item" onkeydown="if(event.key==='Enter')addSetItem(${cat.id})">
      <button class="btn btn-primary btn-sm" onclick="addSetItem(${cat.id})">Add</button>
      <button class="btn btn-ghost btn-sm" onclick="hideAddItemInput(${cat.id})">Cancel</button>
    </div>
  </div>`;
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

function escapeAttr(str) {
  return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function showAddItemInput(id) {
  const row = document.getElementById('add-item-row-' + id);
  row.classList.remove('hidden');
  document.getElementById('add-item-input-' + id).focus();
}

function hideAddItemInput(id) {
  document.getElementById('add-item-row-' + id).classList.add('hidden');
}

async function addSetItem(catId) {
  const input = document.getElementById('add-item-input-' + catId);
  const newItem = input.value.trim();
  if (!newItem) return;

  const cat = categoriesCache.find(c => c.id === catId);
  if (!cat) return;

  const items = cat.description ? cat.description.split(',').map(s => s.trim()).filter(Boolean) : [];
  if (items.includes(newItem)) {
    showToast('Item already exists', true);
    return;
  }
  items.push(newItem);
  const newDesc = items.join(', ');

  try {
    await fetch(`/categories/${catId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: newDesc }),
    });
    input.value = '';
    await renderCategories();
    showToast('Item added');
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function removeSetItem(catId, item) {
  const cat = categoriesCache.find(c => c.id === catId);
  if (!cat) return;

  const items = cat.description.split(',').map(s => s.trim()).filter(Boolean);
  const newItems = items.filter(i => i !== item);
  const newDesc = newItems.join(', ');

  try {
    await fetch(`/categories/${catId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ description: newDesc }),
    });
    await renderCategories();
    showToast('Item removed');
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function addCategory() {
  const name = document.getElementById('new-cat-name').value.trim();
  const color = document.getElementById('new-cat-color').value;
  const desc = document.getElementById('new-cat-desc').value.trim();
  if (!name) {
    showToast('Category name is required', true);
    return;
  }
  try {
    const resp = await fetch('/categories/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description: desc, color }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to create category');
    }
    document.getElementById('new-cat-name').value = '';
    document.getElementById('new-cat-desc').value = '';
    document.getElementById('new-cat-color').value = '#718096';
    await renderCategories();
    showToast(`Category "${name}" created`);
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function editCategory(catId) {
  const cat = categoriesCache.find(c => c.id === catId);
  if (!cat) return;

  const card = document.querySelector(`.cat-card[data-id="${catId}"]`);
  const header = card.querySelector('.cat-card-header');

  // Replace header with edit form
  header.innerHTML = `
    <input type="color" class="cat-color-input" id="edit-color-${catId}" value="${cat.color}">
    <input type="text" class="cat-input cat-input-sm" id="edit-name-${catId}" value="${escapeHtml(cat.name)}" style="flex:1">
    <button class="btn btn-primary btn-sm" onclick="saveCategory(${catId})">Save</button>
    <button class="btn btn-ghost btn-sm" onclick="renderCategories()">Cancel</button>
  `;
  document.getElementById('edit-name-' + catId).focus();
  document.getElementById('edit-name-' + catId).select();
}

async function saveCategory(catId) {
  const name = document.getElementById('edit-name-' + catId).value.trim();
  const color = document.getElementById('edit-color-' + catId).value;
  if (!name) {
    showToast('Name cannot be empty', true);
    return;
  }
  try {
    const resp = await fetch(`/categories/${catId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, color }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to update');
    }
    await renderCategories();
    showToast('Category updated');
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function deleteCategory(catId, catName) {
  if (!confirm(`Delete category "${catName}"? Emails with this category will be moved to Uncategorized.`)) return;
  try {
    const resp = await fetch(`/categories/${catId}`, { method: 'DELETE' });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to delete');
    }
    await renderCategories();
    showToast(`Category "${catName}" deleted`);
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

// Close categories modal on backdrop click
document.addEventListener('click', e => {
  const modal = document.getElementById('categories-modal');
  if (modal && e.target === modal) closeCategoriesModal();
});

// ===== Gmail labels management =====
let gmailLabelsCache = null;

async function fetchGmailLabels() {
  const resp = await fetch('/labels/');
  if (!resp.ok) throw new Error(await resp.text());
  gmailLabelsCache = await resp.json();
  return gmailLabelsCache;
}

function openGmailLabelsModal() {
  document.getElementById('gmail-labels-modal').classList.remove('hidden');
  renderGmailLabels();
}

function closeGmailLabelsModal() {
  document.getElementById('gmail-labels-modal').classList.add('hidden');
}

async function renderGmailLabels() {
  const container = document.getElementById('gmail-labels-list');
  container.innerHTML = '<div class="loading-cell">Loading...</div>';
  try {
    const labels = await fetchGmailLabels();
    if (labels.length === 0) {
      container.innerHTML = '<div class="empty-category">No user-created labels in Gmail.</div>';
      return;
    }
    container.innerHTML = labels.map(renderGmailLabelCard).join('');
  } catch (e) {
    container.innerHTML = '<div class="loading-cell">Failed to load labels</div>';
    showToast('Error loading Gmail labels: ' + e.message, true);
  }
}

function renderGmailLabelCard(label) {
  return `<div class="gmail-label-card" data-id="${label.id}">
    <div class="cat-card-header">
      <span class="gmail-label-icon">&#9679;</span>
      <span class="cat-card-name" id="gmail-label-name-${label.id}">${escapeHtml(label.name)}</span>
      <div class="cat-card-actions">
        <button class="btn btn-ghost btn-sm" onclick="editGmailLabel('${label.id}')" title="Rename">Rename</button>
        <button class="btn btn-ghost btn-sm btn-danger-text" onclick="deleteGmailLabel('${label.id}', '${escapeAttr(label.name)}')" title="Delete">Delete</button>
      </div>
    </div>
  </div>`;
}

async function createGmailLabel() {
  const input = document.getElementById('new-gmail-label-name');
  const name = input.value.trim();
  if (!name) {
    showToast('Label name is required', true);
    return;
  }
  try {
    const resp = await fetch('/labels/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to create label');
    }
    input.value = '';
    await renderGmailLabels();
    showToast(`Label "${name}" created`);
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function editGmailLabel(labelId) {
  const label = gmailLabelsCache.find(l => l.id === labelId);
  if (!label) return;

  const card = document.querySelector(`.gmail-label-card[data-id="${labelId}"]`);
  const header = card.querySelector('.cat-card-header');

  header.innerHTML = `
    <input type="text" class="cat-input cat-input-sm" id="edit-gmail-label-${labelId}" value="${escapeHtml(label.name)}" style="flex:1" onkeydown="if(event.key==='Enter')saveGmailLabel('${labelId}')">
    <button class="btn btn-primary btn-sm" onclick="saveGmailLabel('${labelId}')">Save</button>
    <button class="btn btn-ghost btn-sm" onclick="renderGmailLabels()">Cancel</button>
  `;
  const input = document.getElementById('edit-gmail-label-' + labelId);
  input.focus();
  input.select();
}

async function saveGmailLabel(labelId) {
  const name = document.getElementById('edit-gmail-label-' + labelId).value.trim();
  if (!name) {
    showToast('Name cannot be empty', true);
    return;
  }
  try {
    const resp = await fetch(`/labels/${labelId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to rename');
    }
    await renderGmailLabels();
    showToast('Label renamed');
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

async function deleteGmailLabel(labelId, labelName) {
  if (!confirm(`Delete Gmail label "${labelName}"? Emails with this label will NOT be deleted.`)) return;
  try {
    const resp = await fetch(`/labels/${labelId}`, { method: 'DELETE' });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Failed to delete');
    }
    await renderGmailLabels();
    showToast(`Label "${labelName}" deleted`);
  } catch (e) {
    showToast('Error: ' + e.message, true);
  }
}

// Close Gmail labels modal on backdrop click
document.addEventListener('click', e => {
  const modal = document.getElementById('gmail-labels-modal');
  if (modal && e.target === modal) closeGmailLabelsModal();
});
