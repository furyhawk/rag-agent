/**
 * RAG Agent Frontend — Vue 3 Application
 *
 * Pages: Dashboard, Documents, Document Detail, Collections, Search
 */
import { createApp, ref, reactive, computed, watch, onMounted, nextTick } from 'vue';
import api from './api.js';

/* ═══════════════════════════════════════════════════════════════
   Utilities
   ═══════════════════════════════════════════════════════════════ */
function fmtSize(bytes) {
  if (!bytes || bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}
function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}
function fmtDuration(isoStart, isoEnd) {
  if (!isoStart || !isoEnd) return '';
  const ms = new Date(isoEnd) - new Date(isoStart);
  if (ms < 1000) return '<1s';
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${s % 60}s`;
}
function truncate(str, len = 120) {
  if (!str) return '';
  return str.length > len ? str.slice(0, len) + '...' : str;
}

/* ═══════════════════════════════════════════════════════════════
   Store (shared reactive state)
   ═══════════════════════════════════════════════════════════════ */
const store = reactive({
  page: 'dashboard',
  documentId: null,           // for detail view
  notifications: [],
  health: null,
  collections: [],
  collectionsLoaded: false,
});

function addNotification(msg, type = 'success') {
  const id = Date.now() + Math.random();
  store.notifications.push({ id, msg, type });
  setTimeout(() => {
    const i = store.notifications.findIndex(n => n.id === id);
    if (i !== -1) store.notifications.splice(i, 1);
  }, 4000);
}

function navigate(page, documentId = null) {
  store.page = page;
  store.documentId = documentId;
  const hash = page + (documentId ? `/${documentId}` : '');
  history.pushState(null, '', `#${hash}`);
}

// Hash-based routing
function routeFromHash() {
  const hash = location.hash.slice(1) || 'dashboard';
  const parts = hash.split('/');
  store.page = parts[0];
  store.documentId = parts[1] || null;
}
window.addEventListener('hashchange', routeFromHash);
routeFromHash();

// Load health & collections on start
onMounted && setTimeout(() => {
  fetchHealth();
  fetchCollections();
}, 0);

async function fetchHealth() {
  try {
    // Use raw fetch so we can read the body even on 503 (degraded)
    const res = await fetch('/ready');
    const data = await res.json();
    store.health = data;
  } catch {
    try {
      const data = await api.health();
      store.health = data;
    } catch {
      store.health = { status: 'error', error: 'Cannot reach API' };
    }
  }
}
async function fetchCollections() {
  try {
    const data = await api.listCollections();
    store.collections = data.items || [];
    store.collectionsLoaded = true;
  } catch { store.collections = []; store.collectionsLoaded = true; }
}

/* ═══════════════════════════════════════════════════════════════
   Icons (inline SVG)
   ═══════════════════════════════════════════════════════════════ */
const Icons = {
  search: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>',
  upload: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
  folder: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  file: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>',
  trash: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  refresh: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
  download: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  plus: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  check: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  x: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  alert: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
  home: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>',
  db: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>',
  collections: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  doc: '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="15" x2="15" y2="15"/></svg>',
};

/* ═══════════════════════════════════════════════════════════════
   Page Components
   ═══════════════════════════════════════════════════════════════ */

/* ── Dashboard ────────────────────────────────────────────────── */
const DashboardPage = {
  template: `
    <div>
      <div class="stat-grid">
        <div class="stat-card">
          <span class="label">Collections</span>
          <span class="value">{{ stats.collections }}</span>
        </div>
        <div class="stat-card">
          <span class="label">Documents</span>
          <span class="value">{{ stats.documents }}</span>
        </div>
        <div class="stat-card">
          <span class="label">Total Vectors</span>
          <span class="value">{{ stats.vectors }}</span>
        </div>
        <div class="stat-card">
          <span class="label">Chunks</span>
          <span class="value">{{ stats.chunks }}</span>
        </div>
      </div>

      <div class="mb-4">
        <div class="card-title mb-2">System Health</div>
        <div class="health-grid">
          <div class="health-card" v-for="s in services" :key="s.name">
            <span class="indicator" :class="s.status"></span>
            <div>
              <div class="service-name">{{ s.name }}</div>
              <div class="service-status">{{ s.label }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <span class="card-title">Recent Documents</span>
          <button class="btn btn-sm btn-ghost" @click="navigate('documents')">View all</button>
        </div>
        <div v-if="loadingDocs" class="loading-state"><div class="text-muted">Loading…</div></div>
        <div v-else-if="recentDocs.length === 0" class="empty-state">
          <div v-html="icons.doc"></div>
          <div class="text-muted">No documents yet</div>
          <button class="btn btn-primary btn-sm mt-2" @click="navigate('documents')">Upload your first document</button>
        </div>
        <div v-else class="table-wrap" style="border:none;border-radius:0">
          <table>
            <thead><tr><th>Filename</th><th>Type</th><th>Size</th><th>Status</th><th>Created</th></tr></thead>
            <tbody>
              <tr v-for="doc in recentDocs" :key="doc.id" style="cursor:pointer" @click="viewDoc(doc.id)">
                <td class="truncate" style="max-width:250px">{{ doc.filename }}</td>
                <td><span class="badge" :class="'badge-' + (doc.filetype === 'pdf' ? 'processing' : 'done')">{{ doc.filetype?.toUpperCase() }}</span></td>
                <td>{{ fmtSize(doc.filesize) }}</td>
                <td><status-badge :status="doc.status" /></td>
                <td class="text-muted">{{ fmtDate(doc.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  setup() {
    const services = ref([
      { name: 'API', status: 'warn', label: 'Checking…' },
      { name: 'Database', status: 'warn', label: 'Checking…' },
      { name: 'Valkey', status: 'warn', label: 'Checking…' },
      { name: 'Milvus', status: 'warn', label: 'Checking…' },
    ]);
    const recentDocs = ref([]);
    const loadingDocs = ref(true);
    const stats = reactive({ collections: 0, documents: 0, vectors: 0, chunks: 0 });

    // Map the /ready response to health services
    watch(() => store.health, (h) => {
      if (!h) return;
      if (h.status === 'error') {
        services.value.forEach(s => { s.status = 'err'; s.label = 'Unreachable'; });
        return;
      }
      const checks = h.checks || {};
      function healthy(key) {
        return checks[key]?.status === 'healthy';
      }
      const svcs = [
        { name: 'API', status: 'ok', label: 'Running' },
        { name: 'Database', status: healthy('postgres') ? 'ok' : 'err', label: healthy('postgres') ? 'Connected' : 'Down' },
        { name: 'Valkey', status: healthy('valkey') ? 'ok' : 'err', label: healthy('valkey') ? 'Connected' : 'Down' },
        { name: 'Milvus', status: healthy('milvus') ? 'ok' : 'err', label: healthy('milvus') ? 'Connected' : 'Down' },
      ];
      services.value = svcs;
    }, { immediate: true });

    onMounted(async () => {
      // Load docs
      try {
        const data = await api.listDocuments({ per_page: 5, page: 1 });
        recentDocs.value = data.items || [];
      } catch { recentDocs.value = []; }
      loadingDocs.value = false;

      // Load stats from collections
      try {
        const cols = await api.listCollections();
        stats.collections = cols.total || 0;
        let vectors = 0;
        for (const c of cols.items || []) {
          vectors += c.total_vectors || 0;
        }
        stats.vectors = vectors;
      } catch {}

      // Load doc count
      try {
        const all = await api.listDocuments({ per_page: 1, page: 1 });
        stats.documents = all.total || 0;
        stats.chunks = recentDocs.value.reduce((s, d) => s + (d.chunk_count || 0), 0);
      } catch {}
    });

    function viewDoc(id) { navigate('document', id); }
    return { services, recentDocs, loadingDocs, stats, fmtSize, fmtDate, icons: Icons, navigate };
  }
};

/* ── Documents ────────────────────────────────────────────────── */
const DocumentsPage = {
  template: `
    <div>
      <!-- Upload zone -->
      <div class="upload-zone"
        :class="{ dragover: dragOver }"
        @click="triggerUpload"
        @dragover.prevent="dragOver = true"
        @dragleave="dragOver = false"
        @drop.prevent="handleDrop">
        <div v-html="icons.upload"></div>
        <div class="upload-text" v-if="!uploading && uploadQueue.length === 0">Drop files here or click to upload</div>
        <div class="upload-text" v-else-if="!uploading">{{ uploadQueue.length }} file(s) selected</div>
        <div class="upload-text" v-else>Uploading {{ uploadProgress }} / {{ uploadQueue.length }}…</div>
        <div class="upload-hint" v-if="!uploading && uploadQueue.length === 0">PDF, DOCX, TXT, MD — max 50MB each</div>
        <div class="upload-queue" v-if="uploadQueue.length > 0 && !uploading">
          <div v-for="(f, i) in uploadQueue" :key="i" class="upload-filename">{{ f.name }}</div>
        </div>
      </div>
      <input type="file" ref="fileInput" accept=".pdf,.docx,.txt,.md" multiple style="display:none" @change="onFileSelected" />

      <!-- Filter bar -->
      <div class="filter-bar">
        <div class="field">
          <label>Collection</label>
          <select class="select" v-model="filters.collection" @change="loadDocs(1)">
            <option value="">All</option>
            <option v-for="c in store.collections" :key="c.name" :value="c.name">{{ c.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Status</label>
          <select class="select" v-model="filters.status" @change="loadDocs(1)">
            <option value="">All</option>
            <option value="queued">Queued</option>
            <option value="processing">Processing</option>
            <option value="done">Done</option>
            <option value="error">Error</option>
          </select>
        </div>
        <div class="field">
          <label>Per page</label>
          <select class="select" v-model.number="perPage" @change="loadDocs(1)">
            <option :value="20">20</option>
            <option :value="50">50</option>
            <option :value="100">100</option>
          </select>
        </div>
        <div class="field">
          <label>&nbsp;</label>
          <button class="btn btn-ghost" @click="loadDocs(1)" v-html="icons.refresh"></button>
        </div>
      </div>

      <!-- Table -->
      <div v-if="loading" class="loading-state"><div class="text-muted">Loading documents…</div></div>
      <div v-else-if="docs.length === 0" class="empty-state">
        <div v-html="icons.doc"></div>
        <div class="text-muted">No documents found</div>
      </div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th class="sortable" :class="sortableCls('filename')" @click="toggleSort('filename')">
                Filename <span class="sort-arrow" v-html="sortArrow('filename')"></span>
              </th>
              <th class="sortable" :class="sortableCls('filetype')" @click="toggleSort('filetype')">
                Type <span class="sort-arrow" v-html="sortArrow('filetype')"></span>
              </th>
              <th class="sortable" :class="sortableCls('filesize')" @click="toggleSort('filesize')">
                Size <span class="sort-arrow" v-html="sortArrow('filesize')"></span>
              </th>
              <th class="sortable" :class="sortableCls('collection_name')" @click="toggleSort('collection_name')">
                Collection <span class="sort-arrow" v-html="sortArrow('collection_name')"></span>
              </th>
              <th class="sortable" :class="sortableCls('chunk_count')" @click="toggleSort('chunk_count')">
                Chunks <span class="sort-arrow" v-html="sortArrow('chunk_count')"></span>
              </th>
              <th class="sortable" :class="sortableCls('status')" @click="toggleSort('status')">
                Status <span class="sort-arrow" v-html="sortArrow('status')"></span>
              </th>
              <th class="sortable" :class="sortableCls('created_at')" @click="toggleSort('created_at')">
                Created <span class="sort-arrow" v-html="sortArrow('created_at')"></span>
              </th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in docs" :key="doc.id">
              <td class="truncate" style="max-width:220px;cursor:pointer" @click="viewDoc(doc.id)">{{ doc.filename }}</td>
              <td><span class="badge" :class="'badge-' + (doc.filetype === 'pdf' ? 'processing' : 'done')">{{ doc.filetype?.toUpperCase() }}</span></td>
              <td>{{ fmtSize(doc.filesize) }}</td>
              <td><span class="text-secondary">{{ doc.collection_name }}</span></td>
              <td>{{ doc.chunk_count }}</td>
              <td><status-badge :status="doc.status" /></td>
              <td class="text-muted">{{ fmtDate(doc.created_at) }}</td>
              <td class="actions">
                <button class="btn btn-icon btn-ghost btn-sm" title="Download" @click="downloadDoc(doc.id)" v-html="icons.download"></button>
                <button v-if="doc.status === 'error'" class="btn btn-icon btn-ghost btn-sm" title="Retry" @click="retryDoc(doc.id)" v-html="icons.refresh"></button>
                <button class="btn btn-icon btn-sm" :class="deleting === doc.id ? 'btn-ghost' : 'btn-ghost'" title="Delete" @click="confirmDelete(doc)"><span v-html="icons.trash"></span></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="pagination" v-if="totalPages > 1">
        <button class="page-btn" :disabled="page <= 1" @click="loadDocs(page - 1)">Prev</button>
        <template v-for="p in visiblePages" :key="p">
          <span v-if="p === '...'" class="page-info">…</span>
          <button v-else class="page-btn" :class="{ active: p === page }" @click="loadDocs(p)">{{ p }}</button>
        </template>
        <button class="page-btn" :disabled="page >= totalPages" @click="loadDocs(page + 1)">Next</button>
      </div>

      <!-- Delete confirmation modal -->
      <div class="modal-overlay" v-if="deleteTarget" @click.self="deleteTarget = null">
        <div class="modal">
          <h3>Delete document</h3>
          <p>Are you sure you want to delete <strong>{{ deleteTarget.filename }}</strong>? This cannot be undone.</p>
          <div class="modal-actions">
            <button class="btn" @click="deleteTarget = null">Cancel</button>
            <button class="btn btn-danger" @click="doDelete">Delete</button>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const docs = ref([]);
    const loading = ref(true);
    const page = ref(1);
    const total = ref(0);
    const perPage = ref(20);
    const sortBy = ref('created_at');
    const sortOrder = ref('desc');
    const filters = reactive({ collection: '', status: '' });
    const uploadQueue = ref([]);
    const uploading = ref(false);
    const uploadProgress = ref(0);
    const dragOver = ref(false);
    const fileInput = ref(null);
    const deleteTarget = ref(null);
    const deleting = ref(null);

    const totalPages = computed(() => Math.max(1, Math.ceil(total.value / perPage.value)));
    const visiblePages = computed(() => {
      const p = page.value, tp = totalPages.value;
      if (tp <= 7) return Array.from({ length: tp }, (_, i) => i + 1);
      const pages = [];
      pages.push(1);
      if (p > 3) pages.push('...');
      for (let i = Math.max(2, p - 1); i <= Math.min(tp - 1, p + 1); i++) pages.push(i);
      if (p < tp - 2) pages.push('...');
      pages.push(tp);
      return pages;
    });

    function toggleSort(column) {
      if (sortBy.value === column) {
        sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc';
      } else {
        sortBy.value = column;
        sortOrder.value = 'asc';
      }
      loadDocs(1);
    }

    function sortableCls(column) {
      return sortBy.value === column ? 'sorting-' + sortOrder.value : '';
    }

    function sortArrow(column) {
      if (sortBy.value !== column) return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px"><path d="M8 3l4 4-4 4M16 21l-4-4 4-4"/></svg>';
      if (sortOrder.value === 'asc') return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px"><polyline points="18 15 12 9 6 15"/></svg>';
      return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:12px;height:12px"><polyline points="6 9 12 15 18 9"/></svg>';
    }

    async function loadDocs(p) {
      page.value = p;
      loading.value = true;
      try {
        const params = { page: p, per_page: perPage.value };
        params.sort_by = sortBy.value;
        params.sort_order = sortOrder.value;
        if (filters.collection) params.collection_name = filters.collection;
        if (filters.status) params.status = filters.status;
        const data = await api.listDocuments(params);
        docs.value = data.items || [];
        total.value = data.total || 0;
      } catch (e) {
        addNotification(e.message, 'error');
        docs.value = [];
      }
      loading.value = false;
    }

    function triggerUpload() { fileInput.value?.click(); }
    function onFileSelected(e) {
      const files = Array.from(e.target.files || []);
      if (files.length) startUpload(files);
      e.target.value = '';
    }
    function handleDrop(e) {
      dragOver.value = false;
      const files = Array.from(e.dataTransfer?.files || []);
      if (files.length) startUpload(files);
    }
    function startUpload(files) {
      uploadQueue.value = files;
      uploadProgress.value = 0;
      uploadNext();
    }
    async function uploadNext() {
      if (uploadProgress.value >= uploadQueue.value.length) {
        uploading.value = false;
        uploadQueue.value = [];
        uploadProgress.value = 0;
        loadDocs(1);
        return;
      }
      uploading.value = true;
      const file = uploadQueue.value[uploadProgress.value];
      try {
        await api.uploadDocument(file);
        addNotification(`"${file.name}" uploaded and queued`, 'success');
      } catch (e) {
        addNotification(`"${file.name}": ${e.message}`, 'error');
      }
      uploadProgress.value++;
      uploadNext();
    }

    function viewDoc(id) { navigate('document', id); }
    function downloadDoc(id) { window.open(api.downloadUrl(id), '_blank'); }
    async function retryDoc(id) {
      try {
        await api.retryDocument(id);
        addNotification('Document re-queued for processing', 'success');
        loadDocs(page.value);
      } catch (e) { addNotification(e.message, 'error'); }
    }
    function confirmDelete(doc) { deleteTarget.value = doc; }
    async function doDelete() {
      const doc = deleteTarget.value;
      if (!doc) return;
      deleteTarget.value = null;
      try {
        await api.deleteDocument(doc.id);
        addNotification(`"${doc.filename}" deleted`, 'success');
        loadDocs(page.value);
      } catch (e) { addNotification(e.message, 'error'); }
    }

    onMounted(() => loadDocs(1));

    return { docs, loading, page, totalPages, visiblePages, perPage, sortBy, sortOrder, filters, uploadQueue, uploading, uploadProgress, dragOver, fileInput, deleteTarget, deleting,
      loadDocs, toggleSort, sortableCls, sortArrow, triggerUpload, onFileSelected, handleDrop, viewDoc, downloadDoc, retryDoc, confirmDelete, doDelete,
      fmtSize, fmtDate, store, icons: Icons, navigate };
  }
};

/* ── Document Detail ──────────────────────────────────────────── */
const DocumentDetailPage = {
  template: `
    <div>
      <div class="flex items-center gap-2 mb-4">
        <button class="btn btn-ghost btn-sm" @click="goBack">← Back</button>
      </div>
      <div v-if="loading" class="loading-state"><div class="text-muted">Loading document…</div></div>
      <div v-else-if="!doc" class="empty-state">
        <div class="text-muted">Document not found</div>
      </div>
      <div v-else>
        <div class="card mb-4">
          <div class="card-header">
            <div>
              <div class="card-title">{{ doc.filename }}</div>
              <div class="text-sm text-muted mt-2">ID: {{ doc.id }}</div>
            </div>
            <div class="flex gap-2">
              <button class="btn btn-sm" @click="downloadDoc" v-html="icons.download"> Download</button>
              <button v-if="doc.status === 'error'" class="btn btn-sm btn-danger" @click="retryDoc">Retry</button>
              <button class="btn btn-sm btn-danger" @click="showDelete = true">Delete</button>
            </div>
          </div>
          <div class="detail-grid">
            <div><span class="detail-label">Collection</span><div class="detail-value">{{ doc.collection_name }}</div></div>
            <div><span class="detail-label">Status</span><div><status-badge :status="doc.status" /></div></div>
            <div><span class="detail-label">File Type</span><div class="detail-value">{{ doc.filetype?.toUpperCase() }}</div></div>
            <div><span class="detail-label">File Size</span><div class="detail-value">{{ fmtSize(doc.filesize) }}</div></div>
            <div><span class="detail-label">Chunks</span><div class="detail-value">{{ doc.chunk_count }}</div></div>
            <div><span class="detail-label">Source Type</span><div class="detail-value">{{ doc.source_type }}</div></div>
            <div><span class="detail-label">Created</span><div class="detail-value">{{ fmtDate(doc.created_at) }}</div></div>
            <div><span class="detail-label">Completed</span><div class="detail-value">{{ fmtDate(doc.completed_at) }}</div></div>
            <div><span class="detail-label">Retry Count</span><div class="detail-value">{{ doc.retry_count }}</div></div>
            <div><span class="detail-label">Vector ID</span><div class="detail-value text-sm">{{ doc.vector_document_id || '—' }}</div></div>
            <div v-if="doc.content_hash"><span class="detail-label">Content Hash</span><div class="detail-value text-sm">{{ doc.content_hash }}</div></div>
          </div>
          <div v-if="doc.error_message" class="mt-4" style="background:var(--red-bg);padding:12px;border-radius:var(--radius);font-size:13px;color:var(--red)">
            <strong>Error:</strong> {{ doc.error_message }}
            <div v-if="doc.last_error" class="mt-2 text-sm">Previous: {{ doc.last_error }}</div>
          </div>
        </div>

        <!-- Delete modal -->
        <div class="modal-overlay" v-if="showDelete" @click.self="showDelete = false">
          <div class="modal">
            <h3>Delete document</h3>
            <p>Are you sure you want to delete <strong>{{ doc.filename }}</strong>? This cannot be undone.</p>
            <div class="modal-actions">
              <button class="btn" @click="showDelete = false">Cancel</button>
              <button class="btn btn-danger" @click="doDelete">Delete</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const doc = ref(null);
    const loading = ref(true);
    const showDelete = ref(false);

    async function load() {
      loading.value = true;
      try {
        const data = await api.getDocument(store.documentId);
        doc.value = data;
      } catch (e) {
        addNotification(e.message, 'error');
        doc.value = null;
      }
      loading.value = false;
    }
    onMounted(load);

    function goBack() { navigate('documents'); }
    function downloadDoc() { window.open(api.downloadUrl(doc.value.id), '_blank'); }
    async function retryDoc() {
      try {
        await api.retryDocument(doc.value.id);
        addNotification('Document re-queued', 'success');
        load();
      } catch (e) { addNotification(e.message, 'error'); }
    }
    async function doDelete() {
      showDelete.value = false;
      try {
        await api.deleteDocument(doc.value.id);
        addNotification('Document deleted', 'success');
        navigate('documents');
      } catch (e) { addNotification(e.message, 'error'); }
    }

    return { doc, loading, showDelete, goBack, downloadDoc, retryDoc, doDelete, fmtSize, fmtDate, icons: Icons };
  }
};

/* ── Collections ──────────────────────────────────────────────── */
const CollectionsPage = {
  template: `
    <div>
      <!-- Create -->
      <div class="card mb-4">
        <div class="card-title mb-2">Create Collection</div>
        <div class="flex gap-2">
          <input class="input" style="max-width:300px" v-model="newName" placeholder="Collection name"
            @keyup.enter="createCol" :disabled="creating" />
          <button class="btn btn-primary" @click="createCol" :disabled="creating || !newName.trim()">
            <span v-html="icons.plus"></span> Create
          </button>
        </div>
      </div>

      <!-- List -->
      <div v-if="!store.collectionsLoaded" class="loading-state"><div class="text-muted">Loading…</div></div>
      <div v-else-if="store.collections.length === 0" class="empty-state">
        <div v-html="icons.collections"></div>
        <div class="text-muted">No collections yet</div>
      </div>
      <div v-else class="collection-grid">
        <div v-for="col in store.collections" :key="col.name" class="collection-card" @click="viewCollection(col.name)">
          <div class="name">{{ col.name }}</div>
          <div class="stats">
            <span v-html="icons.db"></span>
            <span>{{ col.total_vectors }} vectors</span>
            <span>dim {{ col.dim }}</span>
          </div>
          <div class="card-actions">
            <button class="btn btn-sm btn-ghost" @click.stop="viewCollection(col.name)">View docs</button>
            <button class="btn btn-sm btn-ghost" @click.stop="confirmDrop(col)" style="color:var(--red)">Delete</button>
          </div>
        </div>
      </div>

      <!-- Drop confirmation -->
      <div class="modal-overlay" v-if="dropTarget" @click.self="dropTarget = null">
        <div class="modal">
          <h3>Delete collection</h3>
          <p>Are you sure you want to delete <strong>{{ dropTarget.name }}</strong>? All associated vectors will be removed.</p>
          <div class="modal-actions">
            <button class="btn" @click="dropTarget = null">Cancel</button>
            <button class="btn btn-danger" @click="doDrop">Delete</button>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const newName = ref('');
    const creating = ref(false);
    const dropTarget = ref(null);

    async function createCol() {
      const name = newName.value.trim();
      if (!name || creating.value) return;
      creating.value = true;
      try {
        await api.createCollection(name);
        addNotification(`Collection "${name}" created`, 'success');
        newName.value = '';
        await fetchCollections();
      } catch (e) { addNotification(e.message, 'error'); }
      creating.value = false;
    }

    function confirmDrop(col) { dropTarget.value = col; }
    async function doDrop() {
      const name = dropTarget.value.name;
      dropTarget.value = null;
      try {
        await api.deleteCollection(name);
        addNotification(`Collection "${name}" deleted`, 'success');
        await fetchCollections();
      } catch (e) { addNotification(e.message, 'error'); }
    }

    function viewCollection(name) {
      // Navigate to documents filtered by this collection
      store.page = 'documents';
      // Set a session-level filter — we handle this via a URL param
      navigate('documents');
      // We'll re-trigger with a custom event approach: set filter in store
      // Actually let's just navigate to documents — the user can select from the dropdown
      addNotification(`Showing collection "${name}" — select it from the filter dropdown`, 'success');
    }

    return { newName, creating, dropTarget, store, createCol, confirmDrop, doDrop, viewCollection, icons: Icons };
  }
};

/* ── Search ────────────────────────────────────────────────────── */
const SearchPage = {
  template: `
    <div>
      <!-- Search input -->
      <div class="search-input-wrap">
        <div class="search-input-icon" v-html="icons.search"></div>
        <input class="input" style="padding-left:44px;font-size:16px"
          v-model="query" placeholder="Search your documents…"
          @keyup.enter="doSearch" />
      </div>

      <!-- Options -->
      <div class="options-bar">
        <div class="field">
          <label>Collection</label>
          <select class="select" v-model="collectionName">
            <option value="">All collections</option>
            <option v-for="c in store.collections" :key="c.name" :value="c.name">{{ c.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>Results</label>
          <select class="select" v-model="limit">
            <option :value="5">5</option>
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </div>
        <div class="field" style="justify-content:flex-end">
          <label class="toggle">
            <input type="checkbox" v-model="useReranker" />
            <span class="toggle-track"></span>
            Reranker
          </label>
        </div>
        <div class="field" style="justify-content:flex-end">
          <label class="toggle">
            <input type="checkbox" v-model="multiCollection" />
            <span class="toggle-track"></span>
            Multi-collection
          </label>
        </div>
        <div class="field">
          <label>&nbsp;</label>
          <button class="btn btn-primary" @click="doSearch" :disabled="!query.trim() || searching">
            {{ searching ? 'Searching…' : 'Search' }}
          </button>
        </div>
      </div>

      <!-- Results -->
      <div v-if="searching" class="loading-state"><div class="text-muted">Searching…</div></div>
      <div v-else-if="hasSearched && results.length === 0" class="empty-state">
        <div v-html="icons.search"></div>
        <div class="text-muted">No results found for "{{ lastQuery }}"</div>
      </div>
      <div v-else-if="results.length > 0">
        <div class="text-sm text-muted mb-2">{{ results.length }} result(s) for "{{ lastQuery }}"</div>
        <div v-for="(r, i) in results" :key="i" class="search-result">
          <div class="result-header">
            <div style="font-size:13px;font-weight:500;color:var(--text-primary);flex:1;word-break:break-word">
              {{ r.metadata?.filename || r.metadata?.source || 'Document' }}
            </div>
            <div class="result-score">
              <span>{{ (r.score * 100).toFixed(0) }}%</span>
              <div class="score-bar">
                <div class="score-bar-fill" :style="{ width: (r.score * 100) + '%' }"></div>
              </div>
            </div>
          </div>
          <div class="result-content">{{ r.content }}</div>
          <div class="result-meta">
            <span title="Score">{{ (r.score * 100).toFixed(1) }}% match</span>
            <span v-if="r.metadata?.page_num">Page {{ r.metadata.page_num }}</span>
            <span v-if="r.parent_doc_id" title="Document ID">{{ r.parent_doc_id.slice(0, 8) }}…</span>
            <span v-if="r.metadata?.chunk_id" class="text-muted">Chunk {{ r.metadata.chunk_id.slice(0, 8) }}…</span>
          </div>
        </div>
      </div>
    </div>
  `,
  setup() {
    const query = ref('');
    const lastQuery = ref('');
    const collectionName = ref('');
    const limit = ref(10);
    const useReranker = ref(false);
    const multiCollection = ref(false);
    const searching = ref(false);
    const results = ref([]);
    const hasSearched = ref(false);

    async function doSearch() {
      const q = query.value.trim();
      if (!q) return;
      searching.value = true;
      hasSearched.value = true;
      lastQuery.value = q;
      try {
        const params = {
          query: q,
          limit: limit.value,
          use_reranker: useReranker.value,
        };
        if (multiCollection.value) {
          params.collection_names = collectionName.value
            ? [collectionName.value]
            : (store.collections.length > 0 ? store.collections.map(c => c.name) : ['documents']);
          const data = await api.multiSearch(params);
          results.value = data.results || [];
        } else {
          params.collection_name = collectionName.value || 'documents';
          const data = await api.search(params);
          results.value = data.results || [];
        }
      } catch (e) {
        addNotification(e.message, 'error');
        results.value = [];
      }
      searching.value = false;
    }

    return {
      query, lastQuery, collectionName, limit, useReranker, multiCollection, searching, results, hasSearched,
      doSearch, store, icons: Icons,
    };
  }
};

/* ═══════════════════════════════════════════════════════════════
   Shared components
   ═══════════════════════════════════════════════════════════════ */
const StatusBadge = {
  props: ['status'],
  template: `<span class="badge" :class="'badge-' + cls">{{ label }}</span>`,
  computed: {
    cls() {
      const m = { done: 'done', completed: 'done', error: 'error', failed: 'error', processing: 'processing', queued: 'queued', running: 'running', cancelled: 'cancelled' };
      return m[this.status] || 'queued';
    },
    label() { return (this.status || 'unknown').toUpperCase(); }
  }
};

/* ═══════════════════════════════════════════════════════════════
   App root
   ═══════════════════════════════════════════════════════════════ */
const app = createApp({
  setup() {
    const pageTitle = computed(() => {
      const titles = { dashboard: 'Dashboard', documents: 'Documents', document: 'Document Detail', collections: 'Collections', search: 'Search' };
      return titles[store.page] || 'RAG Agent';
    });
    const pageComponent = computed(() => {
      const map = { dashboard: DashboardPage, documents: DocumentsPage, document: DocumentDetailPage, collections: CollectionsPage, search: SearchPage };
      return map[store.page] || DashboardPage;
    });
    const isConnected = computed(() => store.health?.status === 'ready' || store.health?.status === 'ok');
    const statusLabel = computed(() => {
      if (store.health?.status === 'ready' || store.health?.status === 'ok') return 'Connected';
      if (store.health?.status === 'degraded') return 'Degraded';
      return store.health?.error || 'Offline';
    });

    return { store, pageTitle, pageComponent, isConnected, statusLabel, navigate, fmtDate, icons: Icons };
  },
  components: { StatusBadge },
});

app.component('status-badge', StatusBadge);
app.mount('#app');
