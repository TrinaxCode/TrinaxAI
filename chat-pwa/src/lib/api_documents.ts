import { systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload } from './api_errors';
import { apiJson, RAG_BASE, isRecord, validateIndexJobStatus } from './api_http';
import {
  DEFAULT_MODEL_SETTINGS,
  INDEXABLE_EXTENSIONS,
  INDEXABLE_FILENAMES,
  aggressiveQuantizationEnabled,
  modelSetting,
} from './api_models';
import type { ChatEngine, ChatMessage } from './api_types';

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  engine: ChatEngine;
  createdAt: number;
  updatedAt: number;
  folderId?: string;
  /** Ephemeral conversations stay in memory only and never enter history. */
  temporary?: boolean;
}
export interface ChatFolder {
  id: string;
  name: string;
  createdAt: number;
  updatedAt: number;
}

export interface FolderImportResult {
  ok: boolean;
  job_id?: string;
  indexed: boolean;
  path: string;
  saved: number;
  skipped: number;
  bytes: number;
  projects: string[];
  collection_id?: string;
  collection_name?: string;
  output?: string;
}

export interface IndexJobStatus {
  id: string;
  label: string;
  path: string;
  status: 'saving' | 'indexing' | 'completed' | 'failed' | 'cancelled' | string;
  phase: string;
  progress: number;
  eta_seconds: number | null;
  elapsed_seconds: number;
  saved: number;
  skipped: number;
  bytes: number;
  indexed: boolean;
  projects: string[];
  collection_id?: string;
  collection_name?: string;
  output?: string;
  error?: string;
  cancel_requested?: boolean;
  pages_total?: number | null;
  pages_processed: number;
  files_total: number;
  files_processed: number;
  chunks_generated: number;
  batches_total?: number | null;
  batches_processed: number;
  progress_exact: boolean;
  recent_activity?: string;
}

export interface Collection {
  id: string;
  name: string;
  created_at: number;
  updated_at: number;
}

export interface ExtractedDocument {
  ok: boolean;
  name: string;
  text: string;
  chars: number;
  truncated: boolean;
}

export function folderLabelFromFiles(files: FileList | File[]): string {
  const first = Array.from(files)[0] as File & { webkitRelativePath?: string };
  const rel = first?.webkitRelativePath || first?.name || 'import';
  return rel.split('/')[0] || 'import';
}

function isIndexableFile(file: File): boolean {
  const rel = ((file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name || '').toLowerCase();
  const filename = rel.split('/').pop() || rel;
  if (INDEXABLE_FILENAMES.has(filename)) return true;
  const dot = filename.lastIndexOf('.');
  if (dot < 0) return false;
  return INDEXABLE_EXTENSIONS.has(filename.slice(dot));
}

export function indexableFilesFrom(files: FileList | File[]): File[] {
  return Array.from(files).filter(isIndexableFile);
}
export function startFolderIndex(
  files: FileList | File[],
  options: {
    signal?: AbortSignal;
    onUploadProgress?: (progress: number) => void;
    collectionId?: string;
    watchId?: string;
    embedModel?: string;
    aggressiveQuant?: boolean;
  } = {},
): Promise<FolderImportResult> {
  const selected = Array.from(files);
  if (selected.length === 0) throw new Error('No files selected.');
  const indexable = indexableFilesFrom(selected);
  if (indexable.length === 0) throw new Error('No indexable files selected.');
  const label = folderLabelFromFiles(selected);
  const form = new FormData();
  form.append('label', label);
  form.append('collection_id', options.collectionId || 'default');
  if (options.watchId) form.append('watch_id', options.watchId);
  form.append('embed_model', options.embedModel || modelSetting('tc-models-embed', DEFAULT_MODEL_SETTINGS['tc-models-embed']));
  form.append('aggressive_quant', String(options.aggressiveQuant ?? aggressiveQuantizationEnabled()));
  indexable.forEach((file) => {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append('files', file, rel);
  });

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const onAbort = () => xhr.abort();
    const finish = () => options.signal?.removeEventListener('abort', onAbort);
    xhr.open('POST', `${RAG_BASE}/system/index-upload`);
    // The request only uploads and enqueues the durable job; processing itself
    // continues asynchronously and must never hold this connection forever.
    xhr.timeout = 5 * 60_000;
    const credentialHeaders = systemRequestHeaders();
    for (const name of ['X-Admin-Token', 'X-TrinaxAI-Device-Token']) {
      const value = credentialHeaders.get(name);
      if (value) xhr.setRequestHeader(name, value);
    }
    xhr.responseType = 'json';
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onUploadProgress?.(Math.round((event.loaded / event.total) * 30));
      }
    };
    xhr.onload = () => {
      finish();
      const result = xhr.response || {};
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(apiErrorFromPayload(xhr.status, result));
        return;
      }
      try {
        localStorage.setItem('tc-last-index-import', JSON.stringify({
          label,
          path: result.path,
          saved: result.saved,
          skipped: result.skipped,
          indexedAt: Date.now(),
          jobId: result.job_id,
          collectionId: result.collection_id,
          collectionName: result.collection_name,
        }));
      } catch { /* ignore */ }
      options.onUploadProgress?.(30);
      resolve(result as FolderImportResult);
    };
    xhr.onerror = () => { finish(); reject(new ApiError('', 0)); };
    xhr.ontimeout = () => { finish(); reject(new ApiError('Folder import upload timed out.', 0)); };
    xhr.onabort = () => { finish(); reject(new DOMException('Upload cancelled', 'AbortError')); };
    if (options.signal?.aborted) {
      reject(new DOMException('Upload cancelled', 'AbortError'));
      return;
    }
    options.signal?.addEventListener('abort', onAbort, { once: true });
    xhr.send(form);
  });
}

export async function getIndexJob(jobId: string, signal?: AbortSignal): Promise<IndexJobStatus> {
  const response = await fetch(`${RAG_BASE}/system/index-jobs/${encodeURIComponent(jobId)}`, { signal, headers: systemRequestHeaders() });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw apiErrorFromPayload(response.status, detail);
  }
  const data = await response.json().catch(() => null);
  return validateIndexJobStatus(data);
}

export async function cancelIndexJob(jobId: string, signal?: AbortSignal): Promise<IndexJobStatus | null> {
  const response = await fetch(`${RAG_BASE}/system/index-jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
    signal,
    headers: systemRequestHeaders(),
  });
  if (!response.ok) return null;
  const data = await response.json().catch(() => null);
  if (!isRecord(data) || !data.job) return null;
  return validateIndexJobStatus(data.job);
}

export async function retryIndexJob(jobId: string, signal?: AbortSignal): Promise<IndexJobStatus> {
  const data = await apiJson<{ job: unknown }>(`${RAG_BASE}/system/index-jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
    signal,
  });
  return validateIndexJobStatus(data.job);
}

export function extractDocumentText(
  file: File,
  options: { signal?: AbortSignal; onUploadProgress?: (progress: number) => void } = {},
): Promise<ExtractedDocument> {
  const form = new FormData();
  form.append('file', file, file.name);

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${RAG_BASE}/documents/extract`);
    xhr.timeout = 120_000;
    const credentialHeaders = systemRequestHeaders();
    for (const name of ['X-Admin-Token', 'X-TrinaxAI-Device-Token']) {
      const value = credentialHeaders.get(name);
      if (value) xhr.setRequestHeader(name, value);
    }
    xhr.responseType = 'json';
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onUploadProgress?.(Math.round((event.loaded / event.total) * 70));
      }
    };
    xhr.onload = () => {
      const result = xhr.response || {};
      if (xhr.status < 200 || xhr.status >= 300) {
        reject(apiErrorFromPayload(xhr.status, result, 'document_unreadable'));
        return;
      }
      options.onUploadProgress?.(100);
      resolve(result as ExtractedDocument);
    };
    xhr.onerror = () => reject(new ApiError('', 0));
    xhr.ontimeout = () => reject(new ApiError('Document extraction timed out after 2 minutes.', 408));
    xhr.onabort = () => reject(new DOMException('Document extraction cancelled', 'AbortError'));
    options.signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    options.onUploadProgress?.(1);
    xhr.send(form);
  });
}
