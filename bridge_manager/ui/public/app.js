const qs = (sel) => document.querySelector(sel);
const qsa = (sel) => Array.from(document.querySelectorAll(sel));

async function fetchRequests(params = {}) {
  const url = new URL('/api/requests', window.location.origin);
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  });
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to load requests');
  return res.json();
}

async function fetchRequest(id) {
  const res = await fetch(`/api/requests/${id}`);
  if (!res.ok) throw new Error('Failed to load request');
  return res.json();
}

function fmtDate(dt) {
  if (!dt) return '';
  const d = new Date(dt);
  if (Number.isNaN(d.getTime())) return String(dt);
  return d.toLocaleString();
}

function renderRows(rows) {
  const tbody = qs('#requests-body');
  tbody.innerHTML = rows.map(r => `
    <tr data-id="${r.id}" class="${rowClass(r.response_status)}">
      <td>${r.id}</td>
      <td><span class="badge ${sourceClass(r.source)}">${r.source || ''}</span></td>
      <td>${r.homeserver_id ?? ''}</td>
      <td>${r.bridge_id ?? ''}</td>
      <td><span class="badge ${methodClass(r.method)}">${r.method || ''}</span></td>
      <td>${statusBadge(r.response_status)}</td>
      <td>${escapeHtml(r.path || '')}</td>
      <td>${fmtDate(r.inbound_at)}</td>
      <td>${fmtDate(r.outbound_at)}</td>
      <td>${fmtDate(r.response_at)}</td>
    </tr>
  `).join('');
}

function renderDetails(r) {
  const el = qs('#details-content');
  el.innerHTML = `
    <div style="display:flex;gap:8px;align-items:center;margin-bottom:8px">
      <strong>ID:</strong> <span>${r.id}</span>
      <span class="badge source">${r.source || ''}</span>
      <span class="badge method">${r.method || ''}</span>
      <span class="badge">${escapeHtml(r.path || '')}</span>
    </div>
    <div class="details-grid">
      <details class="collapsible" open>
        <summary>
          Inbound Request
          <span class="summary-badge">${fmtSize(r.inbound_request)}</span>
        </summary>
        <div class="content">
          <pre class="code json">${formatJson(r.inbound_request)}</pre>
        </div>
      </details>
      <div id="divider-a" class="divider divider-vertical" role="separator" aria-orientation="vertical" aria-label="Resize pane"></div>
      <details class="collapsible" open>
        <summary>
          Outbound Request
          <span class="summary-badge">${fmtSize(r.outbound_request)}</span>
        </summary>
        <div class="content">
          <pre class="code json">${formatJson(r.outbound_request)}</pre>
        </div>
      </details>
      <div id="divider-b" class="divider divider-vertical" role="separator" aria-orientation="vertical" aria-label="Resize pane"></div>
      <details class="collapsible" open>
        <summary>
          Response
          <span class="summary-badge">${fmtSize(r.response)}</span>
        </summary>
        <div class="content">
          <pre class="code json">${formatJson(r.response)}</pre>
        </div>
      </details>
    </div>
  `;
  // Initialize grid widths and attach divider listeners after render
  initDetailsGrid();
}

function escapeHtml(str) {
  if (str == null) return '';
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function formatJson(value) {
  // Accept objects or JSON strings; pretty-print with 2-space indent.
  try {
    const obj = typeof value === 'string' ? JSON.parse(value) : value;
    return renderJson(obj);
  } catch (e) {
    // Fallback to raw string safely escaped
    const raw = typeof value === 'string' ? value : JSON.stringify(value);
    // Try to syntax highlight even the raw string if it looks like JSON
    try {
      const obj2 = JSON.parse(raw);
      return renderJson(obj2);
    } catch (_) {
      return escapeHtml(raw);
    }
  }
}

function fmtSize(val) {
  try {
    const str = typeof val === 'string' ? val : JSON.stringify(val);
    const bytes = new Blob([str]).size;
    if (bytes < 1024) return `${bytes} B`;
    const kb = (bytes / 1024).toFixed(1);
    return `${kb} KB`;
  } catch (_) {
    return '';
  }
}

function statusBadge(code) {
  if (code == null) return '';
  const c = Number(code);
  let cls = 'status-ok';
  if (c >= 500) cls = 'status-err';
  else if (c >= 400) cls = 'status-warn';
  return `<span class="badge ${cls}">${c}</span>`;
}

function rowClass(code) {
  if (code == null) return '';
  const c = Number(code);
  if (c >= 500) return 'row-err';
  if (c >= 400) return 'row-warn';
  return 'row-ok';
}

function sourceClass(source) {
  const s = (source || '').toLowerCase();
  if (s.includes('bridge')) return 'source-bridge';
  if (s.includes('hs') || s.includes('homeserver')) return 'source-hs';
  return 'source';
}

function methodClass(method) {
  const m = (method || '').toLowerCase();
  switch (m) {
    case 'get': return 'method-get';
    case 'post': return 'method-post';
    case 'put': return 'method-put';
    case 'delete': return 'method-delete';
    case 'patch': return 'method-patch';
    default: return 'method';
  }
}

function renderJson(value, level = 0) {
  const indent = '  '.repeat(level);
  const nl = '\n';

  const renderKey = (k) => `<span class="key">"${escapeHtml(k)}"</span>`;
  const renderString = (s) => `<span class="string">"${escapeHtml(s)}"</span>`;
  const renderNumber = (n) => `<span class="number">${n}</span>`;
  const renderBoolean = (b) => `<span class="boolean">${b}</span>`;
  const renderNull = () => `<span class="null">null</span>`;

  if (value === null) return renderNull();
  if (Array.isArray(value)) {
    if (value.length === 0) return '[]';
    let out = '[' + nl;
    for (let i = 0; i < value.length; i++) {
      out += indent + '  ' + renderJson(value[i], level + 1);
      out += i < value.length - 1 ? ',' + nl : nl;
    }
    out += indent + ']';
    return out;
  }
  const t = typeof value;
  if (t === 'string') return renderString(value);
  if (t === 'number') return renderNumber(value);
  if (t === 'boolean') return renderBoolean(value);
  if (t === 'object') {
    const keys = Object.keys(value);
    if (keys.length === 0) return '{}';
    let out = '{' + nl;
    keys.forEach((k, idx) => {
      out += indent + '  ' + renderKey(k) + ': ' + renderJson(value[k], level + 1);
      out += idx < keys.length - 1 ? ',' + nl : nl;
    });
    out += indent + '}';
    return out;
  }
  // Fallback
  return escapeHtml(String(value));
}

async function loadInitial() {
  qs('#requests-body').innerHTML = '<tr><td colspan="9" class="loading">Loading…</td></tr>';
  try {
    const rows = await fetchRequests({ limit: qs('#filter-limit').value });
    renderRows(rows);
  } catch (e) {
    qs('#requests-body').innerHTML = `<tr><td colspan="9" class="loading">${escapeHtml(e.message)}</td></tr>`;
  }
}

function buildFilters() {
  const source = qs('#filter-source').value.trim();
  const method = qs('#filter-method').value.trim();
  const homeserver_id = qs('#filter-hs').value.trim();
  const bridge_id = qs('#filter-bridge').value.trim();
  const limit = qs('#filter-limit').value.trim();
  const sinceRaw = qs('#filter-since').value;
  const since = sinceRaw ? new Date(sinceRaw).toISOString() : '';
  return { source, method, homeserver_id, bridge_id, limit, since };
}

function clearFilters() {
  qsa('.filters input').forEach(i => i.value = i.type === 'number' ? '' : '');
}

document.addEventListener('click', async (e) => {
  const tr = e.target.closest('tr[data-id]');
  if (tr) {
    // Highlight selected row
    qsa('#requests-body tr.selected').forEach(r => r.classList.remove('selected'));
    tr.classList.add('selected');
    const id = tr.getAttribute('data-id');
    try {
      const r = await fetchRequest(id);
      renderDetails(r);
    } catch (err) {
      renderDetails({ id, inbound_request: err.message });
    }
  }
});

// --- Horizontal pane resizing (top-level so renderDetails can call) ---
let detailsGrid = null;
const dividerA = () => qs('#divider-a');
const dividerB = () => qs('#divider-b');
let draggingCol = null;
let startX = 0;
let startWidths = null;

function readCols() {
  detailsGrid = qs('.details-grid');
  if (!detailsGrid) return ['', '', ''];
  const a = getComputedStyle(detailsGrid).getPropertyValue('--col-a').trim();
  const b = getComputedStyle(detailsGrid).getPropertyValue('--col-b').trim();
  const c = getComputedStyle(detailsGrid).getPropertyValue('--col-c').trim();
  return [a, b, c];
}
function setCols(a, b, c) {
  detailsGrid = qs('.details-grid');
  if (!detailsGrid) return;
  detailsGrid.style.setProperty('--col-a', a);
  detailsGrid.style.setProperty('--col-b', b);
  detailsGrid.style.setProperty('--col-c', c);
  detailsGrid.style.setProperty('--div-a', '6px');
  detailsGrid.style.setProperty('--div-b', '6px');
}
function px(n) { return `${n}px`; }

function beginColDrag(which, e) {
  detailsGrid = qs('.details-grid');
  if (!detailsGrid) return;
  draggingCol = which;
  startX = e.clientX;
  const rects = Array.from(detailsGrid.children)
    .filter(el => el.tagName.toLowerCase() === 'details')
    .map(el => el.getBoundingClientRect());
  startWidths = rects.map(r => r.width);
  document.body.style.cursor = 'col-resize';
  e.preventDefault();
}

function initDetailsGrid() {
  detailsGrid = qs('.details-grid');
  if (!detailsGrid) return;
  // Set default equal widths if unset
  const [a,b,c] = readCols();
  if (!a && !b && !c) {
    setCols('1fr','1fr','1fr');
  }
  const da = dividerA();
  const db = dividerB();
  if (da && !da._bound) { da.addEventListener('mousedown', (e) => beginColDrag('a', e)); da._bound = true; }
  if (db && !db._bound) { db.addEventListener('mousedown', (e) => beginColDrag('b', e)); db._bound = true; }
}

// Global mousemove handler for column dragging
window.addEventListener('mousemove', (e) => {
  if (draggingCol === null) return;
  detailsGrid = qs('.details-grid');
  if (!detailsGrid) return;
  const dx = e.clientX - startX;
  const minW = 200;
  const maxW = 1200;
  let [wa, wb, wc] = startWidths;
  if (draggingCol === 'a') {
    wa = Math.max(minW, Math.min(maxW, startWidths[0] + dx));
    wb = Math.max(minW, Math.min(maxW, startWidths[1] - dx));
  } else if (draggingCol === 'b') {
    wb = Math.max(minW, Math.min(maxW, startWidths[1] + dx));
    wc = Math.max(minW, Math.min(maxW, startWidths[2] - dx));
  }
  setCols(px(wa), px(wb), px(wc));
});

document.addEventListener('DOMContentLoaded', () => {
  loadInitial();
  qs('#apply-filters').addEventListener('click', async () => {
    qs('#requests-body').innerHTML = '<tr><td colspan="9" class="loading">Loading…</td></tr>';
    const filters = buildFilters();
    try {
      const rows = await fetchRequests(filters);
      renderRows(rows);
    } catch (e) {
      qs('#requests-body').innerHTML = `<tr><td colspan="9" class="loading">${escapeHtml(e.message)}</td></tr>`;
    }
  });
  qs('#clear-filters').addEventListener('click', async () => {
    clearFilters();
    loadInitial();
  });

  // Theme toggle: restore preference and bind button
  const root = document.documentElement;
  const savedTheme = localStorage.getItem('theme') || 'light';
  if (savedTheme === 'dark') root.classList.add('theme-dark');
  const themeBtn = document.getElementById('toggle-theme');
  if (themeBtn) {
    themeBtn.addEventListener('click', () => {
      const isDark = root.classList.toggle('theme-dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });
  }

  // Vertical resize for bottom panel
  const main = qs('main.layout');
  const divider = qs('#divider');
  const details = qs('#details');
  let dragging = false;
  let startY = 0;
  let startBottomHeight = 0;

  const minBottom = 180; // px
  const maxBottom = 80 * 16; // ~1280px

  function setBottomHeight(px) {
    const clamped = Math.max(minBottom, Math.min(maxBottom, px));
    main.style.setProperty('--bottom-row', clamped + 'px');
    main.style.setProperty('--divider-row', '6px');
    main.style.setProperty('--top-row', '1fr');
  }

  divider.addEventListener('mousedown', (e) => {
    dragging = true;
    startY = e.clientY;
    const rect = details.getBoundingClientRect();
    startBottomHeight = rect.height;
    document.body.style.cursor = 'row-resize';
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const dy = startY - e.clientY; // moving up increases bottom pane height
    setBottomHeight(startBottomHeight + dy);
  });

  function endDrag() {
    dragging = false;
    draggingCol = null;
    document.body.style.cursor = '';
  }
  window.addEventListener('mouseup', endDrag);
  window.addEventListener('mouseleave', endDrag);
  window.addEventListener('blur', endDrag);

  // Initialize bottom pane height from CSS variable (if any)
  const initial = parseInt(getComputedStyle(main).getPropertyValue('--bottom-row'));
  if (!isNaN(initial)) setBottomHeight(initial);

  // Horizontal resize for three panes
  function readCols() {
    const a = getComputedStyle(detailsGrid).getPropertyValue('--col-a').trim();
    const b = getComputedStyle(detailsGrid).getPropertyValue('--col-b').trim();
    const c = getComputedStyle(detailsGrid).getPropertyValue('--col-c').trim();
    return [a, b, c];
  }
  function setCols(a, b, c) {
    detailsGrid.style.setProperty('--col-a', a);
    detailsGrid.style.setProperty('--col-b', b);
    detailsGrid.style.setProperty('--col-c', c);
    detailsGrid.style.setProperty('--div-a', '6px');
    detailsGrid.style.setProperty('--div-b', '6px');
  }
  function px(n) { return `${n}px`; }

  function beginColDrag(which, e) {
    draggingCol = which;
    startX = e.clientX;
    const rects = Array.from(detailsGrid.children)
      .filter(el => el.tagName.toLowerCase() === 'details')
      .map(el => el.getBoundingClientRect());
    startWidths = rects.map(r => r.width);
    document.body.style.cursor = 'col-resize';
    e.preventDefault();
  }
  function initDetailsGrid() {
    detailsGrid = qs('.details-grid');
    if (!detailsGrid) return;
    // Set default equal widths if unset
    const [a,b,c] = readCols();
    if (!a && !b && !c) {
      setCols('1fr','1fr','1fr');
    }
    const da = dividerA();
    const db = dividerB();
    if (da && !da._bound) { da.addEventListener('mousedown', (e) => beginColDrag('a', e)); da._bound = true; }
    if (db && !db._bound) { db.addEventListener('mousedown', (e) => beginColDrag('b', e)); db._bound = true; }
  }

  // Note: column drag mousemove handler registered globally above
});
