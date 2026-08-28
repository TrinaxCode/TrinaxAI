import { APP_CONFIG } from './config';
import { systemFetch, systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload } from './api_errors';
import type { IndexJobStatus } from './api_documents';
import type { WebSearchSettings } from './api_types';

export const RAG_BASE = APP_CONFIG.ragBase;
export const OLLAMA_BASE = APP_CONFIG.ollamaBase;

export async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  const method = (init?.method || 'GET').toUpperCase();
  const safeToRetry = method === 'GET' || method === 'HEAD' || method === 'OPTIONS';
  for (let attempt = 0; attempt < (safeToRetry ? 2 : 1); attempt += 1) {
    let response: Response;
    try {
      response = await fetch(url, { ...init, headers: systemRequestHeaders(init?.headers) });
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') throw err;
      const failure = new ApiError('', 0);
      if (safeToRetry && attempt === 0 && failure.retryable) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        continue;
      }
      throw failure;
    }
    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      const failure = apiErrorFromPayload(response.status, detail.slice(0, 500));
      if (safeToRetry && attempt === 0 && failure.retryable) {
        await new Promise((resolve) => window.setTimeout(resolve, 250));
        continue;
      }
      throw failure;
    }
    try {
      return await response.json() as T;
    } catch {
      throw apiErrorFromPayload(response.status, null, 'invalid_response');
    }
  }
  throw new ApiError('', 0);
}
export async function startLocalAi(): Promise<void> {
  let response: Response;
  try {
    response = await systemFetch('/api/system/startup', { method: 'POST' });
  } catch {
    throw new ApiError('', 0, 'system_start_failed');
  }
  const raw = await response.text().catch(() => '');
  let payload: unknown;
  try { payload = raw ? JSON.parse(raw) as unknown : null; } catch { payload = null; }
  if (!response.ok || !(payload && typeof payload === 'object' && (payload as Record<string, unknown>).ok === true)) {
    throw apiErrorFromPayload(response.status, payload, 'system_start_failed');
  }
}

export function getWebSearchSettings(signal?: AbortSignal): Promise<WebSearchSettings> {
  return apiJson(`${RAG_BASE}/v1/settings/web-search`, { signal });
}

export function saveWebSearchSettings(update: {
  enabled?: boolean;
  preferred_provider?: 'auto' | 'duckduckgo' | 'brave' | 'searxng';
  brave_api_key?: string;
  searxng_url?: string;
}): Promise<WebSearchSettings> {
  return apiJson(`${RAG_BASE}/v1/settings/web-search`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(update),
  });
}

export const WEB_SEARCH_SETTINGS_EVENT = 'trinaxai:web-search-settings-updated';

export function notifyWebSearchSettingsUpdated(settings: WebSearchSettings): void {
  window.dispatchEvent(new CustomEvent(WEB_SEARCH_SETTINGS_EVENT, { detail: settings }));
}

export function testWebSearchProvider(provider: 'auto' | 'duckduckgo' | 'brave' | 'searxng'):
Promise<{ ok: boolean; provider: string; result_count: number }> {
  return apiJson(`${RAG_BASE}/v1/settings/web-search/test`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ provider }),
  });
}

export function deleteWebSearchCredential(provider: 'brave'): Promise<WebSearchSettings> {
  return apiJson(`${RAG_BASE}/v1/settings/web-search/credentials/${provider}`, { method: 'DELETE' });
}

export function resetWebSearchSettings(): Promise<WebSearchSettings> {
  return apiJson(`${RAG_BASE}/v1/settings/web-search`, { method: 'DELETE' });
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function validateIndexJobStatus(value: unknown): IndexJobStatus {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.status !== 'string') {
    throw new ApiError('', 502, 'invalid_response');
  }
  return {
    id: value.id,
    label: typeof value.label === 'string' ? value.label : '',
    path: typeof value.path === 'string' ? value.path : '',
    status: value.status,
    phase: typeof value.phase === 'string' ? value.phase : '',
    progress: typeof value.progress === 'number' ? value.progress : 0,
    eta_seconds: typeof value.eta_seconds === 'number' ? value.eta_seconds : null,
    elapsed_seconds: typeof value.elapsed_seconds === 'number' ? value.elapsed_seconds : 0,
    saved: typeof value.saved === 'number' ? value.saved : 0,
    skipped: typeof value.skipped === 'number' ? value.skipped : 0,
    bytes: typeof value.bytes === 'number' ? value.bytes : 0,
    indexed: Boolean(value.indexed),
    projects: Array.isArray(value.projects) ? value.projects.map(String) : [],
    collection_id: typeof value.collection_id === 'string' ? value.collection_id : undefined,
    collection_name: typeof value.collection_name === 'string' ? value.collection_name : undefined,
    output: typeof value.output === 'string' ? value.output : undefined,
    error: typeof value.error === 'string' ? value.error : undefined,
    cancel_requested: Boolean(value.cancel_requested),
    pages_total: typeof value.pages_total === 'number' ? value.pages_total : null,
    pages_processed: typeof value.pages_processed === 'number' ? value.pages_processed : 0,
    files_total: typeof value.files_total === 'number' ? value.files_total : 0,
    files_processed: typeof value.files_processed === 'number' ? value.files_processed : 0,
    chunks_generated: typeof value.chunks_generated === 'number' ? value.chunks_generated : 0,
    batches_total: typeof value.batches_total === 'number' ? value.batches_total : null,
    batches_processed: typeof value.batches_processed === 'number' ? value.batches_processed : 0,
    progress_exact: Boolean(value.progress_exact),
    recent_activity: typeof value.recent_activity === 'string' ? value.recent_activity : undefined,
  };
}
