import { APP_CONFIG } from './config';
import { getUserSystemInstruction } from './userProfile';

const RAG_BASE = APP_CONFIG.ragBase;
const OLLAMA_BASE = APP_CONFIG.ollamaBase;

/** Custom error with status code for better diagnostics */
class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export type ChatEngine = 'ollama' | 'rag';

/** Fuente citada por el RAG (archivo, proyecto, fragmento). */
export interface Source {
  file: string;
  project: string;
  collection_id?: string;
  collection?: string;
  page?: string | number | null;
  snippet: string;
  score: number | null;
}

/** Metadatos que el backend emite durante el stream (modelo, proyecto, fuentes). */
export interface StreamMeta {
  model?: string;
  project?: string | null;
  sources?: Source[];
}

export interface StreamOptions {
  collections?: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  // Imagen adjunta (data URL base64) — para análisis con modelo de visión.
  image?: string;
  inputMode?: 'text' | 'voice';
  // Solo en respuestas del asistente (RAG): de dónde salió la info.
  sources?: Source[];
  model?: string;
  project?: string | null;
}

/** Modelo de visión para analizar imágenes (se usa al adjuntar una imagen). */
export const VISION_MODEL = import.meta.env.VITE_TRINAXAI_VISION_MODEL || 'qwen2.5vl:3b';
const VISION_QUALITY_MODEL = import.meta.env.VITE_TRINAXAI_VISION_QUALITY_MODEL || 'qwen2.5vl:7b';
const OLLAMA_KEEP_ALIVE_KEY = 'tc-keep-alive';
const TEXT_NUM_CTX = 3072;
const VISION_FAST_NUM_CTX = 1024;
const VISION_FAST_NUM_PREDICT = 120;
const VISION_QUALITY_NUM_CTX = 1536;
const VISION_QUALITY_NUM_PREDICT = 200;
const VISION_IMAGE_MAX_SIDE = 768;
const VISION_IMAGE_QUALITY = 0.74;
const VISION_QUALITY_HINTS = [
  'detallado', 'detalle', 'profundo', 'análisis', 'analisis',
  'ocr', 'texto', 'lee', 'transcribe', 'código', 'codigo', 'ui', 'interfaz',
  'diseño', 'diseno', 'error', 'pantalla', 'captura',
];
let ollamaModelCache: string[] | null = null;
let ollamaModelCacheAt = 0;
const MODEL_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const INDEXABLE_EXTENSIONS = new Set([
  '.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
  '.html', '.css', '.scss', '.sass',
  '.c', '.h', '.cpp', '.cs', '.java', '.go', '.rb', '.php', '.rs',
  '.sh', '.ps1', '.dockerfile', '.sql', '.graphql', '.cjs', '.mjs',
  '.json', '.yml', '.yaml', '.toml', '.xml', '.ini', '.csv',
  '.md', '.mdx', '.txt', '.rst', '.pdf', '.docx',
]);
const INDEXABLE_FILENAMES = new Set(['dockerfile']);

/** AUTO-ROUTER (modo Ollama): elige modelo según la consulta. Espeja al backend. */
const CODE_HINTS = ['código', 'codigo', 'function', 'función', 'funcion', 'def ', 'class ',
  'import', 'const ', 'let ', 'var ', 'react', 'python', 'javascript', 'typescript', 'html',
  'css', 'api', 'endpoint', 'sql', 'query', 'regex', 'bug', 'error', 'traceback', 'exception',
  'compil', 'deploy', 'docker', 'git', 'npm', 'vite', 'tailwind', 'componente', 'librería',
  'libreria', 'dependencia', 'framework', 'archivo', 'script', '.py', '.js', '.ts', '.tsx',
  '.jsx', '.html', '.css', '.json', 'package.json'];
const DEEP_HINTS = ['refactor', 'optimiz', 'arquitect', 'depura', 'debug', 'por qué',
  'porque falla', 'explica a fondo', 'paso a paso', 'detalle', 'rendimiento', 'performance',
  'seguridad', 'security', 'diseña', 'implementa', 'completo', 'varios archivos', 'analiza',
  'revisa', 'compara'];
const VISION_EXPLICIT_QUALITY_HINTS = [
  'máxima calidad', 'maxima calidad', 'alta calidad', 'modelo grande',
  'lo más detallado', 'lo mas detallado', 'muy detallado', 'analiza a fondo',
];

function modelSetting(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key)?.trim() || fallback;
  } catch {
    return fallback;
  }
}

function ollamaKeepAliveSetting(): string | number {
  try {
    const raw = localStorage.getItem(OLLAMA_KEEP_ALIVE_KEY)?.trim();
    if (!raw) return 0;
    const minutes = Number(raw.replace(/[^0-9.]/g, ''));
    if (!Number.isFinite(minutes) || minutes <= 0) return 0;
    if (/^\d+(?:\.\d+)?[smh]$/.test(raw)) return raw;
    return `${minutes}m`;
  } catch {
    return 0;
  }
}

function shouldUnloadAfterRequest(keepAlive: string | number): boolean {
  if (typeof keepAlive === 'number') return keepAlive <= 0;
  return /^0(?:s|m|h)?$/i.test(keepAlive.trim());
}

export function routeOllamaModel(text: string): string {
  const t = (text || '').toLowerCase();
  const isCode = text.includes('`') || CODE_HINTS.some((h) => t.includes(h));
  const isDeep = text.length > 600 || DEEP_HINTS.some((h) => t.includes(h));
  if (isDeep) return modelSetting('tc-models-deep', 'qwen2.5-coder:3b');
  if (isCode) return modelSetting('tc-models-code', 'qwen2.5-coder:3b');
  if (t.trim().length < 25) return modelSetting('tc-models-fast', 'llama3.2:3b');
  return modelSetting('tc-models-chat', 'llama3.2:3b');
}

async function availableOllamaModels(): Promise<string[]> {
  if (ollamaModelCache && (Date.now() - ollamaModelCacheAt) < MODEL_CACHE_TTL_MS) {
    return ollamaModelCache;
  }
  try {
    const res = await fetch(`${OLLAMA_BASE}/api/tags`, { signal: AbortSignal.timeout(2500) });
    const data = await res.json();
    ollamaModelCache = Array.isArray(data.models)
      ? data.models.map((m: { name?: string }) => m.name).filter(Boolean)
      : [];
  } catch {
    ollamaModelCache = [];
  }
  ollamaModelCacheAt = Date.now();
  return ollamaModelCache ?? [];
}

function hasModel(models: string[], model: string): boolean {
  const base = model.includes(':') ? model : `${model}:latest`;
  return models.includes(model) || models.includes(base);
}

async function ensureOllamaModel(model: string): Promise<void> {
  const models = await availableOllamaModels();
  if (hasModel(models, model)) return;
  const response = await fetch(`${OLLAMA_BASE}/api/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: model, stream: false }),
  });
  if (!response.ok) {
    throw new ApiError(`Ollama model "${model}" is not installed and could not be downloaded.`, response.status);
  }
  ollamaModelCache = null;
}

async function routeVisionModel(text: string): Promise<string> {
  const t = (text || '').toLowerCase();
  const models = await availableOllamaModels();
  const fastVision = modelSetting('tc-models-vision', VISION_MODEL);
  const qualityVision = modelSetting('tc-models-vision-quality', VISION_QUALITY_MODEL);
  if (VISION_EXPLICIT_QUALITY_HINTS.some((h) => t.includes(h)) && hasModel(models, qualityVision)) {
    return qualityVision;
  }
  if (hasModel(models, fastVision)) return fastVision;
  if (hasModel(models, 'moondream')) return 'moondream';
  return fastVision;
}

function isVisionQualityTurn(text: string): boolean {
  const t = (text || '').toLowerCase();
  return VISION_QUALITY_HINTS.some((h) => t.includes(h));
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error ?? new Error('No se pudo leer la imagen.'));
    reader.readAsDataURL(file);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('No se pudo procesar la imagen.'));
    img.src = src;
  });
}

/** Reduce imágenes antes de mandarlas al modelo de visión para evitar 400/OOM. */
export async function prepareImageForVision(file: File): Promise<string> {
  if (!file.type.startsWith('image/')) {
    throw new Error('Selecciona un archivo de imagen válido.');
  }

  const raw = await readFileAsDataUrl(file);
  const img = await loadImage(raw);
  const scale = Math.min(1, VISION_IMAGE_MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
  const width = Math.max(1, Math.round(img.naturalWidth * scale));
  const height = Math.max(1, Math.round(img.naturalHeight * scale));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return raw;

  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);
  return canvas.toDataURL('image/jpeg', VISION_IMAGE_QUALITY);
}

function base64FromDataUrl(dataUrl: string): string {
  const marker = ';base64,';
  const idx = dataUrl.indexOf(marker);
  return idx >= 0 ? dataUrl.slice(idx + marker.length) : dataUrl;
}

function unloadOllamaModel(model?: string): void {
  if (!model) return;
  void fetch(`${OLLAMA_BASE}/api/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ model, keep_alive: 0 }),
    keepalive: true,
  }).catch(() => undefined);
}

/** Estado de los servicios para los indicadores de la PWA. */
export async function checkStatus(): Promise<{ ollama: boolean; rag: boolean; indexed: boolean; ramPercent: number | null }> {
  const out = { ollama: false, rag: false, indexed: false, ramPercent: null as number | null };
  try {
    const r = await fetch(`${OLLAMA_BASE}/api/tags`, { signal: AbortSignal.timeout(3000) });
    out.ollama = r.ok;
  } catch { /* down */ }
  try {
    const r = await fetch(`${RAG_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      out.rag = true;
      const d = await r.json();
      out.indexed = !!d.indexed;
      if (!out.ollama && typeof d?.ollama === 'boolean') out.ollama = d.ollama;
    }
  } catch { /* down */ }
  if (out.rag) {
    try {
      const r = await fetch(`${RAG_BASE}/resources`, { signal: AbortSignal.timeout(2500) });
      if (r.ok) {
        const d = await r.json();
        out.ramPercent = typeof d?.ram?.percent === 'number' ? d.ram.percent : null;
      }
    } catch { /* optional */ }
  }
  return out;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  engine: ChatEngine;
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

/** Generate a short title from the first user message */
export function generateTitle(message: string): string {
  const cleaned = message.replace(/\n/g, ' ').trim();
  return cleaned.length > 50 ? cleaned.slice(0, 47) + '…' : cleaned;
}

/** Unique ID generator */
export function uid(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 9);
}

export function folderLabelFromFiles(files: FileList | File[]): string {
  const first = Array.from(files)[0] as File & { webkitRelativePath?: string };
  const rel = first?.webkitRelativePath || first?.name || 'import';
  return rel.split('/')[0] || 'import';
}

export function isIndexableFile(file: File): boolean {
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

async function apiJson<T>(url: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError('La API RAG local no está disponible. Enciende TrinaxAI desde Configuración. / Local RAG API is not available.', 0);
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(`${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 500)}` : ''}`, response.status);
  }
  try {
    return await response.json() as T;
  } catch {
    throw new ApiError('Invalid JSON response from local API.', response.status);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function validateIndexJobStatus(value: unknown): IndexJobStatus {
  if (!isRecord(value) || typeof value.id !== 'string' || typeof value.status !== 'string') {
    throw new ApiError('Invalid index job response from local API.', 0);
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
  };
}

export async function getCollections(signal?: AbortSignal): Promise<Collection[]> {
  const data = await apiJson<{ collections?: Collection[] }>(`${RAG_BASE}/collections`, { signal });
  return Array.isArray(data.collections) ? data.collections : [];
}

export async function createCollection(name: string): Promise<Collection> {
  const data = await apiJson<{ collection: Collection }>(`${RAG_BASE}/collections`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return data.collection;
}

export async function renameCollection(id: string, name: string): Promise<Collection> {
  const data = await apiJson<{ collection: Collection }>(`${RAG_BASE}/collections/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  return data.collection;
}

export async function deleteCollection(id: string): Promise<void> {
  await apiJson(`${RAG_BASE}/collections/${encodeURIComponent(id)}`, { method: 'DELETE' });
}

// ── Knowledge Browser ──
export interface CollectionSourceRow {
  file: string;
  chunks: number;
  size: number;
  mtime: number;
  preview: string;
}
export interface FileChunk {
  id: string;
  text: string;
  metadata: Record<string, unknown>;
  score: number | null;
}
export interface ResearchResult {
  answer: string;
  sub_questions: string[];
  sources: Source[];
  passes: number;
  model: string;
}

export async function getCollectionSources(
  collection: string,
  signal?: AbortSignal,
): Promise<{ collection: string; sources: CollectionSourceRow[] }> {
  const url = `${RAG_BASE}/v1/sources?collection=${encodeURIComponent(collection)}`;
  return apiJson(url, { signal });
}

export async function getFileChunks(
  collection: string,
  file: string,
  opts: { limit?: number; offset?: number; q?: string; signal?: AbortSignal } = {},
): Promise<{ collection: string; file: string; total: number; chunks: FileChunk[]; query?: string }> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  if (opts.q) params.set('q', opts.q);
  const qs = params.toString();
  const encodedFile = file.split('/').map((part) => encodeURIComponent(part)).join('/');
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}/${encodedFile}/chunks${qs ? `?${qs}` : ''}`;
  return apiJson(url, { signal: opts.signal });
}

// ── File Watcher ──
export interface WatchStatus {
  running: boolean;
  watching: string[];
  events_seen: number;
  started_at: number | null;
}

export async function startWatch(opts: { paths?: string[]; collection?: string } = {}): Promise<{ status: string; watching: string[]; pid: number | null }> {
  return apiJson(`${RAG_BASE}/v1/watch/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paths: opts.paths, collection: opts.collection }),
  });
}
export async function stopWatch(): Promise<{ status: string }> {
  return apiJson(`${RAG_BASE}/v1/watch/stop`, { method: 'POST' });
}
export async function getWatchStatus(signal?: AbortSignal): Promise<WatchStatus> {
  return apiJson(`${RAG_BASE}/v1/watch/status`, { signal });
}

// ── Memory ──
export interface MemoryEntry {
  id: string;
  text: string;
  created_at: number;
  tags: string[];
}
export interface MemorySummary {
  summary: string;
  count: number;
  updated_at: number;
}

export async function listMemories(signal?: AbortSignal): Promise<MemoryEntry[]> {
  const data = await apiJson<{ memories?: MemoryEntry[] }>(`${RAG_BASE}/v1/memory`, { signal });
  return Array.isArray(data.memories) ? data.memories : [];
}
export async function addMemory(text: string, tags?: string[]): Promise<MemoryEntry> {
  return apiJson(`${RAG_BASE}/v1/memory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, tags }),
  });
}
export async function deleteMemory(id: string): Promise<{ deleted: boolean }> {
  return apiJson(`${RAG_BASE}/v1/memory/${encodeURIComponent(id)}`, { method: 'DELETE' });
}
export async function refreshMemorySummary(): Promise<{ status: string; summary: string; count: number }> {
  return apiJson(`${RAG_BASE}/v1/memory/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}
export async function getMemorySummary(signal?: AbortSignal): Promise<MemorySummary> {
  try {
    return await apiJson<MemorySummary>(`${RAG_BASE}/v1/memory/summary`, { signal });
  } catch {
    return { summary: '', count: 0, updated_at: 0 };
  }
}

// ── Deep Research ──
export async function runResearch(
  query: string,
  opts: { collections?: string[]; depth?: 1 | 2 | 3; signal?: AbortSignal } = {},
): Promise<ResearchResult> {
  return apiJson(`${RAG_BASE}/v1/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      collections: opts.collections,
      depth: opts.depth ?? 2,
    }),
    signal: opts.signal,
  });
}

// ── Usage Stats ──
export interface UsageStats {
  messages_total: number;
  messages_by_engine: Record<string, number>;
  tokens_estimated: number;
  top_collections: Array<{ id: string; count: number }>;
  top_models: Array<{ model: string; count: number }>;
  index_runs: number;
  first_seen: number;
  last_seen: number;
}
export async function getUsageStats(signal?: AbortSignal): Promise<UsageStats> {
  return apiJson(`${RAG_BASE}/v1/stats`, { signal });
}

function estimateUsageTokens(messages: ChatMessage[], answer: string): number {
  const chars = messages.reduce((sum, msg) => sum + (msg.content?.length ?? 0), 0) + answer.length;
  return Math.max(1, Math.round(chars / 4));
}

function recordUsage(engine: ChatEngine | 'ollama-vision', model: string, messages: ChatMessage[], answer: string, collections?: string[]): void {
  if (!answer.trim()) return;
  void fetch(`${RAG_BASE}/v1/usage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      engine,
      model,
      collections: collections || [],
      est_tokens: estimateUsageTokens(messages, answer),
    }),
    keepalive: true,
  }).catch(() => undefined);
}

export async function resetSharedAppState(): Promise<void> {
  await apiJson(`${RAG_BASE}/app-state`, {
    method: 'DELETE',
    headers: { 'X-TrinaxAI-Confirm': 'reset-app-state' },
  });
}

export function startFolderIndex(
  files: FileList | File[],
  options: { signal?: AbortSignal; onUploadProgress?: (progress: number) => void; collectionId?: string } = {},
): Promise<FolderImportResult> {
  const selected = Array.from(files);
  if (selected.length === 0) throw new Error('No files selected.');
  const indexable = indexableFilesFrom(selected);
  if (indexable.length === 0) throw new Error('No indexable files selected.');
  const label = folderLabelFromFiles(selected);
  const form = new FormData();
  form.append('label', label);
  form.append('collection_id', options.collectionId || 'default');
  indexable.forEach((file) => {
    const rel = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
    form.append('files', file, rel);
  });

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${RAG_BASE}/system/index-upload`);
    xhr.responseType = 'json';
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        options.onUploadProgress?.(Math.round((event.loaded / event.total) * 30));
      }
    };
    xhr.onload = () => {
      const result = xhr.response || {};
      if (xhr.status < 200 || xhr.status >= 300) {
        const detail = typeof result === 'object' ? JSON.stringify(result).slice(0, 500) : String(xhr.responseText || '').slice(0, 500);
        reject(new ApiError(`Folder import failed: ${xhr.status} ${xhr.statusText}${detail ? `\n${detail}` : ''}`, xhr.status));
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
    xhr.onerror = () => reject(new ApiError('Folder import failed: network error', 0));
    xhr.onabort = () => reject(new DOMException('Upload cancelled', 'AbortError'));
    options.signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    xhr.send(form);
  });
}

export async function getIndexJob(jobId: string, signal?: AbortSignal): Promise<IndexJobStatus> {
  const response = await fetch(`${RAG_BASE}/system/index-jobs/${encodeURIComponent(jobId)}`, { signal });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(`Index job status failed: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 500)}` : ''}`, response.status);
  }
  const data = await response.json().catch(() => null);
  return validateIndexJobStatus(data);
}

export async function cancelIndexJob(jobId: string, signal?: AbortSignal): Promise<IndexJobStatus | null> {
  const response = await fetch(`${RAG_BASE}/system/index-jobs/${encodeURIComponent(jobId)}/cancel`, {
    method: 'POST',
    signal,
  });
  if (!response.ok) return null;
  const data = await response.json().catch(() => null);
  if (!isRecord(data) || !data.job) return null;
  return validateIndexJobStatus(data.job);
}

export async function extractDocumentText(file: File, signal?: AbortSignal): Promise<ExtractedDocument> {
  const form = new FormData();
  form.append('file', file, file.name);
  return apiJson<ExtractedDocument>(`${RAG_BASE}/documents/extract`, {
    method: 'POST',
    body: form,
    signal,
  });
}

/** System prompt for Ollama — gives TrinaxAI identity and purpose */
function ollamaSystemPrompt(lang: 'en' | 'es'): ChatMessage {
  if (lang === 'en') {
    return {
      role: 'system',
      content:
      'You are TrinaxAI, a local-first, open-source AI assistant. ' +
      'Your product identity is always TrinaxAI. ' +
      'You were created by TrinaxCode — a Full Stack Web Developer from Tuxtla Gutiérrez, Chiapas (originally from Nicaragua), ' +
      'focused on React, TypeScript, Python, Django, PostgreSQL, and Firebase. ' +
      'TrinaxCode builds products with real traffic, real leads, and real revenue. ' +
      'GitHub: https://github.com/TrinaxCode. LinkedIn: https://linkedin.com/in/trinaxcode. ' +
      'If the user asks who created you, what is TrinaxCode, or anything about your origin, explain that TrinaxCode is your creator, ' +
      'a Full Stack Developer who made you as an open-source local-first AI project, and share the links above. ' +
      'Always answer in the language of the current user message. Be clear, useful, honest, and professional with a natural tone. ' +
      'Do not invent details about the user hardware, location, identity, or files. ' +
      'If you do not know something or lack enough context, say so and suggest how to verify it.\n\n' +
      'USER:\n' +
      `- ${getUserSystemInstruction('en')}\n\n` +
      'IDENTITY:\n' +
      '- You run locally with Ollama and open-source models.\n' +
      '- You can use RAG when the user enables that mode to answer with indexed files.\n' +
      '- The PWA works on desktop, tablets, and phones, and aims to preserve local privacy.\n' +
      '- You do not depend on cloud services to answer in local mode.\n\n' +
      'STYLE:\n' +
      '- Greet only once at the start of a new conversation. In follow-up turns, do not start with "hola", "hello", "claro", "me alegra", or welcome phrases; answer directly.\n' +
      '- For simple questions, answer briefly.\n' +
      '- For code or debugging, give concrete steps and verifiable examples.\n' +
      '- For images, describe visible observations and avoid assuming non-visible facts.\n' +
      '- Do not say you run on specific hardware unless the user has said that in this conversation.',
    };
  }
  return {
    role: 'system',
    content:
    'Eres TrinaxAI, un asistente de IA local-first y open-source. ' +
    'Tu identidad de producto siempre es TrinaxAI. ' +
    'Fuiste creado por TrinaxCode — un Full Stack Web Developer de Tuxtla Gutiérrez, Chiapas (originario de Nicaragua), ' +
    'enfocado en React, TypeScript, Python, Django, PostgreSQL y Firebase. ' +
    'TrinaxCode construye productos con tráfico real, leads reales e ingresos reales. ' +
    'GitHub: https://github.com/TrinaxCode. LinkedIn: https://linkedin.com/in/trinaxcode. ' +
    'Si el usuario pregunta quién te creó, qué es TrinaxCode, o cualquier cosa sobre tu origen, explica que TrinaxCode es tu creador, ' +
    'un Full Stack Developer que te hizo como un proyecto open-source local-first, y comparte los links anteriores. ' +
    'Responde en el idioma del usuario. Sé claro, útil, honesto y profesional, con tono cercano. ' +
    'No inventes detalles sobre el hardware del usuario, su ubicación, su identidad o sus archivos. ' +
    'Si no sabes algo o no tienes contexto suficiente, dilo y sugiere cómo verificarlo.\n\n' +
    'USUARIO:\n' +
    `• ${getUserSystemInstruction('es')}\n\n` +
    'IDENTIDAD:\n' +
    '• Corres localmente con Ollama y modelos open-source.\n' +
    '• Puedes usar RAG cuando el usuario active ese modo para responder con archivos indexados.\n' +
    '• La PWA funciona en escritorio, tablets y teléfonos, y busca mantener privacidad local.\n' +
    '• No dependes de servicios cloud para responder en modo local.\n\n' +
    'ESTILO:\n' +
    '• Saluda solo una vez al inicio de una conversación nueva. En turnos posteriores no empieces con "hola", "claro", "me alegra" ni fórmulas de bienvenida; responde directo.\n' +
    '• Para preguntas simples, responde breve.\n' +
    '• Para código o depuración, da pasos concretos y ejemplos verificables.\n' +
    '• Para imágenes, describe observaciones visibles y evita asumir datos no visibles.\n' +
    '• No digas que corres en hardware específico salvo que el usuario lo haya dicho en esta conversación.',
  };
}

function voiceSystemPrompt(lang: 'en' | 'es'): ChatMessage {
  return {
    role: 'system',
    content: lang === 'en'
      ? 'The latest message arrived by voice. Reply like spoken conversation: natural, clear, no long lists, ideally in 2 to 4 sentences. If you need to give steps, keep them few and direct.'
      : 'El ultimo mensaje llego por voz. Responde como conversacion hablada: natural, claro, sin listas largas, idealmente en 2 a 4 frases. Si necesitas dar pasos, que sean pocos y directos.',
  };
}

function isVoiceTurn(messages: ChatMessage[]): boolean {
  return messages[messages.length - 1]?.inputMode === 'voice';
}

function detectTurnLanguage(text: string): 'en' | 'es' {
  const sample = text.toLowerCase();
  const enHits = [
    'the ', 'what ', 'why ', 'how ', 'can ', 'could ', 'would ', 'should ',
    'please', 'thanks', 'thank ', 'hello', 'hi ', 'hey ', 'install', 'error',
    'file', 'folder', 'tell ', 'explain', 'write ', 'make ', 'create ', 'help ',
    'fix ', 'does ', 'is ', 'are ', 'you ', 'my ', 'your ', 'this ', 'that ',
  ].filter((word) => sample.includes(word)).length;
  const esHits = [
    ' el ', ' la ', ' los ', ' las ', ' que ', ' como ', 'por ', 'para ',
    'hola', 'gracias', 'instalar', 'error', 'archivo', 'carpeta', 'dime ',
    'explica', 'escribe ', 'haz ', 'crea ', 'ayuda ', 'arregla ', 'eres ',
    'soy ', 'mi ', 'tu ', 'este ', 'esta ',
  ].filter((word) => sample.includes(word)).length;
  if (enHits > esHits) return 'en';
  if (esHits > enHits) return 'es';
  return /[¿¡ñáéíóú]/i.test(text) ? 'es' : 'en';
}

function languageSystemPrompt(messages: ChatMessage[]): ChatMessage {
  const last = messages[messages.length - 1]?.content ?? '';
  const detected = detectTurnLanguage(last);
  return {
    role: 'system',
    content: detected === 'en'
      ? 'The current user message is in English. Answer in English. This overrides the interface language, profile language, previous conversation language, and any indexed document language unless the user explicitly asks for another language.'
      : 'El mensaje actual del usuario esta en espanol. Responde en espanol. Esto tiene prioridad sobre el idioma de la interfaz, el perfil, la conversacion previa y los documentos indexados, salvo que el usuario pida explicitamente otro idioma.',
  };
}

function turnLanguage(messages: ChatMessage[]): 'en' | 'es' {
  const last = messages[messages.length - 1]?.content ?? '';
  return detectTurnLanguage(last);
}

function conversationStylePrompt(messages: ChatMessage[]): ChatMessage {
  const hasAssistantReply = messages.some((m) => m.role === 'assistant');
  return {
    role: 'system',
    content: hasAssistantReply
      ? 'This conversation already has assistant replies. Do not greet again. Do not start with "Hola", "Hello", "Claro", "Me alegra", or welcome phrases. Answer the current request directly.'
      : 'This is the first assistant reply in the conversation. A brief greeting is allowed if natural, then answer the user request.',
  };
}

function textMessagesForOllama(messages: ChatMessage[]) {
  const lang = turnLanguage(messages);
  const system = isVoiceTurn(messages)
    ? [ollamaSystemPrompt(lang), languageSystemPrompt(messages), conversationStylePrompt(messages), voiceSystemPrompt(lang)]
    : [ollamaSystemPrompt(lang), languageSystemPrompt(messages), conversationStylePrompt(messages)];
  return [
    ...system,
    ...messages.map((m) => ({ role: m.role, content: m.content })),
  ];
}

async function readStreamLines(
  response: Response,
  signal: AbortSignal | undefined,
  onLine: (line: string) => void,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');
  const decoder = new TextDecoder();
  let pending = '';

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) {
        if (pending.trim()) onLine(pending);
        break;
      }
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split('\n');
      pending = lines.pop() ?? '';
      for (const line of lines) onLine(line);
    }
  } finally {
    if (signal?.aborted) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

function appendOllamaJsonLine(line: string, onToken: (token: string) => void): string {
  const trimmed = line.trim();
  if (!trimmed) return '';
  try {
    const parsed = JSON.parse(trimmed);
    const token = typeof parsed?.message?.content === 'string' ? parsed.message.content : '';
    if (token) onToken(token);
    return token;
  } catch {
    return '';
  }
}

export function parseRagSseLine(line: string): {
  token?: string;
  meta?: StreamMeta;
  done?: boolean;
} {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return {};
  const data = trimmed.slice(6);
  if (data === '[DONE]') return { done: true };
  try {
    const parsed = JSON.parse(data);
    if (parsed.trinaxai) {
      return { meta: { model: parsed.trinaxai.model, project: parsed.trinaxai.project } };
    }
    if (parsed.trinaxai_sources) {
      return { meta: { sources: parsed.trinaxai_sources as Source[] } };
    }
    const token = parsed.choices?.[0]?.delta?.content;
    return typeof token === 'string' && token ? { token } : {};
  } catch {
    return {};
  }
}

/** Stream a chat completion from Ollama (OpenAI-compatible endpoint) */
export async function streamOllama(
  messages: ChatMessage[],
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onMeta?: (m: StreamMeta) => void,
  _unused?: StreamOptions,  // kept for backward compat; not read by Ollama path
): Promise<string> {
  const lastMessage = messages[messages.length - 1];
  const last = lastMessage?.content ?? '';
  // Solo el turno actual con imagen debe activar visión. Si no, no cargamos 7B.
  if (lastMessage?.image) {
    return streamOllamaVision(messages, onToken, signal, onMeta);
  }

  const model = routeOllamaModel(last);
  await ensureOllamaModel(model);
  const keepAlive = ollamaKeepAliveSetting();
  onMeta?.({ model });
  const response = await fetch(`${OLLAMA_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages: textMessagesForOllama(messages),
      stream: true,
      keep_alive: keepAlive,
      options: {
        num_ctx: TEXT_NUM_CTX,
        num_thread: 8,
      },
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(
      `Ollama: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 240)}` : ''}`,
      response.status,
    );
  }

  let fullContent = '';

  try {
    await readStreamLines(response, signal, (line) => {
      fullContent += appendOllamaJsonLine(line, onToken);
    });
  } finally {
    if (shouldUnloadAfterRequest(keepAlive)) unloadOllamaModel(model);
  }
  if (!signal?.aborted) recordUsage('ollama', model, messages, fullContent);
  return fullContent;
}

/** Vision models are more reliable through Ollama's native /api/chat schema. */
async function streamOllamaVision(
  messages: ChatMessage[],
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onMeta?: (m: StreamMeta) => void,
): Promise<string> {
  const lastIndex = messages.length - 1;
  const lastContent = messages[lastIndex]?.content ?? '';
  const lang = turnLanguage(messages);
  const qualityTurn = isVisionQualityTurn(lastContent);
  const model = await routeVisionModel(lastContent);
  await ensureOllamaModel(model);
  const keepAlive = ollamaKeepAliveSetting();
  onMeta?.({ model });

  const apiMessages = messages.map((m, i) => {
    const msg: { role: ChatMessage['role']; content: string; images?: string[] } = {
      role: m.role,
      content: m.content || (m.image ? 'Analiza esta imagen de forma útil, breve y concreta.' : ''),
    };
    if (i === lastIndex && m.image) {
      msg.images = [base64FromDataUrl(m.image)];
    }
    return msg;
  });

  const response = await fetch(`${OLLAMA_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages: [
        ollamaSystemPrompt(lang),
        languageSystemPrompt(messages),
        conversationStylePrompt(messages),
        ...(isVoiceTurn(messages) ? [voiceSystemPrompt(lang)] : []),
        ...apiMessages,
      ],
      stream: true,
      keep_alive: keepAlive,
      options: {
        num_ctx: qualityTurn ? VISION_QUALITY_NUM_CTX : VISION_FAST_NUM_CTX,
        num_predict: qualityTurn ? VISION_QUALITY_NUM_PREDICT : VISION_FAST_NUM_PREDICT,
        num_thread: 8,
      },
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    const hint = /unexpected EOF|llama runner|model/i.test(detail)
      ? '\nEl modelo de visión local falló al cargar/procesar la imagen. Prueba con una captura más pequeña o una pregunta más concreta; el modelo se descargará de RAM automáticamente.'
      : '';
    throw new ApiError(
      `Ollama visión: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 240)}` : ''}${hint}`,
      response.status,
    );
  }

  let fullContent = '';

  try {
    await readStreamLines(response, signal, (line) => {
      fullContent += appendOllamaJsonLine(line, onToken);
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (/unexpected EOF|terminated|network|Failed to fetch/i.test(msg)) {
      throw new Error(
        'El modelo de visión local no completó la solicitud. ' +
        'La imagen ya fue reducida y el modelo se descargará de RAM; intenta con una imagen más simple o una pregunta más específica.',
      );
    }
    throw err;
  } finally {
    if (shouldUnloadAfterRequest(keepAlive)) unloadOllamaModel(model);
  }
  if (!signal?.aborted) recordUsage('ollama-vision', model, messages, fullContent);
  return fullContent;
}

/** Stream a chat completion from the RAG API (SSE via StreamingResponse) */
export async function streamRag(
  messages: ChatMessage[],
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onMeta?: (m: StreamMeta) => void,
  options: StreamOptions = {},
): Promise<string> {
  const voiceTurn = isVoiceTurn(messages);
  const lang = turnLanguage(messages);
  const clean = messages.map((m, i) => ({
    role: m.role,
    content: voiceTurn && i === messages.length - 1
      ? (lang === 'en'
        ? `${m.content}\n\nVoice mode: answer naturally, briefly, and easy to listen to.`
        : `${m.content}\n\nModo voz: responde natural, breve y facil de escuchar.`)
      : m.content,
  }));
  const response = await fetch(`${RAG_BASE}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      messages: [
        { role: 'system', content: getUserSystemInstruction(lang) },
        { role: 'system', content: languageSystemPrompt(messages).content },
        { role: 'system', content: conversationStylePrompt(messages).content },
        ...clean,
      ],
      stream: true,
      collections: options.collections,
    }),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(
      `RAG: ${response.status} ${response.statusText}`,
      response.status,
    );
  }

  let fullContent = '';
  await readStreamLines(response, signal, (line) => {
    const event = parseRagSseLine(line);
    if (event.meta) onMeta?.(event.meta);
    if (event.token) {
      fullContent += event.token;
      onToken(event.token);
    }
  });
  return fullContent;
}
