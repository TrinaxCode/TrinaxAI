import { APP_CONFIG } from './config';
import { getUserSystemInstruction } from './userProfile';
import { systemFetch, systemRequestHeaders } from './authHeaders';

export { generateTitle, uid } from './chatUtils';
export { systemRequestHeaders } from './authHeaders';

export const RAG_BASE = APP_CONFIG.ragBase;
const OLLAMA_BASE = APP_CONFIG.ollamaBase;

/** Custom error with status code for better diagnostics */
export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

function friendlyApiFailure(status: number, detail = ''): string {
  const en = typeof document !== 'undefined' && document.documentElement.lang.toLowerCase().startsWith('en');
  if (status === 401 || status === 403) {
    return en
      ? 'This device does not have permission to use this feature. Grant access from your main device under Settings → Paired device.'
      : 'Este dispositivo no tiene permiso para usar esta función. Brinda acceso desde tu dispositivo principal en Configuración → Dispositivo vinculado.';
  }
  if (status === 429) return en ? 'Too many requests. Wait a moment and try again.' : 'Hay demasiadas solicitudes. Espera un momento e inténtalo de nuevo.';
  if (status >= 500) {
    try {
      const parsed = JSON.parse(detail);
      if (typeof parsed?.detail === 'string' && parsed.detail.trim()) return parsed.detail.trim().slice(0, 500);
    } catch { /* plain-text response */ }
    if (detail.trim()) return detail.trim().slice(0, 500);
    return en ? 'TrinaxAI could not complete the action. Check that Ollama and RAG are running, then try again.' : 'TrinaxAI no pudo completar la acción. Verifica que Ollama y RAG estén encendidos e inténtalo de nuevo.';
  }
  return detail || (en ? `The action could not be completed (code ${status}).` : `No se pudo completar la acción (código ${status}).`);
}

export type ChatEngine = 'ollama' | 'rag';

/** Fuente citada por el RAG (archivo, proyecto, fragmento). */
export interface Source {
  file: string;
  url?: string | null;
  title?: string | null;
  kind?: 'local' | 'web' | string;
  authority?: 'primary' | 'secondary' | string | null;
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
  mode?: 'auto' | 'knowledge' | 'model';
  rag_used?: boolean;
  result_count?: number;
  collections?: string[];
}

export interface StreamOptions {
  collections?: string[];
  /** Avoid analytics/usage writes for an in-memory temporary chat. */
  temporary?: boolean;
}

export interface ChatDocumentAttachment {
  id?: string;
  name: string;
  size: number;
  mimeType?: string;
  storageKey?: string;
  kind?: 'image' | 'document';
  truncated?: boolean;
  localOnly?: boolean;
}

/** Persisted routing intent used by edit/regenerate for a stable turn mode. */
export interface ChatTurnMetadata {
  mode: 'chat' | 'vision' | 'web' | 'deep_research' | 'agent' | 'rag';
  source: 'manual' | 'rule';
  reason: string;
  webSearch: boolean;
  depth: 1 | 2 | 3;
  announce: boolean;
  collections?: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  // Texto corto que se muestra al usuario cuando `content` incluye contexto interno.
  displayContent?: string;
  // Imagen adjunta (data URL base64) — para análisis con modelo de visión.
  image?: string;
  documentAttachments?: ChatDocumentAttachment[];
  inputMode?: 'text' | 'voice';
  // Solo en respuestas del asistente (RAG): de dónde salió la info.
  sources?: Source[];
  model?: string;
  project?: string | null;
  /** Routing intent associated with this user turn/assistant response. */
  turn?: ChatTurnMetadata;
  /** Internal UI marker so regeneration replaces, rather than repeats, it. */
  routerNotice?: boolean;
}

/** Specialized model for OCR, screenshots and image analysis. */
export const VISION_MODEL = import.meta.env.VITE_TRINAXAI_VISION_MODEL || 'qwen3-vl:4b-instruct';
const OLLAMA_KEEP_ALIVE_KEY = 'tc-keep-alive';
export const OLLAMA_KEEP_ALIVE_DEFAULT = import.meta.env.VITE_TRINAXAI_KEEP_ALIVE || '10m';
export const MODEL_KEYS = [
  'tc-models-chat',
  'tc-models-deep',
  'tc-models-vision',
  'tc-models-embed',
  'tc-models-code',
  'tc-models-fast',
] as const;
export type ModelSettingKey = typeof MODEL_KEYS[number];
export type ModelPreset = 'low' | 'balanced' | 'max' | 'ultra';
export const MODEL_PRESETS: Record<ModelPreset, Record<ModelSettingKey, string>> = {
  low: {
    'tc-models-chat': 'qwen3.5:4b',
    'tc-models-deep': 'qwen3.5:4b',
    'tc-models-vision': 'qwen3-vl:2b-instruct',
    'tc-models-embed': 'bge-m3',
    'tc-models-code': 'qwen2.5-coder:1.5b',
    'tc-models-fast': 'qwen3.5:0.8b',
  },
  balanced: {
    'tc-models-chat': 'granite4:3b',
    'tc-models-deep': 'qwen3.5:4b',
    'tc-models-vision': 'qwen3-vl:4b-instruct',
    'tc-models-embed': 'bge-m3',
    'tc-models-code': 'qwen2.5-coder:3b',
    'tc-models-fast': 'granite4:3b',
  },
  max: {
    'tc-models-chat': 'qwen3.5:27b',
    'tc-models-deep': 'qwen3.5:27b',
    'tc-models-vision': 'qwen3-vl:8b-instruct',
    'tc-models-embed': 'bge-m3',
    'tc-models-code': 'qwen2.5-coder:7b',
    'tc-models-fast': 'qwen3.5:4b',
  },
  ultra: {
    'tc-models-chat': 'qwen3.5:35b-a3b',
    'tc-models-deep': 'qwen3.5:35b-a3b',
    'tc-models-vision': 'qwen3-vl:30b-a3b-instruct',
    'tc-models-embed': 'bge-m3',
    'tc-models-code': 'qwen2.5-coder:14b',
    'tc-models-fast': 'qwen3.5:4b',
  },
};
export const DEFAULT_MODEL_SETTINGS = MODEL_PRESETS.balanced;
const TEXT_NUM_CTX = 8192;
const ANALYTICAL_NUM_CTX = 12288;
const TEXT_NUM_PREDICT = 2048;
const ANALYTICAL_NUM_PREDICT = 4096;
const VISION_NUM_CTX = 8192;
const VISION_NUM_PREDICT = 2560;
const VISION_IMAGE_MAX_SIDE = 768;
const VISION_IMAGE_QUALITY = 0.74;
// Room for long exam prompts; matches the raised text window (num_ctx=8192).
// Kept as a safety cap only so a runaway history can't blow the model window,
// well above any single question.
const DIRECT_CHAT_CONTEXT_CHARS = 24_000;
let ollamaModelCache: string[] | null = null;
let ollamaModelCapabilities = new Map<string, Set<string>>();
let ollamaModelCacheAt = 0;
let lastResolvedTextModel: { model: string; at: number; role: 'code' | 'text' } | null = null;
const ollamaPullsInFlight = new Map<string, Promise<void>>();
const MODEL_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
const INDEXABLE_EXTENSIONS = new Set([
  '.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte',
  '.html', '.css', '.scss', '.sass',
  '.c', '.h', '.cpp', '.cs', '.java', '.go', '.rb', '.php', '.rs',
  '.swift', '.kt', '.kts', '.scala', '.dart', '.lua', '.pl', '.pm',
  '.erl', '.ex', '.exs', '.clj', '.fs', '.fsx', '.vb', '.asm', '.s',
  '.r', '.jl', '.m',
  '.sh', '.bash', '.zsh', '.fish', '.ps1', '.bat', '.cmd',
  '.dockerfile', '.sql', '.graphql', '.gql', '.cjs', '.mjs',
  '.json', '.jsonl', '.ipynb', '.yml', '.yaml', '.toml', '.xml', '.ini',
  '.cfg', '.conf', '.properties', '.env', '.csv', '.tsv',
  '.md', '.mdx', '.txt', '.rst', '.tex', '.bib', '.log',
  '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
  '.odt', '.ods', '.odp', '.rtf',
]);
const INDEXABLE_FILENAMES = new Set([
  'dockerfile', 'makefile', 'readme', 'license', 'changelog',
  'contributing', 'gemfile', 'procfile',
]);

/** AUTO-ROUTER (modo Ollama): elige modelo según la consulta. Espeja al backend. */
// Programming languages / tools. On their own these do NOT mean "code": a math
// exam can mention "api", "grafo" o "algoritmo". They only route to the code
// model when paired with an explicit code action (see isCodeIntent).
const CODE_LANG_HINTS = ['react', 'python', 'javascript', 'typescript', 'html',
  'css', 'sql', 'regex', 'docker', 'git', 'npm', 'vite', 'tailwind', 'django',
  'node', 'bash', 'shell', 'json', 'archivo', 'file', 'proyecto', 'project',
  'repo', 'repositorio'];
// Explicit "write/build/debug code" actions.
const CODE_ACTION_HINTS = ['código', 'codigo', 'function', 'función', 'funcion',
  'def ', 'class ', 'import ', 'const ', 'let ', 'var ', 'endpoint', 'traceback',
  'exception', 'stacktrace', 'stack trace', 'compil', 'deploy', 'script',
  'depura', 'debug', 'programa ', 'programar', 'componente', 'framework',
  'dependencia', 'librería', 'libreria', 'query'];
// Unambiguous code syntax / filenames — code on their own.
const CODE_STRONG_RE = /```|~~~|=>|<\/[a-z]|<[a-z][a-z0-9]*\s|\bpackage\.json\b|\.(py|js|jsx|ts|tsx|html|css|json)\b/i;
// Build verbs that only mean "code" when paired with a language/tool hint.
const CODE_BUILD_VERBS = ['escribe', 'crea', 'implementa', 'programa', 'genera',
  'write', 'create', 'implement', 'build', 'refactor', 'refactoriza', 'arregla',
  'corrige', 'fix'];
const REASONING_HINTS = [
  'examen', 'álgebra', 'algebra', 'ecuación', 'ecuacion', 'matriz', 'determinante',
  'integral', 'derivada', 'límite', 'limite', 'probabilidad', 'distribución normal',
  'demuestra', 'demostración', 'inducción', 'induccion', 'teorema maestro',
  'recurrencia', 'complejidad temporal', 'complejidad espacial', 'correctitud',
  'grafo ponderado', 'dijkstra', 'euleriano', 'tsp', 'p vs np', 'puntos críticos',
  'puntos criticos', 'integración por partes', 'integracion por partes',
];
const GENERAL_TOPIC_HINTS = [
  'clima', 'weather', 'receta', 'cocina', 'comida', 'viaje', 'vacaciones',
  'película', 'pelicula', 'música', 'musica', 'deporte', 'salud', 'ejercicio',
  'historia', 'geografía', 'geografia', 'capital de', 'quién es', 'quien es',
  'qué es', 'que es', 'cuéntame', 'cuentame', 'consejo', 'traduce', 'traducción',
  'translation', 'recipe', 'travel', 'movie', 'music', 'who is', 'what is',
];
const TOPIC_SHIFT_HINTS = [
  'cambiando de tema', 'cambio de tema', 'otra cosa', 'ahora hablemos',
  'dejando el código', 'dejando el codigo', 'new topic', 'change of topic',
  'switching topics', 'let\'s talk about',
];
export function modelSetting(key: string, fallback: string): string {
  try {
    if (localStorage.getItem('tc-model-defaults-v2') !== '1') {
      const chat = localStorage.getItem('tc-models-chat');
      const deep = localStorage.getItem('tc-models-deep');
      const code = localStorage.getItem('tc-models-code');
      const fast = localStorage.getItem('tc-models-fast');
      if ((!chat || chat === 'qwen3.5:9b') && (!deep || deep === 'qwen3.5:9b')
        && (!code || code === 'qwen2.5-coder:3b') && (!fast || fast === 'granite4:3b')) {
        localStorage.setItem('tc-models-chat', 'granite4:3b');
        localStorage.setItem('tc-models-deep', 'qwen3.5:4b');
      }
      localStorage.setItem('tc-model-defaults-v2', '1');
    }
    const value = localStorage.getItem(key)?.trim() || fallback;
    // Migrate defaults that were removed after the local Qwen3.5 benchmark.
    // This prevents stale shared/local state from routing chat to a deleted
    // model (and then incorrectly falling back to a coder model).
    if (key === 'tc-models-chat' && value === 'qwen3:4b-instruct-2507-q4_K_M') return 'qwen3.5:4b';
    if (key === 'tc-models-fast' && (value === 'qwen3:4b-instruct-2507-q4_K_M' || value === 'qwen3.5:2b')) return 'granite4:3b';
    if (key === 'tc-models-vision' && (value.startsWith('qwen3.5:') || value === 'gemma3:4b')) {
      return VISION_MODEL;
    }
    return value;
  } catch {
    return fallback;
  }
}

export function ollamaKeepAliveSetting(): string | number {
  try {
    const raw = localStorage.getItem(OLLAMA_KEEP_ALIVE_KEY)?.trim();
    if (!raw) return OLLAMA_KEEP_ALIVE_DEFAULT;
    const stripped = raw.replace(/[^0-9.]/g, '');
    if (!stripped) return OLLAMA_KEEP_ALIVE_DEFAULT;
    const minutes = Number(stripped);
    if (!Number.isFinite(minutes) || minutes < 0) return OLLAMA_KEEP_ALIVE_DEFAULT;
    if (minutes === 0) return 0;
    if (/^\d+(?:\.\d+)?[smh]$/.test(raw)) return raw;
    return `${minutes}m`;
  } catch {
    return OLLAMA_KEEP_ALIVE_DEFAULT;
  }
}

export function aggressiveQuantizationEnabled(): boolean {
  try {
    return localStorage.getItem('tc-aggressive-quant') === '1';
  } catch {
    return false;
  }
}

export function normalizeActiveCollections(
  ids: string[],
  validIds?: Set<string>,
  defaultId = 'default',
): string[] {
  const seen = new Set<string>();
  const cleaned = ids
    .map((id) => String(id || '').trim())
    .filter((id) => id && (!validIds || validIds.has(id)))
    .filter((id) => {
      if (seen.has(id)) return false;
      seen.add(id);
      return true;
    });
  if (cleaned.length === 0) return [defaultId];
  return cleaned;
}

export function nextActiveCollections(
  current: string[],
  toggledId: string,
  defaultId = 'default',
): string[] {
  const id = String(toggledId || '').trim() || defaultId;
  const active = normalizeActiveCollections(current, undefined, defaultId);
  if (id === defaultId) {
    if (active.includes(defaultId)) {
      const next = active.filter((value) => value !== defaultId);
      return next.length ? next : [defaultId];
    }
    return [...active, defaultId];
  }
  if (active.includes(id)) {
    const next = active.filter((value) => value !== id);
    return next.length ? next : [defaultId];
  }
  if (active.length === 1 && active[0] === defaultId) return [id];
  return normalizeActiveCollections(
    [...active, id],
    undefined,
    defaultId,
  );
}

function ollamaRuntimeOptions<T extends Record<string, number>>(
  base: T,
  opts: { preserveContext?: boolean } = {},
): T & { num_gpu?: number } {
  const options: T & { num_gpu?: number } = { ...base };
  if (aggressiveQuantizationEnabled()) {
    options.num_gpu = 0;
    const runtime = options as Record<string, number>;
    // Don't shrink the window for vision: the image + qwen3-vl's thinking phase
    // need the room, and clipping num_ctx to 2048 makes the answer come back
    // empty. Text turns can still be trimmed to save RAM.
    if (!opts.preserveContext && typeof runtime.num_ctx === 'number') {
      runtime.num_ctx = Math.min(runtime.num_ctx, 2048);
    }
  }
  return options;
}

function shouldUnloadAfterRequest(keepAlive: string | number): boolean {
  if (typeof keepAlive === 'number') return keepAlive <= 0;
  return /^0(?:s|m|h)?$/i.test(keepAlive.trim());
}

/** True for maths/exam/theory work even when the prompt embeds source code. */
export function isAnalyticalReasoning(text: string): boolean {
  const t = (text || '').toLowerCase();
  const hits = REASONING_HINTS.reduce((count, hint) => count + (t.includes(hint) ? 1 : 0), 0);
  return hits >= 3 || ((t.includes('examen') || t.includes('problem set')) && hits >= 2);
}

/** Split very long numbered exams into independent, stable model calls. */
export function splitAnalyticalTask(text: string, batchSize = 3): string[] {
  const starts = [...text.matchAll(/^(?=(?:#{1,6}\s*)?(?:\*\*)?\d+\.(?:\*\*)?\s*$)/gm)]
    .map((match) => match.index ?? 0);
  if (starts.length < 6 || batchSize < 1) return [text];
  const preamble = text.slice(0, starts[0]).trim();
  const sections = starts.map((start, index) => text.slice(start, starts[index + 1] ?? text.length).trim());
  const batches: string[] = [];
  for (let index = 0; index < sections.length; index += batchSize) {
    batches.push([
      preamble,
      `Resuelve únicamente este bloque (${index + 1}-${Math.min(index + batchSize, sections.length)} de ${sections.length}); conserva la numeración original:`,
      ...sections.slice(index, index + batchSize),
    ].filter(Boolean).join('\n\n'));
  }
  return batches;
}

/** Detect visible draft artifacts and incomplete analytical blocks. */
export function analyticalQualityIssues(answer: string, task: string): string[] {
  const issues: string[] = [];
  const clean = answer.trim();
  if (clean.length < 120) issues.push('respuesta demasiado corta');
  if (/\b(error detectado|me equivoqu[eé]|rehagamos|revisemos desde cero|no[,;:]?\s*(?:espera|mejor)|no es así|scratch|borrador)\b/i.test(clean)) {
    issues.push('contiene tanteos o autocorrecciones visibles');
  }
  if (/[,:=+\-*/(]\s*$/.test(clean) || /\.\.\.\s*$/.test(clean)) {
    issues.push('termina en una expresión incompleta');
  }
  if ((clean.match(/```/g)?.length ?? 0) % 2 !== 0 || (clean.match(/\$\$/g)?.length ?? 0) % 2 !== 0) {
    issues.push('contiene bloques Markdown o LaTeX sin cerrar');
  }
  const expected = [...task.matchAll(/^(?:#{1,6}\s*)?(?:\*\*)?(\d+)\.(?:\*\*)?\s*$/gm)]
    .map((match) => match[1]);
  for (const number of expected) {
    const heading = new RegExp(`(?:^|\\n)\\s*(?:#{1,6}\\s*)?(?:\\*\\*)?${number}\\.(?:\\*\\*)?`, 'm');
    if (!heading.test(clean)) issues.push(`falta el ejercicio ${number}`);
  }
  return issues;
}

/**
 * Route instantly while keeping model affinity across follow-up turns.
 * Loading a second Ollama model is usually slower than answering a short
 * follow-up with the model that is already warm.
 */
export function routeOllamaModel(text: string, messages: ChatMessage[] = []): string {
  const t = (text || '').toLowerCase();
  const isReasoning = isAnalyticalReasoning(text);
  // Code only on an EXPLICIT code action or unambiguous syntax — NOT merely
  // because a math exam mentions "api", "grafo" o "algoritmo", nor because a
  // sentence has an inline `backtick`. A build verb paired with a language name
  // (e.g. "escribe esto en Python") also counts as code intent.
  const hasBuildVerb = CODE_BUILD_VERBS.some((h) => t.includes(h));
  const hasLangHint = CODE_LANG_HINTS.some((h) => t.includes(h));
  const isCode = CODE_STRONG_RE.test(text)
    || CODE_ACTION_HINTS.some((h) => t.includes(h))
    || (hasBuildVerb && hasLangHint);
  const codeModel = modelSetting('tc-models-code', DEFAULT_MODEL_SETTINGS['tc-models-code']);
  const fastModel = modelSetting('tc-models-fast', DEFAULT_MODEL_SETTINGS['tc-models-fast']);
  const chatModel = modelSetting('tc-models-chat', DEFAULT_MODEL_SETTINGS['tc-models-chat']);
  // The general instruct chat model is the CLI-equivalent default: it answers
  // math and analytical prose well. The heavy "deep" (30B) model is never
  // auto-selected here — on a 16GB CPU box it isn't installed and would trigger
  // a 30GB pull/OOM. It stays reachable only via the RAG/research paths and the
  // explicit model picker in Settings.
  const candidate = isReasoning
    ? chatModel
    : isCode
    ? codeModel
    : t.trim().length < 25
      ? fastModel
      : chatModel;

  const textModels = new Set([codeModel, fastModel, chatModel]);
  const previousModel = [...messages]
    .reverse()
    .find((message) => message.role === 'assistant' && message.model && textModels.has(message.model))
    ?.model;
  if (!previousModel || previousModel === candidate) return candidate;

  // Strong technical intent switches to the coder immediately. An explicit
  // everyday topic (or an explicit topic change) switches back immediately.
  if (isReasoning || isCode) return candidate;
  const explicitGeneral = TOPIC_SHIFT_HINTS.some((h) => t.includes(h))
    || GENERAL_TOPIC_HINTS.some((h) => t.includes(h));
  if (explicitGeneral) return candidate;

  // Ambiguous/short follow-ups inherit the warm model, avoiding Ollama unload/load
  // churn in the middle of one task.
  return previousModel;
}

/**
 * Pick an actually-installed text model. Auto-routing must NEVER trigger a pull
 * of an un-installed model (that hangs/OOMs a 16GB box). If the routed model is
 * not present, fall back to an installed one, preferring the general chat model.
 */
export async function resolveTextModel(candidate: string): Promise<string> {
  const models = await availableOllamaModels();
  const codeModel = modelSetting('tc-models-code', DEFAULT_MODEL_SETTINGS['tc-models-code']);
  const role = candidate === codeModel ? 'code' : 'text';
  if (lastResolvedTextModel && lastResolvedTextModel.role === role
    && Date.now() - lastResolvedTextModel.at < 30_000 && hasModel(models, lastResolvedTextModel.model)) {
    console.info(`[TrinaxAI router] selected ${lastResolvedTextModel.model}: compatible model cooldown prevents replacing it with ${candidate}`);
    return lastResolvedTextModel.model;
  }
  // Empty list ⇒ Ollama unreachable or /api/tags failed; don't second-guess the
  // routed choice, let the request surface the real connection error.
  if (models.length === 0 || hasModel(models, candidate)) {
    console.info(`[TrinaxAI router] selected ${candidate}: requested model is installed`);
    lastResolvedTextModel = { model: candidate, at: Date.now(), role };
    return candidate;
  }
  const chatModel = modelSetting('tc-models-chat', DEFAULT_MODEL_SETTINGS['tc-models-chat']);
  const fastModel = modelSetting('tc-models-fast', DEFAULT_MODEL_SETTINGS['tc-models-fast']);
  for (const fallback of [chatModel, fastModel, codeModel]) {
    if (hasModel(models, fallback)) {
      console.info(`[TrinaxAI router] selected ${fallback}: ${candidate} is unavailable; using compatible installed fallback`);
      lastResolvedTextModel = { model: fallback, at: Date.now(), role: fallback === codeModel ? 'code' : 'text' };
      return fallback;
    }
  }
  // Last resort: any installed model, preferring an instruct/chat build.
  return models.find((m) => /instruct|chat/i.test(m)) ?? models[0];
}

/** Pick an installed tool-capable model for Agent requests.
 * The small Qwen 3.5 fast fleet may answer
 * chat but Ollama rejects its `tools` payload with HTTP 400.
 */
export async function resolveAgentModel(candidate: string): Promise<string> {
  const fastModel = modelSetting('tc-models-fast', DEFAULT_MODEL_SETTINGS['tc-models-fast']);
  const codeModel = modelSetting('tc-models-code', DEFAULT_MODEL_SETTINGS['tc-models-code']);
  const chatModel = modelSetting('tc-models-chat', DEFAULT_MODEL_SETTINGS['tc-models-chat']);
  const safeCandidate = candidate === fastModel ? codeModel : candidate;
  await availableOllamaModels();
  const supportsTools = (model: string) => ollamaModelCapabilities.get(model)?.has('tools')
    || ollamaModelCapabilities.get(`${model}:latest`)?.has('tools');
  if (supportsTools(safeCandidate)) {
    console.info(`[TrinaxAI router] selected ${safeCandidate}: installed model supports tools`);
    return safeCandidate;
  }
  for (const fallback of [codeModel, chatModel]) {
    if (supportsTools(fallback)) {
      console.info(`[TrinaxAI router] selected ${fallback}: ${candidate} lacks tools or is unavailable`);
      return fallback;
    }
  }
  throw new ApiError(`No installed model supports Agent tools (requested: ${candidate}).`, 424, 'model_incompatible');
}

async function availableOllamaModels(): Promise<string[]> {
  if (ollamaModelCache && (Date.now() - ollamaModelCacheAt) < MODEL_CACHE_TTL_MS) {
    return ollamaModelCache;
  }
  try {
    const res = await systemFetch(`${OLLAMA_BASE}/api/tags`, {
      signal: AbortSignal.timeout(2500),
      headers: systemRequestHeaders(),
    });
    if (!res.ok) throw new Error(`Ollama tags: ${res.status}`);
    const data = await res.json();
    const records = Array.isArray(data.models) ? data.models : [];
    ollamaModelCapabilities = new Map(records
      .filter((m: { name?: string }) => Boolean(m.name))
      .map((m: { name: string; capabilities?: string[] }) => [m.name, new Set(m.capabilities || [])]));
    ollamaModelCache = records.length
      ? records.map((m: { name?: string }) => m.name).filter(Boolean)
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

export function clearOllamaModelAvailabilityCache(): void {
  ollamaModelCache = null;
  ollamaModelCapabilities.clear();
  ollamaModelCacheAt = 0;
  lastResolvedTextModel = null;
}

export async function ensureOllamaModel(model: string, signal?: AbortSignal): Promise<void> {
  const models = await availableOllamaModels();
  if (hasModel(models, model)) return;
  if (localStorage.getItem('tc-auto-download-models') !== '1') {
    throw new ApiError(`Model "${model}" is not installed. Automatic downloads are disabled; install it from Settings.`, 424, 'model_unavailable');
  }
  const pending = ollamaPullsInFlight.get(model);
  if (pending) return pending;
  const pull = (async () => {
    const response = await systemFetch(`${OLLAMA_BASE}/api/pull`, {
      method: 'POST',
      headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ name: model, stream: false }),
      signal,
    });
    if (!response.ok) {
      throw new ApiError(`Ollama model "${model}" is not installed and could not be downloaded.`, response.status);
    }
    ollamaModelCache = null;
  })();
  ollamaPullsInFlight.set(model, pull);
  try {
    await pull;
  } finally {
    ollamaPullsInFlight.delete(model);
  }
}

async function routeVisionModel(_text: string): Promise<string> {
  // Vision is latency-sensitive and only runs for attached images. Respect the
  // configured lightweight model even when an older, much larger VL model is
  // already installed; ensureOllamaModel downloads it on first use.
  return modelSetting('tc-models-vision', VISION_MODEL);
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
  void systemFetch(`${OLLAMA_BASE}/api/generate`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ model, keep_alive: 0 }),
    keepalive: true,
  }).catch(() => undefined);
}

/** Estado de los servicios para los indicadores de la PWA. */
export async function checkStatus(): Promise<{ ollama: boolean; rag: boolean; indexed: boolean; ramPercent: number | null }> {
  const out = { ollama: false, rag: false, indexed: false, ramPercent: null as number | null };
  try {
    const r = await fetch(`${RAG_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      out.rag = true;
      const d = await r.json();
      out.indexed = !!d.indexed;
      out.ollama = typeof d?.ollama === 'boolean' ? d.ollama : false;
    }
  } catch { /* down */ }
  if (!out.rag) {
    try {
      const r = await systemFetch(`${OLLAMA_BASE}/api/tags`, {
        signal: AbortSignal.timeout(2500),
        headers: systemRequestHeaders(),
      });
      out.ollama = r.ok;
    } catch { /* down */ }
  }
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
    response = await fetch(url, { ...init, headers: systemRequestHeaders(init?.headers) });
  } catch (err) {
    // A caller-initiated abort is not a connectivity problem — re-throw it so
    // callers can ignore it instead of surfacing a false "TrinaxAI is off" error.
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError('Asegúrate de que TrinaxAI esté encendido. / Make sure TrinaxAI is turned on.', 0);
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(friendlyApiFailure(response.status, detail.slice(0, 500)), response.status);
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
    pages_total: typeof value.pages_total === 'number' ? value.pages_total : null,
    pages_processed: typeof value.pages_processed === 'number' ? value.pages_processed : 0,
    chunks_generated: typeof value.chunks_generated === 'number' ? value.chunks_generated : 0,
    batches_total: typeof value.batches_total === 'number' ? value.batches_total : null,
    batches_processed: typeof value.batches_processed === 'number' ? value.batches_processed : 0,
    progress_exact: Boolean(value.progress_exact),
    recent_activity: typeof value.recent_activity === 'string' ? value.recent_activity : undefined,
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
  source_id: string | null;
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
  web_search?: boolean;
  web_provider?: string | null;
  degraded?: boolean;
  error_code?: 'web_search_unavailable' | string;
  error_detail?: string;
}

export interface DeleteIndexedImportResult {
  deleted: number;
  removed_path: boolean;
  path: string;
  collection: string;
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
  opts: { limit?: number; offset?: number; q?: string; sourceId?: string | null; signal?: AbortSignal } = {},
): Promise<{ collection: string; file: string; source_id?: string | null; total: number; chunks: FileChunk[]; query?: string }> {
  const params = new URLSearchParams();
  if (opts.limit != null) params.set('limit', String(opts.limit));
  if (opts.offset != null) params.set('offset', String(opts.offset));
  if (opts.q) params.set('q', opts.q);
  if (opts.sourceId) params.set('source_id', opts.sourceId);
  const qs = params.toString();
  const encodedFile = file.split('/').map((part) => encodeURIComponent(part)).join('/');
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}/${encodedFile}/chunks${qs ? `?${qs}` : ''}`;
  return apiJson(url, { signal: opts.signal });
}

/** Delete all indexed chunks for a single file within a collection. */
export async function deleteSource(
  collection: string,
  file: string,
  sourceId?: string | null,
): Promise<{ deleted: number; collection: string; file: string; source_id?: string | null }> {
  const encodedFile = file.split('/').map((part) => encodeURIComponent(part)).join('/');
  const params = new URLSearchParams();
  if (sourceId) params.set('source_id', sourceId);
  const qs = params.toString();
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}/${encodedFile}${qs ? `?${qs}` : ''}`;
  return apiJson(url, { method: 'DELETE' });
}

/** Bulk-delete ALL indexed sources in a collection (keeps the collection itself). */
export async function deleteCollectionSources(
  collection: string,
): Promise<{ deleted: number; collection: string }> {
  const url = `${RAG_BASE}/v1/sources/${encodeURIComponent(collection)}`;
  return apiJson(url, { method: 'DELETE' });
}

/** Delete a browser-imported folder copy and its indexed chunks. */
export async function deleteIndexedImport(
  path: string,
  collectionId?: string,
): Promise<DeleteIndexedImportResult> {
  return apiJson(`${RAG_BASE}/system/index-imports`, {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, collection_id: collectionId || 'default' }),
  });
}

// ── File Watcher ──
export interface WatchJobStatus {
  status: 'idle' | 'queued' | 'running' | 'succeeded' | 'failed' | 'timed_out' | 'cancelled' | 'stopping' | string;
  pending_events: number;
  active_root: string | null;
  last_started_at: number | null;
  last_finished_at: number | null;
  last_duration_seconds: number | null;
  last_exit_code: number | null;
  last_error: string | null;
  last_stdout: string;
  last_stderr: string;
  runs_completed: number;
  runs_failed: number;
  runs_timed_out: number;
  runs_cancelled: number;
}

export interface WatchStatus {
  running: boolean;
  watching: string[];
  events_seen: number;
  started_at: number | null;
  job: WatchJobStatus;
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
  updated_at?: number;
  tags: string[];
  kind: 'fact' | 'preference' | 'decision' | 'note';
  provenance: 'manual' | 'inferred';
  expires_at?: number | null;
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
export async function addMemory(
  text: string,
  tags?: string[],
  options: { kind?: MemoryEntry['kind']; expiresAt?: number } = {},
): Promise<MemoryEntry> {
  return apiJson(`${RAG_BASE}/v1/memory`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      text,
      tags,
      kind: options.kind ?? 'note',
      provenance: 'manual',
      expires_at: options.expiresAt,
    }),
  });
}
export async function updateMemory(
  id: string,
  change: Partial<Pick<MemoryEntry, 'text' | 'tags' | 'kind' | 'expires_at'>>,
): Promise<MemoryEntry> {
  return apiJson(`${RAG_BASE}/v1/memory/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(change),
  });
}
export async function getRelevantMemoryContext(
  query: string,
  signal?: AbortSignal,
): Promise<MemoryEntry[]> {
  const data = await apiJson<{ memories?: MemoryEntry[] }>(`${RAG_BASE}/v1/memory/context`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, max_entries: 8 }),
    signal,
  });
  return Array.isArray(data.memories) ? data.memories : [];
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
  return apiJson<MemorySummary>(`${RAG_BASE}/v1/memory/summary`, { signal });
}

// ── Deep Research ──
export async function runResearch(
  query: string,
  opts: {
    collections?: string[];
    depth?: 1 | 2 | 3;
    webSearch?: boolean;
    searchQuery?: string;
    context?: string;
    includeLocal?: boolean;
    signal?: AbortSignal;
  } = {},
): Promise<ResearchResult> {
  const keepAlive = ollamaKeepAliveSetting();
  const payload = {
    query,
    search_query: opts.searchQuery,
    context: opts.context,
    collections: opts.collections,
    depth: opts.depth ?? 2,
    web_search: opts.webSearch,
    include_local: opts.includeLocal ?? false,
    model: opts.webSearch
      ? opts.depth === 1
        ? modelSetting('tc-models-fast', DEFAULT_MODEL_SETTINGS['tc-models-fast'])
        : modelSetting('tc-models-chat', DEFAULT_MODEL_SETTINGS['tc-models-chat'])
      : modelSetting('tc-models-deep', DEFAULT_MODEL_SETTINGS['tc-models-deep']),
    keep_alive: keepAlive,
    aggressive_quant: aggressiveQuantizationEnabled(),
  };
  const timeoutSignal = AbortSignal.timeout(90_000);
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeoutSignal]) : timeoutSignal;
  let preflight: { ok: boolean; model?: string; error_code?: string; error_detail?: string } | undefined;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      preflight = await apiJson(`${RAG_BASE}/v1/research/preflight`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal,
      });
      break;
    } catch (error) {
      if (attempt || !(error instanceof ApiError) || error.status !== 0) {
        if (opts.signal?.aborted) throw new DOMException('Research request cancelled.', 'AbortError');
        if (timeoutSignal.aborted) throw new ApiError('Research dependency check timed out.', 408, 'timeout');
        if (error instanceof ApiError && error.status === 0) {
          let ollamaReachable = false;
          try {
            const response = await systemFetch(`${OLLAMA_BASE}/api/tags`, {
              signal: AbortSignal.timeout(2500), headers: systemRequestHeaders(),
            });
            ollamaReachable = response.ok;
            if (response.status >= 500) throw new ApiError('Ollama is not running or is not reachable.', 503, 'ollama_unavailable');
          } catch (ollamaError) {
            if (ollamaError instanceof ApiError) throw ollamaError;
            throw new ApiError('The browser cannot reach the TrinaxAI services. Check the network connection.', 0, 'connection_error');
          }
          if (ollamaReachable) throw new ApiError('The RAG service is not running or is not reachable.', 503, 'rag_unavailable');
        }
        throw error;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 250));
    }
  }
  if (!preflight?.ok) {
    const code = preflight?.error_code || 'internal_error';
    const detail = preflight?.error_detail || '';
    const messages: Record<string, string> = {
      ollama_unavailable: 'Ollama is not running or is not reachable.',
      model_unavailable: `The selected model is not installed: ${detail}`,
      collection_empty: `The selected RAG collection is empty or not initialized: ${detail}`,
      web_search_disabled: 'Web search is disabled in the server configuration.',
    };
    throw new ApiError(messages[code] || detail || 'Research preflight failed.', 424, code);
  }
  payload.model = preflight.model || payload.model;
  try {
    const result = await apiJson<ResearchResult>(`${RAG_BASE}/v1/research`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });
    if (result.error_code) throw new ApiError(result.error_detail || result.answer, 503, result.error_code);
    return result;
  } catch (error) {
    if (opts.signal?.aborted) throw new DOMException('Research request cancelled.', 'AbortError');
    if (timeoutSignal.aborted) throw new ApiError('Research request timed out after 90 seconds.', 408, 'timeout');
    throw error;
  }
}

/** Build a standalone search query for follow-ups without trusting old AI answers. */
export function buildWebSearchQuery(
  query: string,
  history: ChatMessage[],
  now: Date = new Date(),
): { searchQuery: string; context: string } {
  const current = query.replace(/\s+/g, ' ').trim();
  const previousUserTurns = history
    .filter((message) => message.role === 'user')
    .map((message) => (message.displayContent ?? message.content).replace(/\s+/g, ' ').trim())
    .filter((text) => text && text !== current)
    .slice(-2);
  const context = previousUserTurns.map((text) => `User: ${text}`).join('\n').slice(-1800);
  const needsCurrentDate = /\b(actual(?:mente)?|ahora|hoy|reciente|últim\w*|temporada|current|latest|today|recent|season)\b/i.test(current);
  const searchTerms = [...previousUserTurns, current]
    .join(' ')
    .replace(/[¿?¡!.,:;|]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const dateHint = needsCurrentDate ? ` ${now.toISOString().slice(0, 10)}` : '';
  const sourceHint = detectTurnLanguage(current) === 'es' ? ' fuente oficial' : ' official source';
  return {
    // Keep this natural and compact: verbose instruction-like queries trigger
    // anti-bot challenges in HTML search providers and rank worse.
    searchQuery: `${searchTerms}${dateHint}${sourceHint}`.slice(0, 500),
    context,
  };
}

/** True only for an explicit request to consult the public web. */
export function isWebSearchRequest(query: string): boolean {
  const text = query.replace(/\s+/g, ' ').trim().toLowerCase();
  const patterns = [
    /\b(?:busca|buscar|búscalo|buscarlo|investiga|consulta|verifica)\b.{0,35}\b(?:internet|web|en\s+línea|online)\b/i,
    /\b(?:internet|web|en\s+línea|online)\b.{0,35}\b(?:busca|buscar|investiga|consulta|verifica)\b/i,
    /\b(?:search|look\s+up|research|check|verify)\b.{0,35}\b(?:the\s+)?(?:internet|web|online)\b/i,
    /\b(?:internet|web|online)\b.{0,35}\b(?:search|look\s+up|research|check|verify)\b/i,
  ];
  return patterns.some((pattern) => pattern.test(text));
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
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
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
    xhr.onerror = () => { finish(); reject(new ApiError('Folder import failed: network error', 0)); };
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
    throw new ApiError(`Index job status failed: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 500)}` : ''}`, response.status);
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
        const detail = typeof result === 'object'
          ? JSON.stringify(result).slice(0, 500)
          : String(xhr.responseText || '').slice(0, 500);
        reject(new ApiError(`Document extraction failed: ${xhr.status} ${xhr.statusText}${detail ? `\n${detail}` : ''}`, xhr.status));
        return;
      }
      options.onUploadProgress?.(100);
      resolve(result as ExtractedDocument);
    };
    xhr.onerror = () => reject(new ApiError('Document extraction failed: network error', 0));
    xhr.ontimeout = () => reject(new ApiError('Document extraction timed out after 2 minutes.', 408));
    xhr.onabort = () => reject(new DOMException('Document extraction cancelled', 'AbortError'));
    options.signal?.addEventListener('abort', () => xhr.abort(), { once: true });
    options.onUploadProgress?.(1);
    xhr.send(form);
  });
}

/**
 * Core chat policy. Keep product/creator facts out of ordinary turns: compact
 * local models tend to repeat salient system-prompt biography even when it is
 * unrelated to the request. The creator details are supplied only when asked.
 */
export function ollamaSystemPrompt(lang: 'en' | 'es'): ChatMessage {
  if (lang === 'en') {
    return {
      role: 'system',
      content:
      'You are TrinaxAI, a capable general-purpose AI assistant. ' +
      'Answer the current request first and follow the user\'s latest correction or constraint. ' +
      'Do not mention your identity, creator, local execution, privacy, links, or product mission unless the user asks about them. ' +
      'Do not force local-first choices: recommend cloud or local tools according to the user\'s actual requirements. ' +
      'Always answer in the language of the current user message. Be direct, useful, honest, and natural. ' +
      'Treat words such as "only", "just", "nothing else", and equivalent corrections as strict scope limits. ' +
      'Do not add unrequested background, marketing, setup, next steps, or a follow-up question. Do not assume the user\'s stack; when it matters, state the condition briefly. ' +
      'Exception for social conversation: if the user only greets you, greet them back warmly and briefly, and invite them to tell you what they need. Never scold or reject a greeting. ' +
      'If asked who you are, say clearly that you are TrinaxAI, briefly describe what you can help with, and share its official repository: https://github.com/TrinaxCode/TrinaxAI. ' +
      'Do not invent details about the user hardware, location, identity, or files. ' +
      'If you do not know something or lack enough context, say so and suggest how to verify it.\n\n' +
      'USER:\n' +
      `- ${getUserSystemInstruction('en')}\n\n` +
      'STYLE:\n' +
      '- Greet only once at the start of a new conversation. In follow-up turns, do not start with "hola", "hello", "claro", "me alegra", or welcome phrases; answer directly.\n' +
      '- Match the answer length to the question. For a simple question, answer briefly. For complex, multi-part, analytical, or math questions, give a complete, step-by-step answer and do not omit steps for the sake of brevity.\n' +
      '- For math, show the reasoning and format expressions in LaTeX ($...$ inline, $$...$$ for display). Use Markdown tables for tabular data.\n' +
      '- For code or debugging, give concrete steps and verifiable examples.\n' +
      '- For images, describe visible observations and avoid assuming non-visible facts.\n' +
      '- Do not say you run on specific hardware unless the user has said that in this conversation.',
    };
  }
  return {
    role: 'system',
    content:
    'Eres TrinaxAI, un asistente de IA de propósito general. ' +
    'Responde primero a la petición actual y respeta la corrección o restricción más reciente del usuario. ' +
    'No menciones tu identidad, creador, ejecución local, privacidad, enlaces ni misión del producto salvo que el usuario lo pregunte. ' +
    'No impongas soluciones local-first: recomienda nube o local según los requisitos reales del usuario. ' +
    'Responde en el idioma del usuario. Sé directo, útil, honesto y natural. ' +
    'Trata expresiones como "solo", "nada más" y correcciones equivalentes como límites estrictos de alcance. ' +
    'No añadas contexto, marketing, preparación, próximos pasos ni preguntas finales que no se pidieron. No asumas el stack del usuario; cuando importe, indica brevemente la condición. ' +
    'Excepción para conversación social: si el usuario solo saluda, devuélvele el saludo con amabilidad y brevedad e invítalo a decir qué necesita. Nunca regañes ni rechaces un saludo. ' +
    'Si pregunta quién eres, di claramente que eres TrinaxAI, describe brevemente en qué puedes ayudar y comparte su repositorio oficial: https://github.com/TrinaxCode/TrinaxAI. ' +
    'No inventes detalles sobre el hardware del usuario, su ubicación, su identidad o sus archivos. ' +
    'Si no sabes algo o no tienes contexto suficiente, dilo y sugiere cómo verificarlo.\n\n' +
    'USUARIO:\n' +
    `• ${getUserSystemInstruction('es')}\n\n` +
    'ESTILO:\n' +
    '• Saluda solo una vez al inicio de una conversación nueva. En turnos posteriores no empieces con "hola", "claro", "me alegra" ni fórmulas de bienvenida; responde directo.\n' +
    '• Ajusta la extensión a la pregunta. Para preguntas simples, responde breve. Para preguntas complejas, de varias partes, analíticas o de matemáticas, da una respuesta completa y paso a paso, sin omitir pasos por brevedad.\n' +
    '• Para matemáticas, muestra el razonamiento y formatea las expresiones en LaTeX ($...$ en línea, $$...$$ para bloques). Usa tablas Markdown para datos tabulares.\n' +
    '• Para código o depuración, da pasos concretos y ejemplos verificables.\n' +
    '• Para imágenes, describe observaciones visibles y evita asumir datos no visibles.\n' +
    '• No digas que corres en hardware específico salvo que el usuario lo haya dicho en esta conversación.',
  };
}

/** Minimal vision policy: visual evidence is the focus, not product identity. */
export function visionSystemPrompt(lang: 'en' | 'es'): ChatMessage {
  return {
    role: 'system',
    content: lang === 'en'
      ? 'Analyze the attached image and answer only the user\'s question. Start with the directly visible result. Distinguish observations from uncertain inferences; do not invent hidden details. Keep simple identification questions concise. Do not mention TrinaxAI, its creator, links, local execution, or privacy unless explicitly asked.'
      : 'Analiza la imagen adjunta y responde solo la pregunta del usuario. Empieza por el resultado directamente visible. Distingue observaciones de inferencias inciertas y no inventes detalles ocultos. Sé breve ante preguntas simples de identificación. No menciones TrinaxAI, su creador, enlaces, ejecución local ni privacidad salvo que se pregunte explícitamente.',
  };
}

const CREATOR_QUERY_HINTS = [
  'trinaxcode', 'quién te creó', 'quien te creo', 'quién es tu creador',
  'quien es tu creador', 'tu creador', 'tu origen', 'quién lo creó',
  'quien lo creo', 'sus enlaces', 'sus links', 'sus redes',
  'who created you', 'who made you', 'your creator', 'who is your creator',
  'creator links',
];

export function creatorSystemPrompt(messages: ChatMessage[], lang: 'en' | 'es'): ChatMessage[] {
  const current = [...messages].reverse().find((message) => message.role === 'user')?.content.toLowerCase() ?? '';
  const recentContext = messages.slice(-6).map((message) => message.content.toLowerCase()).join('\n');
  const directRequest = CREATOR_QUERY_HINTS.some((hint) => current.includes(hint));
  const creatorFollowUp = /\b(enlaces|links?|github|linkedin|redes|perfil)\b/i.test(current)
    && CREATOR_QUERY_HINTS.some((hint) => recentContext.includes(hint));
  if (!directRequest && !creatorFollowUp) return [];
  return [{
    role: 'system',
    content: lang === 'en'
      ? 'Verified creator facts: TrinaxAI was created by TrinaxCode, a Full Stack Web Developer based in Tuxtla Gutiérrez, Chiapas, originally from Nicaragua. Their work prioritizes production impact: live products that generate traffic, leads and revenue. Expertise includes React, TypeScript, Django, PostgreSQL and Firebase; they completed Harvard CS50x/CS50W and Stanford Code in Place 2026, and are a TikTok creator with 60K+ followers. Official links: GitHub https://github.com/TrinaxCode, LinkedIn https://www.linkedin.com/in/trinaxcode/, X https://x.com/TrinaxCode, TikTok https://www.tiktok.com/@trinaxcode, Instagram https://www.instagram.com/trinaxcode/, Facebook https://www.facebook.com/TrinaxCode, ORCID https://orcid.org/0009-0009-2321-9834, email mailto:trinaxcode@gmail.com, WhatsApp https://wa.me/529618533231. When the user asks who the creator is, this overrides any brevity rule: never answer with only the name. Always give a complete answer of at least two or three sentences covering, at minimum, the role (Full Stack Web Developer), origin/location, and key expertise, phrased naturally for the question. For links or social media, provide the complete official list. Use these exact URLs and never invent or alter profiles.'
      : 'Datos verificados del creador: TrinaxAI fue creado por TrinaxCode, un Full Stack Web Developer radicado en Tuxtla Gutiérrez, Chiapas, originario de Nicaragua. Su trabajo prioriza el impacto en producción: productos vivos que generan tráfico, leads e ingresos. Domina React, TypeScript, Django, PostgreSQL y Firebase; completó Harvard CS50x/CS50W y Stanford Code in Place 2026, y es creador de contenido en TikTok con más de 60K seguidores. Enlaces oficiales: GitHub https://github.com/TrinaxCode, LinkedIn https://www.linkedin.com/in/trinaxcode/, X https://x.com/TrinaxCode, TikTok https://www.tiktok.com/@trinaxcode, Instagram https://www.instagram.com/trinaxcode/, Facebook https://www.facebook.com/TrinaxCode, ORCID https://orcid.org/0009-0009-2321-9834, correo mailto:trinaxcode@gmail.com, WhatsApp https://wa.me/529618533231. Cuando el usuario pregunte quién es el creador, esto anula cualquier regla de brevedad: nunca respondas solo con el nombre. Da siempre una respuesta completa de al menos dos o tres oraciones que cubra, como mínimo, el rol (Full Stack Web Developer), origen/ubicación y expertise principal, redactada de forma natural para la pregunta. Si pide enlaces o redes, entrega la lista oficial completa. Usa exactamente estas URL y nunca inventes ni alteres perfiles.',
  }];
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

export function detectTurnLanguage(text: string): 'en' | 'es' {
  // Count complete words only. Substring matching made neutral words such as
  // "error" influence the result and was especially unreliable for short
  // questions and code-related messages.
  const words = text.toLocaleLowerCase().match(/[a-záéíóúüñ]+/gi) ?? [];
  const enWords = new Set([
    'the', 'a', 'an', 'this', 'that', 'these', 'those', 'is', 'are', 'am',
    'be', 'was', 'were', 'do', 'does', 'did', 'how', 'what', 'why', 'when',
    'where', 'which', 'who', 'can', 'could', 'would', 'should', 'please',
    'thanks', 'thank', 'hello', 'hi', 'hey', 'install', 'file', 'folder',
    'tell', 'explain', 'write', 'make', 'create', 'help', 'fix', 'you',
    'your', 'my', 'we', 'with', 'from', 'to', 'of', 'in', 'on', 'and', 'or',
    'but', 'for', 'yes',
  ]);
  const esWords = new Set([
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'este', 'esta',
    'estos', 'estas', 'es', 'son', 'soy', 'eres', 'está', 'están', 'hay',
    'que', 'qué', 'cómo', 'como', 'por', 'para', 'con', 'sin', 'de', 'del',
    'en', 'y', 'o', 'pero', 'hola', 'gracias', 'instalar', 'archivo',
    'carpeta', 'dime', 'explica', 'escribe', 'haz', 'crea', 'ayuda', 'arregla',
    'tú', 'tu', 'yo', 'mi', 'me', 'te', 'cuando', 'cuándo', 'dónde', 'porque',
    'también', 'sí',
  ]);
  const enHits = words.filter((word) => enWords.has(word)).length;
  const esHits = words.filter((word) => esWords.has(word)).length;
  if (enHits !== esHits) return enHits > esHits ? 'en' : 'es';
  return /[¿¡ñáéíóúü]/i.test(text) ? 'es' : 'en';
}

function languageSystemPrompt(messages: ChatMessage[]): ChatMessage {
  const last = [...messages].reverse().find((message) => message.role === 'user')?.content ?? '';
  const detected = detectTurnLanguage(last);
  return {
    role: 'system',
    content: detected === 'en'
      ? 'The current user message is in English. Answer in English. This overrides the interface language, profile language, previous conversation language, and any indexed document language unless the user explicitly asks for another language.'
      : 'El mensaje actual del usuario esta en espanol. Responde en espanol. Esto tiene prioridad sobre el idioma de la interfaz, el perfil, la conversacion previa y los documentos indexados, salvo que el usuario pida explicitamente otro idioma.',
  };
}

function turnLanguage(messages: ChatMessage[]): 'en' | 'es' {
  const last = [...messages].reverse().find((message) => message.role === 'user')?.content ?? '';
  return detectTurnLanguage(last);
}

function conversationStylePrompt(messages: ChatMessage[]): ChatMessage {
  const hasAssistantReply = messages.some((m) => m.role === 'assistant');
  const current = [...messages].reverse().find((message) => message.role === 'user')?.content.trim().toLowerCase() ?? '';
  const greetingOnly = /^(hola|buenas|buenos días|buenos dias|buenas tardes|buenas noches|hello|hi|hey)[!.¡¿?\s]*$/i.test(current);
  return {
    role: 'system',
    content: hasAssistantReply
      ? 'This conversation already has assistant replies. Do not greet again. Do not start with "Hola", "Hello", "Claro", "Me alegra", or welcome phrases. Answer the current request directly.'
      : greetingOnly
        ? 'The user only sent a greeting. Greet them back warmly and briefly, then invite them to say what they need.'
        : 'This is the first assistant reply, but the user did not merely greet you. Do not open with a greeting or welcome phrase; answer the request directly.',
  };
}

function analyticalSystemPrompt(lang: 'en' | 'es'): ChatMessage {
  return {
    role: 'system',
    content: lang === 'en'
      ? 'This is a long analytical task. Solve every numbered item and every subpart; do not merely acknowledge the exam or wish the user luck. Show the necessary derivations, exact results, proofs, algorithm tables, correctness and complexity analysis. Continue until all requested parts are answered, using clear numbered sections.'
      : 'Esta es una tarea analítica extensa. Resuelve todos los ejercicios numerados y cada inciso; no te limites a reconocer el examen ni a desear suerte. Verifica silenciosamente cada operación antes de escribirla: no muestres tanteos, falsos comienzos, autocorrecciones ni texto de borrador. Muestra derivaciones limpias, resultados exactos, demostraciones, tablas de algoritmos y análisis de correctitud y complejidad. Sé riguroso pero suficientemente conciso para terminar todo el bloque, usando secciones numeradas claras.',
  };
}

function truncateForContext(content: string, maxChars: number): string {
  if (content.length <= maxChars) return content;
  const marker = '\n\n[...contexto anterior truncado para ajustarse al modelo...]\n\n';
  if (maxChars <= marker.length + 80) return content.slice(-maxChars);
  const available = maxChars - marker.length;
  const head = Math.ceil(available * 0.55);
  return `${content.slice(0, head)}${marker}${content.slice(-(available - head))}`;
}

/**
 * Keep the newest useful conversation context inside the local model window.
 * Ollama otherwise truncates oversized prompts implicitly, which can discard
 * the current question or system instructions and sharply degrade answers.
 */
export function compactChatContext(
  messages: ChatMessage[],
  maxChars = DIRECT_CHAT_CONTEXT_CHARS,
): ChatMessage[] {
  if (maxChars <= 0 || messages.length === 0) return [];
  const selected: ChatMessage[] = [];
  let remaining = maxChars;

  for (let index = messages.length - 1; index >= 0 && remaining > 0; index -= 1) {
    const message = messages[index];
    const content = truncateForContext(message.content ?? '', remaining);
    selected.push({ ...message, content });
    remaining -= content.length;
  }

  return selected.reverse();
}

function textMessagesForOllama(messages: ChatMessage[]) {
  const lang = turnLanguage(messages);
  const last = [...messages].reverse().find((message) => message.role === 'user')?.content ?? '';
  const analytical = isAnalyticalReasoning(last) ? [analyticalSystemPrompt(lang)] : [];
  const system = isVoiceTurn(messages)
    ? [ollamaSystemPrompt(lang), ...creatorSystemPrompt(messages, lang), ...analytical, languageSystemPrompt(messages), conversationStylePrompt(messages), voiceSystemPrompt(lang)]
    : [ollamaSystemPrompt(lang), ...creatorSystemPrompt(messages, lang), ...analytical, languageSystemPrompt(messages), conversationStylePrompt(messages)];
  return [
    ...system,
    ...compactChatContext(messages).map((m) => ({ role: m.role, content: m.content })),
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
  let completed = false;

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) {
        if (pending.trim()) onLine(pending);
        completed = true;
        break;
      }
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split('\n');
      pending = lines.pop() ?? '';
      for (const line of lines) onLine(line);
    }
  } finally {
    // Cancel unless the body was fully drained. This covers aborts *and* the
    // case where onLine() throws on a backend error frame — otherwise the HTTP
    // body would be left undrained, leaking the connection/stream.
    if (!completed) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export function parseOllamaJsonLine(line: string): { token?: string; error?: string; thinking?: string; doneReason?: string } {
  const trimmed = line.trim();
  if (!trimmed) return {};
  try {
    const parsed = JSON.parse(trimmed);
    const token = typeof parsed?.message?.content === 'string' ? parsed.message.content : '';
    if (typeof parsed?.error === 'string' && parsed.error.trim()) {
      return { error: parsed.error.trim() };
    }
    const out: { token?: string; thinking?: string; doneReason?: string } = {};
    if (token) out.token = token;
    // qwen3-vl streams its reasoning in a separate `thinking` field. We don't
    // render it, but tracking it lets the caller detect a "thought the whole
    // budget away, produced no content" turn instead of showing a blank reply.
    if (typeof parsed?.message?.thinking === 'string' && parsed.message.thinking) {
      out.thinking = parsed.message.thinking;
    }
    if (parsed?.done && typeof parsed?.done_reason === 'string') {
      out.doneReason = parsed.done_reason;
    }
    return out;
  } catch {
    return {};
  }
}

function appendOllamaJsonLine(line: string, onToken: (token: string) => void): string {
  const event = parseOllamaJsonLine(line);
  if (event.error) throw new Error(`Ollama: ${event.error}`);
  // Gemma 3n may occasionally leak SentencePiece's whitespace marker (▁)
  // through Ollama. It is tokenizer metadata, never intended user-visible text.
  const token = event.token?.replace(/▁+/g, ' ');
  if (token) onToken(token);
  return token ?? '';
}

function parseRetrievalMeta(value: unknown): StreamMeta {
  if (!value || typeof value !== 'object') return {};
  const raw = value as Record<string, unknown>;
  const meta: StreamMeta = {};
  if (typeof raw.model === 'string') meta.model = raw.model;
  if (typeof raw.project === 'string' || raw.project === null) meta.project = raw.project as string | null;
  if (raw.mode === 'auto' || raw.mode === 'knowledge' || raw.mode === 'model') meta.mode = raw.mode;
  if (typeof raw.rag_used === 'boolean') meta.rag_used = raw.rag_used;
  if (typeof raw.result_count === 'number') meta.result_count = raw.result_count;
  if (Array.isArray(raw.collections) && raw.collections.every((item) => typeof item === 'string')) {
    meta.collections = raw.collections as string[];
  }
  return meta;
}

export function parseRagSseLine(line: string): {
  token?: string;
  meta?: StreamMeta;
  done?: boolean;
  error?: string;
} {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return {};
  const data = trimmed.slice(6);
  if (data === '[DONE]') return { done: true };
  try {
    const parsed = JSON.parse(data);
    if (parsed.trinaxai) {
      return { meta: parseRetrievalMeta(parsed.trinaxai) };
    }
    if (parsed.trinaxai_sources) {
      return {
        meta: {
          sources: parsed.trinaxai_sources as Source[],
          ...parseRetrievalMeta(parsed.trinaxai_retrieval),
        },
      };
    }
    if (typeof parsed.trinaxai_error === 'string' && parsed.trinaxai_error.trim()) {
      return { error: parsed.trinaxai_error.trim() };
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
  options: StreamOptions = {},
): Promise<string> {
  const lastMessage = messages[messages.length - 1];
  const last = lastMessage?.content ?? '';
  // Solo el turno actual con imagen debe activar visión. Si no, no cargamos 7B.
  if (lastMessage?.image) {
    return streamOllamaVision(messages, onToken, signal, onMeta, options);
  }

  const routed = routeOllamaModel(last, messages);
  const analyticalTurn = isAnalyticalReasoning(last);
  // Auto-routing must never pull: resolve to an installed model instead of
  // letting ensureOllamaModel download (a 30GB pull would OOM a 16GB box).
  const model = await resolveTextModel(routed);
  const keepAlive = ollamaKeepAliveSetting();
  onMeta?.({ model });
  let fullContent = '';
  const batches = analyticalTurn ? splitAnalyticalTask(last) : [last];
  try {
    for (let batchIndex = 0; batchIndex < batches.length; batchIndex += 1) {
      if (signal?.aborted) break;
      const batchMessages = batches.length === 1
        ? messages
        : messages.map((message, index) => index === messages.length - 1
          ? { ...message, content: batches[batchIndex] }
          : message);
      const baseRequestMessages = textMessagesForOllama(batchMessages);
      const generateAttempt = async (requestMessages: Array<{ role: string; content: string }>) => {
        const response = await systemFetch(`${OLLAMA_BASE}/api/chat`, {
          method: 'POST',
          headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            model,
            messages: requestMessages,
            stream: true,
            think: false,
            keep_alive: keepAlive,
            options: ollamaRuntimeOptions({
              num_ctx: analyticalTurn ? ANALYTICAL_NUM_CTX : TEXT_NUM_CTX,
              num_predict: analyticalTurn ? ANALYTICAL_NUM_PREDICT : TEXT_NUM_PREDICT,
              num_thread: 8,
              temperature: analyticalTurn ? 0.15 : 0.4,
              repeat_penalty: analyticalTurn ? 1.08 : 1.1,
            }, { preserveContext: analyticalTurn }),
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
        let generated = '';
        await readStreamLines(response, signal, (line) => {
          generated += appendOllamaJsonLine(line, analyticalTurn ? () => undefined : onToken);
        });
        return generated;
      };

      let batchContent = await generateAttempt(baseRequestMessages);
      if (analyticalTurn && !signal?.aborted) {
        const issues = analyticalQualityIssues(batchContent, batches[batchIndex]);
        if (issues.length > 0) {
          batchContent = await generateAttempt([
            ...baseRequestMessages,
            { role: 'assistant', content: batchContent },
            {
              role: 'user',
              content: `Reescribe todo el bloque desde cero y corrige estos problemas: ${issues.join('; ')}. Entrega únicamente la versión final limpia, completa y verificada.`,
            },
          ]);
        }
        if (batchIndex > 0) {
          const separator = '\n\n---\n\n';
          fullContent += separator;
          onToken(separator);
        }
        fullContent += batchContent;
        onToken(batchContent);
      } else {
        fullContent += batchContent;
      }
    }
  } finally {
    if (shouldUnloadAfterRequest(keepAlive)) unloadOllamaModel(model);
  }
  if (!signal?.aborted && !options.temporary) recordUsage('ollama', model, messages, fullContent);
  return fullContent;
}

/** Vision models are more reliable through Ollama's native /api/chat schema. */
async function streamOllamaVision(
  messages: ChatMessage[],
  onToken: (token: string) => void,
  signal?: AbortSignal,
  onMeta?: (m: StreamMeta) => void,
  options: StreamOptions = {},
): Promise<string> {
  const lastIndex = messages.length - 1;
  const lastContent = messages[lastIndex]?.content ?? '';
  const lang = turnLanguage(messages);
  const model = await routeVisionModel(lastContent);
  await ensureOllamaModel(model, signal);
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

  const response = await systemFetch(`${OLLAMA_BASE}/api/chat`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      model,
      messages: [
        visionSystemPrompt(lang),
        languageSystemPrompt(messages),
        conversationStylePrompt(messages),
        ...(isVoiceTurn(messages) ? [voiceSystemPrompt(lang)] : []),
        ...apiMessages,
      ],
      stream: true,
      // Ask qwen3-vl to skip its reasoning phase so the written answer starts
      // immediately instead of burning latency (and the token budget) thinking.
      // Harmless on models that don't support it (ignored), and paired with a
      // generous num_predict + an empty-answer fallback so a reply always shows.
      think: false,
      keep_alive: keepAlive,
      options: ollamaRuntimeOptions({
        num_ctx: VISION_NUM_CTX,
        num_predict: VISION_NUM_PREDICT,
        num_thread: 8,
      }, { preserveContext: true }),
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
  let sawThinking = false;
  let doneReason: string | undefined;

  try {
    await readStreamLines(response, signal, (line) => {
      const event = parseOllamaJsonLine(line);
      if (event.error) throw new Error(`Ollama: ${event.error}`);
      if (event.thinking) sawThinking = true;
      if (event.doneReason) doneReason = event.doneReason;
      if (event.token) {
        fullContent += event.token;
        onToken(event.token);
      }
    });
  } catch (err) {
    // A user-initiated abort must propagate as-is, never be reclassified as a
    // model failure (some runtimes surface aborts as "terminated"/"network").
    if (signal?.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
      throw err;
    }
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

  // Guard against the silent-empty-answer bug: qwen3-vl can spend its entire
  // num_predict budget "thinking" and stop (done_reason="length") before it
  // emits any visible content. Rather than show a blank bubble, surface a clear,
  // actionable message so the turn never looks like it did nothing.
  if (!signal?.aborted && !fullContent.trim() && (sawThinking || doneReason === 'length')) {
    const fallback = lang === 'en'
      ? 'The local vision model used its whole budget reasoning about the image and did not finish a written answer. Try a shorter, more specific question (e.g. "What text is in this image?") or enable higher quality in settings.'
      : 'El modelo de visión local agotó su presupuesto razonando sobre la imagen y no alcanzó a escribir la respuesta. Prueba una pregunta más corta y concreta (p. ej. "¿Qué texto hay en esta imagen?") o activa mayor calidad en ajustes.';
    onToken(fallback);
    fullContent = fallback;
  }
  if (!signal?.aborted && !options.temporary) recordUsage('ollama-vision', model, messages, fullContent);
  return fullContent;
}

/**
 * Describe an attached image with the local vision model so a text-only agent
 * can reason about it. The agent backend speaks only text, so we run one vision
 * pass here and hand the agent a written description instead of the pixels.
 *
 * `image` is a data URL (already reduced by {@link prepareImageForVision}).
 * Returns the model's plain-text observation, or throws on vision failure.
 */
export async function describeImageForAgent(
  image: string,
  prompt: string,
  signal?: AbortSignal,
): Promise<string> {
  const lang = detectLangFromText(prompt);
  const model = await routeVisionModel(prompt);
  await ensureOllamaModel(model, signal);
  const keepAlive = ollamaKeepAliveSetting();
  const instruction = lang === 'en'
    ? 'Describe this image in precise, concrete detail so another assistant can act on it. Transcribe any visible text or code verbatim. State only what is visible.'
    : 'Describe esta imagen con detalle preciso y concreto para que otro asistente pueda actuar sobre ella. Transcribe literalmente cualquier texto o código visible. Indica solo lo que se ve.';
  const userText = prompt.trim()
    ? (lang === 'en' ? `${instruction}\nThe user asks: ${prompt.trim()}` : `${instruction}\nEl usuario pregunta: ${prompt.trim()}`)
    : instruction;
  const response = await systemFetch(`${OLLAMA_BASE}/api/chat`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      model,
      messages: [{ role: 'user', content: userText, images: [base64FromDataUrl(image)] }],
      stream: true,
      think: false,
      keep_alive: keepAlive,
      options: ollamaRuntimeOptions({
        num_ctx: VISION_NUM_CTX,
        num_predict: VISION_NUM_PREDICT,
        num_thread: 8,
      }, { preserveContext: true }),
    }),
    signal,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(`Ollama visión: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 240)}` : ''}`, response.status);
  }
  let out = '';
  try {
    await readStreamLines(response, signal, (line) => {
      const event = parseOllamaJsonLine(line);
      if (event.error) throw new Error(`Ollama: ${event.error}`);
      if (event.token) out += event.token;
    });
  } finally {
    if (shouldUnloadAfterRequest(keepAlive)) unloadOllamaModel(model);
  }
  return out.trim();
}

/** Best-effort language guess from a single string (for one-shot vision turns). */
function detectLangFromText(text: string): 'en' | 'es' {
  return turnLanguage([{ role: 'user', content: text || '' }]);
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
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')?.content ?? '';
  const keepAlive = ollamaKeepAliveSetting();
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
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      messages: [
        { role: 'system', content: `${getUserSystemInstruction(lang)}\n\n${languageSystemPrompt(messages).content}` },
        ...clean,
      ],
      stream: true,
      collections: options.collections,
      model: routeOllamaModel(lastUser, messages),
      keep_alive: keepAlive,
      aggressive_quant: aggressiveQuantizationEnabled(),
      // Choosing the RAG engine is an explicit product intent: retrieval must
      // run even when the natural-language classifier sees no grounding phrase.
      mode: 'knowledge',
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
    if (event.error) throw new Error(`RAG: ${event.error}`);
    if (event.meta) onMeta?.(event.meta);
    if (event.token) {
      fullContent += event.token;
      onToken(event.token);
    }
  });
  return fullContent;
}

// ── TrinaxAI Agent (file/shell tool-use over a workspace) ──

/** Default workspace root for the agent (user-overridable in Settings). */
export function agentWorkspaceRoot(): string {
  try {
    const v = localStorage.getItem('tc-agent-workspace')?.trim();
    if (v) return v;
  } catch { /* localStorage unavailable */ }
  return APP_CONFIG.defaultIndexDir;
}

/** One event emitted by the agent SSE stream. */
export type AgentEvent =
  | { type: 'start'; session_id: string; workspace: string; model: string }
  | { type: 'status'; state: 'running'; elapsed_seconds: number; idle_seconds: number; current_tool: string | null; steps: number; last_activity: number }
  | { type: 'tool_start'; tool: string; dangerous: boolean; args: Record<string, string> }
  | { type: 'tool_result'; tool: string; result: string }
  | { type: 'approval_request'; approval_id: string; tool: string; args: Record<string, string> }
  | { type: 'approval_timeout'; approval_id: string }
  | { type: 'token'; content: string }
  | { type: 'done'; answer: string }
  | { type: 'error'; error: string; recoverable?: boolean };

function parseAgentSseLine(line: string): AgentEvent | { done: true } | null {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return null;
  const data = trimmed.slice(6);
  if (data === '[DONE]') return { done: true };
  try {
    const parsed = JSON.parse(data);
    return parsed && typeof parsed.type === 'string' ? (parsed as AgentEvent) : null;
  } catch {
    return null;
  }
}

/**
 * Run the agent for one turn, streaming events. Dangerous actions arrive as
 * `approval_request` events; call {@link approveAgentAction} with the id to let
 * them proceed (or reject). The returned promise resolves when the stream ends.
 */
export async function runAgent(
  messages: ChatMessage[],
  onEvent: (event: AgentEvent) => void,
  opts: { workspace?: string; model?: string; maxSteps?: number; yolo?: boolean; webSearch?: boolean; knowledgeSearch?: boolean; deepResearch?: boolean; signal?: AbortSignal } = {},
): Promise<void> {
  const response = await fetch(`${RAG_BASE}/v1/agent`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({
      messages: messages.map((m) => ({ role: m.role, content: m.content })),
      workspace: opts.workspace ?? agentWorkspaceRoot(),
      model: opts.model,
      max_steps: opts.maxSteps ?? 25,
      yolo: opts.yolo ?? false,
      web_search: opts.webSearch ?? false,
      knowledge_search: opts.knowledgeSearch ?? true,
      deep_research: opts.deepResearch ?? false,
    }),
    signal: opts.signal,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw new ApiError(`Agent: ${response.status} ${response.statusText}${detail ? `\n${detail.slice(0, 300)}` : ''}`, response.status);
  }
  let terminal = false;
  await readStreamLines(response, opts.signal, (line) => {
    const event = parseAgentSseLine(line);
    if (!event) return;
    if ('done' in event) return;
    if (event.type === 'done') terminal = true;
    if (event.type === 'error') {
      terminal = true;
      throw new Error(`Agent: ${event.error}`);
    }
    onEvent(event);
  });
  if (!terminal && !opts.signal?.aborted) throw new Error('Agent stream closed before a final result. You can retry safely.');
}

/** Approve or reject a pending dangerous agent action by its approval id. */
export async function approveAgentAction(sessionId: string, approvalId: string, approved: boolean): Promise<void> {
  await apiJson<{ ok: boolean }>(`${RAG_BASE}/v1/agent/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, approval_id: approvalId, approved }),
  });
}

export interface DirectoryEntry {
  name: string;
  path: string;
  readable: boolean;
}

export interface DirectoryListing {
  path: string;
  parent: string | null;
  home: string;
  directories: DirectoryEntry[];
}

/** List sub-directories of a host path so the user can pick the agent workspace. */
export async function browseDirectories(path?: string, signal?: AbortSignal): Promise<DirectoryListing> {
  const query = path ? `?path=${encodeURIComponent(path)}` : '';
  return apiJson<DirectoryListing>(`${RAG_BASE}/v1/agent/browse${query}`, {
    method: 'GET',
    headers: systemRequestHeaders(),
    signal,
  });
}
