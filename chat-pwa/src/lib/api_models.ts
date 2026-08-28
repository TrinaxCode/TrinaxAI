import { systemFetch, systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload } from './api_errors';
import { OLLAMA_BASE, RAG_BASE } from './api_http';
import { thinkingModeEnabled } from './api_types';
import type { ChatMessage } from './api_types';

/** Specialized model for OCR, screenshots and image analysis. */
const VISION_MODEL = import.meta.env.VITE_TRINAXAI_VISION_MODEL || 'qwen3.5:4b';
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
export type ModelPreset = '8gb' | '16gb' | '32gb' | '64gb';
export const MODEL_PRESETS: Record<ModelPreset, Record<ModelSettingKey, string>> = {
  '8gb': {
    'tc-models-chat': 'qwen3.5:2b',
    'tc-models-deep': 'qwen3.5:2b',
    'tc-models-vision': 'qwen3.5:2b',
    'tc-models-embed': 'qwen3-embedding:0.6b',
    'tc-models-code': 'qwen3.5:2b',
    'tc-models-fast': 'qwen3.5:2b',
  },
  '16gb': {
    'tc-models-chat': 'qwen3.5:4b',
    'tc-models-deep': 'qwen3.5:4b',
    'tc-models-vision': 'qwen3.5:4b',
    'tc-models-embed': 'qwen3-embedding:0.6b',
    'tc-models-code': 'qwen3.5:4b',
    'tc-models-fast': 'qwen3.5:2b',
  },
  '32gb': {
    'tc-models-chat': 'qwen3.5:9b',
    'tc-models-deep': 'qwen3.5:9b',
    'tc-models-vision': 'qwen3.5:9b',
    'tc-models-embed': 'qwen3-embedding:4b',
    'tc-models-code': 'qwen3.5:9b',
    'tc-models-fast': 'qwen3.5:4b',
  },
  '64gb': {
    'tc-models-chat': 'qwen3.5:35b',
    'tc-models-deep': 'qwen3.5:35b',
    'tc-models-vision': 'qwen3.5:35b',
    'tc-models-embed': 'qwen3-embedding:4b',
    'tc-models-code': 'qwen3-coder:30b',
    'tc-models-fast': 'qwen3.5:4b',
  },
};
export const DEFAULT_MODEL_SETTINGS = MODEL_PRESETS['16gb'];
const MANAGED_MODELS_KEY = 'tc-managed-ollama-models';
const OLLAMA_PULL_TIMEOUT_MS = 30 * 60 * 1000;

type OllamaPullEvent = {
  status?: string;
  error?: string;
  completed?: number;
  total?: number;
};

function pullSignal(signal?: AbortSignal): AbortSignal {
  const timeout = AbortSignal.timeout(OLLAMA_PULL_TIMEOUT_MS);
  return signal ? AbortSignal.any([signal, timeout]) : timeout;
}
/** Consume Ollama's NDJSON pull stream so the server can finish the download. */
async function pullOllamaModel(
  model: string,
  onProgress?: (model: string, completed: number, total: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await systemFetch(`${OLLAMA_BASE}/api/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/x-ndjson' },
    body: JSON.stringify({ model, stream: true }),
    signal: pullSignal(signal),
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw apiErrorFromPayload(response.status, detail, 'model_unavailable');
  }
  if (!response.body) throw new ApiError(`Could not read pull progress for ${model}`, 502);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let sawSuccess = false;
  const consume = (line: string) => {
    if (!line.trim()) return;
    let event: OllamaPullEvent;
    try { event = JSON.parse(line) as OllamaPullEvent; } catch { return; }
    if (event.error) throw new ApiError(event.error, 502, 'model_loading_failed');
    if (event.status === 'success') sawSuccess = true;
    if (typeof event.completed === 'number' && typeof event.total === 'number') {
      onProgress?.(model, event.completed, event.total);
    }
  };

  let completed = false;
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() || '';
      lines.forEach(consume);
      if (done) {
        completed = true;
        break;
      }
    }
    buffer += decoder.decode();
    consume(buffer.trim());
    if (!sawSuccess) throw new ApiError('The model download ended before completion.', 502, 'stream_incomplete');
  } finally {
    if (!completed) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

/** Reconcile only models previously installed through TrinaxAI's explicit button. */
export async function reconcileManagedModels(
  models: string[],
  onProgress?: (model: string, completed: number, total: number) => void,
  signal?: AbortSignal,
): Promise<void> {
  const desired = new Set(models.map((model) => model.trim()).filter(Boolean));
  let managed = new Set<string>();
  try {
    const stored = JSON.parse(localStorage.getItem(MANAGED_MODELS_KEY) || '[]');
    if (Array.isArray(stored)) managed = new Set(stored.filter((item): item is string => typeof item === 'string'));
  } catch { /* corrupt local ownership metadata means delete nothing */ }

  const persist = () => localStorage.setItem(MANAGED_MODELS_KEY, JSON.stringify([...managed].sort()));
  for (const model of [...managed].filter((item) => !desired.has(item))) {
    const response = await systemFetch(`${OLLAMA_BASE}/api/delete`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
      signal,
    });
    if (!response.ok && response.status !== 404) throw new ApiError(`Could not remove ${model}`, response.status);
    managed.delete(model);
    persist();
  }
  for (const model of desired) {
    await pullOllamaModel(model, onProgress, signal);
    managed.add(model);
    persist();
  }
}
export const TEXT_NUM_CTX = 8192;
export const ANALYTICAL_NUM_CTX = 12288;
export const TEXT_NUM_PREDICT = 2048;
export const ANALYTICAL_NUM_PREDICT = 4096;
export const VISION_NUM_CTX = 8192;
export const VISION_NUM_PREDICT = 2560;
const VISION_IMAGE_MAX_SIDE = 768;
const VISION_IMAGE_QUALITY = 0.74;
export const MAX_VISION_IMAGE_BYTES = 32 * 1024 * 1024;
// Room for long exam prompts; matches the raised text window (num_ctx=8192).
// Kept as a safety cap only so a runaway history can't blow the model window,
// well above any single question.
export const DIRECT_CHAT_CONTEXT_CHARS = 24_000;
const configuredMaxContinuations = Number(import.meta.env.VITE_TRINAXAI_MAX_CONTINUATIONS || 2);
export const MAX_CONTINUATIONS = Number.isFinite(configuredMaxContinuations)
  ? Math.max(0, Math.min(8, configuredMaxContinuations))
  : 2;
let ollamaModelCache: string[] | null = null;
let ollamaModelCapabilities = new Map<string, Set<string>>();
let ollamaModelCacheAt = 0;
let lastResolvedTextModel: { model: string; at: number; role: 'code' | 'text' } | null = null;
const ollamaPullsInFlight = new Map<string, Promise<void>>();
const MODEL_CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes
export const INDEXABLE_EXTENSIONS = new Set([
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
export const INDEXABLE_FILENAMES = new Set([
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
  'quién te creó', 'quien te creo', 'qué eres', 'que eres',
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
    if (localStorage.getItem('tc-model-defaults-v6') !== '1') {
      const obsolete = new Set([
        'granite4:3b', 'llama3.2:3b', 'qwen2.5vl:3b',
        'qwen2.5-coder:1.5b', 'qwen2.5-coder:3b',
        'qwen2.5-coder:14b', 'bge-m3', 'qwen3-vl:2b-instruct',
        'qwen3-vl:4b-instruct', 'qwen3-vl:8b-instruct',
        'qwen3-vl:30b-a3b-instruct', 'qwen3.5:27b', 'qwen3.5:35b-a3b', 'qwen3.5:0.8b',
      ]);
      for (const modelKey of MODEL_KEYS) {
        const current = localStorage.getItem(modelKey)?.trim();
        if (!current || obsolete.has(current) || (modelKey === 'tc-models-chat' && current === 'qwen3.5:2b')) {
          localStorage.setItem(modelKey, DEFAULT_MODEL_SETTINGS[modelKey]);
        }
      }
      localStorage.setItem('tc-model-defaults-v6', '1');
    }
    const value = localStorage.getItem(key)?.trim() || fallback;
    // Migrate defaults that were removed after the local Qwen3.5 benchmark.
    // This prevents stale shared/local state from routing chat to a deleted
    // model (and then incorrectly falling back to a coder model).
    if (key === 'tc-models-chat' && value === 'qwen3:4b-instruct-2507-q4_K_M') return 'qwen3.5:4b';
    if (key === 'tc-models-fast' && value === 'qwen3:4b-instruct-2507-q4_K_M') return DEFAULT_MODEL_SETTINGS[key];
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

export function ollamaRuntimeOptions<T extends Record<string, number>>(
  base: T,
  opts: { preserveContext?: boolean } = {},
): T & { num_gpu?: number } {
  const options: T & { num_gpu?: number } = { ...base };
  if (aggressiveQuantizationEnabled()) {
    options.num_gpu = 0;
    const runtime = options as Record<string, number>;
    // Don't shrink the window for vision: image tokens need the room
    // need the room, and clipping num_ctx to 2048 makes the answer come back
    // empty. Text turns can still be trimmed to save RAM.
    if (!opts.preserveContext && typeof runtime.num_ctx === 'number') {
      runtime.num_ctx = Math.min(runtime.num_ctx, 2048);
    }
  }
  return options;
}

export function shouldUnloadAfterRequest(keepAlive: string | number): boolean {
  if (typeof keepAlive === 'number') return keepAlive <= 0;
  return /^0(?:s|m|h)?$/i.test(keepAlive.trim());
}

/** True for maths/exam/theory work even when the prompt embeds source code. */
export function isAnalyticalReasoning(text: string): boolean {
  const t = (text || '').toLowerCase();
  const hits = REASONING_HINTS.reduce((count, hint) => count + (t.includes(hint) ? 1 : 0), 0);
  return hits >= 3 || ((t.includes('examen') || t.includes('problem set')) && hits >= 2);
}

const REASONING_ACTION_RE = /\b(?:demuestra|demostrar|demostración|demostracion|prueba|probar|prove|proof|resuelve|resolver|calcula|calcular|deriva|derivar|analiza|analizar|determina|determinar|compara|compare|paso a paso|step by step|a fondo|exhaustivo|thorough)\b/i;
const EXPLANATION_ONLY_RE = /^\s*[¿?]?\s*(?:qué es|que es|qué son|que son|cómo funciona|como funciona|what is|what are|how does|how do)\b/i;
const COMPLEX_CODE_RE = /\b(?:implementa|implement|crea|create|construye|build|refactoriza|refactor|depura|debug)\b[\s\S]{0,120}\b(?:tests?|pruebas?|benchmark|varios archivos|multiple files|completo|complete)\b/i;

/** User preference enables deep reasoning, while routing decides when it is useful. */
export function shouldThinkForTurn(text: string, enabled = thinkingModeEnabled()): boolean {
  if (!enabled) return false;
  const current = (text || '').toLocaleLowerCase();
  const analytical = isAnalyticalReasoning(current);
  const formalAction = REASONING_ACTION_RE.test(current);
  return (analytical && !EXPLANATION_ONLY_RE.test(current))
    || (formalAction && !EXPLANATION_ONLY_RE.test(current))
    || COMPLEX_CODE_RE.test(current);
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
    : GENERAL_TOPIC_HINTS.some((h) => t.includes(h))
      ? chatModel
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
  await availableOllamaModels();
  const supportsAgentTools = (model: string) => !/^qwen2\.5-coder:/i.test(model)
    && (ollamaModelCapabilities.get(model)?.has('tools')
      || ollamaModelCapabilities.get(`${model}:latest`)?.has('tools'));
  if (supportsAgentTools(candidate)) {
    console.info(`[TrinaxAI router] selected ${candidate}: installed model supports reliable Agent tools`);
    return candidate;
  }
  for (const fallback of [DEFAULT_MODEL_SETTINGS['tc-models-chat'], chatModel, fastModel]) {
    if (supportsAgentTools(fallback)) {
      console.info(`[TrinaxAI router] selected ${fallback}: ${candidate} is unreliable for Agent tools`);
      return fallback;
    }
  }
  throw new ApiError(`No installed model supports reliable Agent tools (requested: ${candidate}; code model: ${codeModel}).`, 424, 'model_incompatible');
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
    await pullOllamaModel(model, undefined, signal);
    ollamaModelCache = null;
  })();
  ollamaPullsInFlight.set(model, pull);
  try {
    await pull;
  } finally {
    ollamaPullsInFlight.delete(model);
  }
}

export async function resolveVisionModel(_text: string): Promise<string> {
  // Vision is latency-sensitive and only runs for attached images. Respect the
  // configured lightweight model even when an older, much larger VL model is
  // already installed; ensureOllamaModel downloads it on first use.
  const configured = modelSetting('tc-models-vision', VISION_MODEL);
  const models = await availableOllamaModels();
  if (!models.length || hasModel(models, configured)) return configured;
  // qwen3.5:2b is a valid vision model for the 16 GB fleet. Prefer it over an
  // error when the larger configured model was removed or is still downloading.
  const fallback = [DEFAULT_MODEL_SETTINGS['tc-models-fast'], 'qwen3.5:2b']
    .find((candidate) => hasModel(models, candidate)
      && (ollamaModelCapabilities.get(candidate)?.has('vision') || ollamaModelCapabilities.get(`${candidate}:latest`)?.has('vision')));
  return fallback || configured;
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
  if (file.size > MAX_VISION_IMAGE_BYTES) {
    throw new Error('La imagen es demasiado grande para procesarla en el navegador.');
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

export function base64FromDataUrl(dataUrl: string): string {
  const marker = ';base64,';
  const idx = dataUrl.indexOf(marker);
  return idx >= 0 ? dataUrl.slice(idx + marker.length) : dataUrl;
}

export function unloadOllamaModel(model?: string): void {
  if (!model) return;
  void systemFetch(`${OLLAMA_BASE}/api/generate`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ model, keep_alive: 0 }),
    keepalive: true,
  }).catch(() => undefined);
}

/** Estado de los servicios y del perfil real para los indicadores de la PWA. */
export async function checkStatus(): Promise<{
  ollama: boolean;
  rag: boolean;
  indexed: boolean;
  ramPercent: number | null;
  profile: ModelPreset | null;
}> {
  const out = { ollama: false, rag: false, indexed: false, ramPercent: null as number | null, profile: null as ModelPreset | null };
  try {
    const r = await fetch(`${RAG_BASE}/health`, { cache: 'no-store', signal: AbortSignal.timeout(3000) });
    if (r.ok) {
      out.rag = true;
      const d = await r.json();
      out.indexed = !!d.indexed;
      out.ollama = typeof d?.ollama === 'boolean' ? d.ollama : false;
      const profile = typeof d?.profile === 'string' ? d.profile : '';
      if (Object.prototype.hasOwnProperty.call(MODEL_PRESETS, profile)) out.profile = profile as ModelPreset;
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
