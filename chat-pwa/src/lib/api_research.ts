import { systemFetch, systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload } from './api_errors';
import { OLLAMA_BASE, RAG_BASE, apiJson } from './api_http';
import {
  DEFAULT_MODEL_SETTINGS,
  aggressiveQuantizationEnabled,
  modelSetting,
  ollamaKeepAliveSetting,
} from './api_models';
import { detectTurnLanguage } from './api_prompts';
import { parseRagSseLine, readStreamLines } from './api_streams';
import { thinkingModeEnabled } from './api_types';
import type { ChatMessage, Source, StreamMeta } from './api_types';

async function researchFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof ApiError || (error instanceof DOMException && error.name === 'AbortError')) throw error;
    throw new ApiError('', 503, 'rag_unavailable');
  }
}

export interface ResearchResult {
  answer: string;
  sub_questions: string[];
  sources: Source[];
  passes: number;
  model: string;
  web_search?: boolean;
  web_provider?: string | null;
  search_query?: string | null;
  degraded?: boolean;
  error_code?: 'web_search_unavailable' | string;
  error_detail?: string;
  failure_reason?: string;
  failure_message?: string;
  finish_reason?: string;
  completion_status?: string;
}

export interface ResearchStreamMeta {
  degraded?: boolean;
  error_code?: string;
  error_detail?: string;
  failure_reason?: string;
  failure_message?: string;
  web_search?: boolean;
  web_provider?: string | null;
  search_query?: string | null;
  passes?: number;
  sub_questions?: string[];
  finishReason?: string;
  completionStatus?: string;
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
    onToken?: (token: string, fullText: string) => void;
    thinking?: boolean;
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
    think: opts.thinking ?? thinkingModeEnabled(),
  };
  const timeoutSignal = AbortSignal.timeout(15 * 60_000);
  const signal = opts.signal ? AbortSignal.any([opts.signal, timeoutSignal]) : timeoutSignal;
  let preflight: { ok: boolean; model?: string; error_code?: string; error_detail?: string } | undefined;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      preflight = await apiJson(`${RAG_BASE}/v1/research/preflight`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload), signal,
      });
      break;
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        throw new ApiError(
          'El servicio RAG activo pertenece a una versión anterior y no incluye Search Mode. Reinicia TrinaxAI para cargar el backend actual.',
          503,
          'rag_version_mismatch',
        );
      }
      if (attempt || !(error instanceof ApiError) || error.status !== 0) {
        if (opts.signal?.aborted) throw new DOMException('Research request cancelled.', 'AbortError');
        if (timeoutSignal.aborted) throw new ApiError('Research dependency check timed out.', 408, 'timeout');
        if (error instanceof ApiError && error.status === 0) {
          let ollamaReachable: boolean;
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
      collection_not_found: `The selected RAG collection was not found: ${detail}`,
      web_search_disabled: 'Web search is disabled in the server configuration.',
    };
    throw new ApiError(messages[code] || detail || 'Research preflight failed.', 424, code);
  }
  payload.model = preflight.model || payload.model;
  try {
    if (!opts.onToken) {
      const result = await apiJson<ResearchResult>(`${RAG_BASE}/v1/research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal,
      });
      if (result.error_code && result.error_code !== 'web_search_unavailable') {
        throw new ApiError(result.error_detail || result.answer, 503, result.error_code);
      }
      return result;
    }

    const response = await researchFetch(`${RAG_BASE}/v1/research`, {
      method: 'POST',
      headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ ...payload, stream: true }),
      signal,
    });
    if (!response.ok) {
      const detail = await response.text().catch(() => '');
      throw apiErrorFromPayload(response.status, detail);
    }
    let answer = '';
    let sources: Source[] = [];
    let researchMeta: ResearchStreamMeta = {};
    let completionMeta: StreamMeta = {};
    let sawDone = false;
    const selectedModel = String(payload.model || '');
    await readStreamLines(response, signal, (line) => {
      const event = parseRagSseLine(line);
      if (event.error) throw new ApiError(event.error, 503);
      if (event.done) sawDone = true;
      if (event.meta) completionMeta = { ...completionMeta, ...event.meta };
      if (event.token) {
        answer += event.token;
        opts.onToken?.(event.token, answer);
      }
      if (event.meta?.sources) sources = event.meta.sources;
      if (event.researchMeta) researchMeta = { ...researchMeta, ...event.researchMeta };
    }, 'rag_unavailable');
    if (!sawDone && !signal?.aborted) throw new ApiError('The research stream ended before completion.', 502, 'stream_incomplete');
    const result: ResearchResult = {
      answer: answer.trim(),
      sub_questions: researchMeta.sub_questions || [],
      sources,
      passes: researchMeta.passes || 0,
      model: selectedModel,
      web_search: researchMeta.web_search,
      web_provider: researchMeta.web_provider,
      search_query: researchMeta.search_query || payload.search_query || null,
      degraded: researchMeta.degraded,
      error_code: researchMeta.error_code,
      error_detail: researchMeta.error_detail,
      failure_reason: researchMeta.failure_reason,
      failure_message: researchMeta.failure_message,
      finish_reason: completionMeta.finishReason,
      completion_status: completionMeta.completionStatus,
    };
    if (result.error_code && result.error_code !== 'web_search_unavailable') {
      throw new ApiError(result.answer, 503, result.error_code);
    }
    return result;
  } catch (error) {

    if (opts.signal?.aborted) throw new DOMException('Research request cancelled.', 'AbortError');
    if (timeoutSignal.aborted) throw new ApiError('Research request timed out after 15 minutes.', 408, 'timeout');
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
    .map((text) => text.replace(/^\s*(?:busca(?:r)?|consulta|investiga|verifica|search(?:\s+for)?|look\s+up|check)\s+(?:(?:en\s+)?(?:internet|la\s+web|online)\s+)?/i, ''))
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
