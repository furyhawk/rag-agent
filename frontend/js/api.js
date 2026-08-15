/**
 * RAG Agent API Client
 * Wraps all backend REST endpoints with error handling.
 */
class ApiClient {
  constructor(baseURL = '') {
    this.baseURL = baseURL;
  }

  async _fetch(path, options = {}) {
    const url = `${this.baseURL}${path}`;
    const res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try {
        const body = await res.json();
        msg = body.error || body.detail || msg;
      } catch {}
      throw new Error(msg);
    }
    return res.json();
  }

  // ── Health ──────────────────────────────────────────────
  health() {
    return this._fetch('/health');
  }
  ready() {
    return this._fetch('/ready');
  }

  // ── Collections ─────────────────────────────────────────
  listCollections() {
    return this._fetch('/api/v1/collections');
  }
  createCollection(name) {
    return this._fetch(`/api/v1/collections?name=${encodeURIComponent(name)}`, { method: 'POST' });
  }
  getCollection(name) {
    return this._fetch(`/api/v1/collections/${encodeURIComponent(name)}`);
  }
  deleteCollection(name) {
    return this._fetch(`/api/v1/collections/${encodeURIComponent(name)}`, { method: 'DELETE' });
  }
  getCollectionDocuments(name, params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this._fetch(`/api/v1/collections/${encodeURIComponent(name)}/documents${qs ? '?' + qs : ''}`);
  }

  // ── Documents ───────────────────────────────────────────
  listDocuments(params = {}) {
    const clean = Object.fromEntries(Object.entries(params).filter(([_, v]) => v !== '' && v !== null && v !== undefined));
    const qs = new URLSearchParams(clean).toString();
    return this._fetch(`/api/v1/documents${qs ? '?' + qs : ''}`);
  }
  getDocument(id) {
    return this._fetch(`/api/v1/documents/${id}`);
  }
  deleteDocument(id) {
    return this._fetch(`/api/v1/documents/${id}`, { method: 'DELETE' });
  }
  retryDocument(id) {
    return this._fetch(`/api/v1/documents/${id}/retry`, { method: 'POST' });
  }
  downloadUrl(id) {
    return `${this.baseURL}/api/v1/documents/${id}/download`;
  }
  imageUrl(id) {
    return `${this.baseURL}/api/v1/images/${encodeURIComponent(id)}`;
  }
  // Fetch a stored image as a base64 data URI (data:image/png;base64,...)
  async imageDataUri(id) {
    const url = `${this.baseURL}/api/v1/images/${encodeURIComponent(id)}`;
    const res = await fetch(url);
    if (!res.ok) {
      let msg = `Image request failed (${res.status})`;
      try { const body = await res.json(); msg = body.error || body.detail || msg; } catch {}
      throw new Error(msg);
    }
    return res.text();
  }
  documentImages(documentId, collectionName = 'documents') {
    const qs = new URLSearchParams({ collection_name: collectionName }).toString();
    return this._fetch(`/api/v1/documents/${encodeURIComponent(documentId)}/images?${qs}`);
  }

  async uploadDocument(file, collectionName = 'documents', replace = true) {
    const fd = new FormData();
    fd.append('file', file);
    const qs = new URLSearchParams({ collection_name: collectionName, replace }).toString();
    const res = await fetch(`${this.baseURL}/api/v1/documents/upload?${qs}`, { method: 'POST', body: fd });
    if (!res.ok) {
      let msg = 'Upload failed';
      try { const b = await res.json(); msg = b.error || b.detail || msg; } catch {}
      throw new Error(msg);
    }
    return res.json();
  }

  // ── Search ──────────────────────────────────────────────
  search(params) {
    const body = {
      query: params.query,
      collection_name: params.collection_name || 'documents',
      limit: params.limit || 5,
      min_score: params.min_score ?? 0.0,
      use_reranker: !!params.use_reranker,
    };
    return this._fetch('/api/v1/search', { method: 'POST', body: JSON.stringify(body) });
  }

  multiSearch(params) {
    const body = {
      query: params.query,
      collection_names: params.collection_names || ['documents'],
      limit: params.limit || 5,
      min_score: params.min_score ?? 0.0,
      use_reranker: !!params.use_reranker,
    };
    return this._fetch('/api/v1/search/multi', { method: 'POST', body: JSON.stringify(body) });
  }

  // ── Sync ────────────────────────────────────────────────
  triggerSync(params) {
    const qs = new URLSearchParams(params).toString();
    return this._fetch(`/api/v1/sync?${qs}`, { method: 'POST' });
  }
  getSyncLogs() {
    return this._fetch('/api/v1/sync/logs');
  }
  getConnectors() {
    return this._fetch('/api/v1/connectors');
  }
}

// Export singleton
const api = new ApiClient();
export default api;
