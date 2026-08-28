import { getUserSystemInstruction } from './userProfile';
import { systemFetch, systemRequestHeaders } from './authHeaders';
import { ApiError, apiErrorFromPayload, isCollectionEmptyMessage } from './api_errors';
import { OLLAMA_BASE, RAG_BASE } from './api_http';
import {
  ANALYTICAL_NUM_CTX,
  ANALYTICAL_NUM_PREDICT,
  MAX_CONTINUATIONS,
  TEXT_NUM_CTX,
  TEXT_NUM_PREDICT,
  VISION_NUM_CTX,
  VISION_NUM_PREDICT,
  aggressiveQuantizationEnabled,
  base64FromDataUrl,
  ensureOllamaModel,
  ollamaKeepAliveSetting,
  ollamaRuntimeOptions,
  resolveTextModel,
  resolveVisionModel,
  routeOllamaModel,
  shouldThinkForTurn,
  shouldUnloadAfterRequest,
  splitAnalyticalTask,
  analyticalQualityIssues,
  isAnalyticalReasoning,
  unloadOllamaModel,
} from './api_models';
import { recordUsage } from './api_usage';
import {
  conversationStylePrompt,
  isVoiceTurn,
  languageSystemPrompt,
  structurallyIncomplete,
  textMessagesForOllama,
  turnLanguage,
  visionSystemPrompt,
  voiceSystemPrompt,
} from './api_prompts';
import type { ResearchStreamMeta } from './api_research';
import type { ChatMessage, StreamMeta, StreamOptions, Source } from './api_types';

type LocalServiceErrorCode = 'ollama_unavailable' | 'rag_unavailable';

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

async function ollamaFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await systemFetch(input, init);
  } catch (error) {
    if (error instanceof ApiError || isAbortError(error)) throw error;
    throw new ApiError('', 503, 'ollama_unavailable');
  }
}

async function ragFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    if (error instanceof ApiError || isAbortError(error)) throw error;
    throw new ApiError('', 503, 'rag_unavailable');
  }
}

export async function readStreamLines(
  response: Response,
  signal: AbortSignal | undefined,
  onLine: (line: string) => void,
  unavailableCode?: LocalServiceErrorCode,
): Promise<void> {
  const reader = response.body?.getReader();
  if (!reader) {
    if (unavailableCode) throw new ApiError('', 503, unavailableCode);
    throw new Error('No response body');
  }
  const decoder = new TextDecoder();
  let pending = '';
  let completed = false;

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) {
        pending += decoder.decode();
        if (pending.trim()) onLine(pending);
        completed = true;
        break;
      }
      pending += decoder.decode(value, { stream: true });
      const lines = pending.split('\n');
      pending = lines.pop() ?? '';
      for (const line of lines) onLine(line);
    }
  } catch (error) {
    if (unavailableCode && !signal?.aborted && !(error instanceof ApiError) && !isAbortError(error)) {
      throw new ApiError('', 503, unavailableCode);
    }
    throw error;
  } finally {
    // Cancel unless the body was fully drained. This covers aborts *and* the
    // case where onLine() throws on a backend error frame — otherwise the HTTP
    // body would be left undrained, leaking the connection/stream.
    if (!completed) await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export function parseOllamaJsonLine(line: string): { token?: string; error?: string; thinking?: string; done?: boolean; doneReason?: string } {
  const trimmed = line.trim();
  if (!trimmed) return {};
  try {
    const parsed = JSON.parse(trimmed);
    const token = typeof parsed?.message?.content === 'string' ? parsed.message.content : '';
    if (typeof parsed?.error === 'string' && parsed.error.trim()) {
      return { error: parsed.error.trim() };
    }
    const out: { token?: string; thinking?: string; done?: boolean; doneReason?: string } = {};
    if (token) out.token = token;
    // qwen3-vl streams its reasoning in a separate `thinking` field. We don't
    // render it, but tracking it lets the caller detect a "thought the whole
    // budget away, produced no content" turn instead of showing a blank reply.
    if (typeof parsed?.message?.thinking === 'string' && parsed.message.thinking) {
      out.thinking = parsed.message.thinking;
    }
    if (parsed?.done) {
      if (typeof parsed?.done_reason === 'string') out.doneReason = parsed.done_reason;
      else out.done = true;
    }
    return out;
  } catch {
    return {};
  }
}

function appendOllamaJsonLine(line: string, onToken: (token: string) => void, onThinking?: (token: string) => void): string {
  const event = parseOllamaJsonLine(line);
  if (event.error) throw new ApiError('', 503, 'model_loading_failed');
  if (event.thinking) onThinking?.(event.thinking);
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
  if (typeof raw.error_code === 'string') meta.errorCode = raw.error_code;
  return meta;
}

function parseCompletionMeta(value: unknown): StreamMeta {
  if (!value || typeof value !== 'object') return {};
  const raw = value as Record<string, unknown>;
  const meta: StreamMeta = {};
  if (typeof raw.reason === 'string') meta.finishReason = raw.reason;
  if (typeof raw.status === 'string') meta.completionStatus = raw.status;
  if (typeof raw.can_continue === 'boolean') meta.canContinue = raw.can_continue;
  if (typeof raw.max_continuations === 'number') meta.maxContinuations = raw.max_continuations;
  if (typeof raw.continuation_count === 'number') meta.continuationCount = raw.continuation_count;
  return meta;
}

export function parseRagSseLine(line: string): {
  token?: string;
  thinking?: string;
  thinkingDurationMs?: number;
  meta?: StreamMeta;
  researchMeta?: ResearchStreamMeta;
  done?: boolean;
  error?: string;
} {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return {};
  const data = trimmed.slice(6);
  if (data === '[DONE]') return { done: true };
  try {
    const parsed = JSON.parse(data);
    if (typeof parsed.trinaxai_thinking === 'string' && parsed.trinaxai_thinking) {
      return { thinking: parsed.trinaxai_thinking };
    }
    if (parsed.trinaxai_timing && typeof parsed.trinaxai_timing === 'object') {
      const timing = parsed.trinaxai_timing as Record<string, unknown>;
      const meta: StreamMeta = {};
      if (typeof timing.total_ms === 'number') meta.totalMs = timing.total_ms;
      if (typeof timing.thinking_duration_ms === 'number') meta.thinkingDurationMs = timing.thinking_duration_ms;
      return Object.keys(meta).length ? { meta, thinkingDurationMs: meta.thinkingDurationMs } : {};
    }
    if (parsed.trinaxai_error && typeof parsed.trinaxai_error === 'object') {
      const failure = apiErrorFromPayload(503, { error: parsed.trinaxai_error });
      return { error: failure.message };
    }
    if (typeof parsed.trinaxai_error === 'string' && parsed.trinaxai_error.trim()) {
      return { error: apiErrorFromPayload(503, parsed.trinaxai_error).message };
    }
    if (parsed.trinaxai_finish) {
      const meta = parseCompletionMeta(parsed.trinaxai_finish);
      if (Object.prototype.hasOwnProperty.call(parsed, 'trinaxai_sources')) {
        return {
          meta: {
            ...meta,
            sources: parsed.trinaxai_sources as Source[],
            ...parseRetrievalMeta(parsed.trinaxai_retrieval),
          },
          ...(parsed.trinaxai_research ? { researchMeta: parsed.trinaxai_research as ResearchStreamMeta } : {}),
        };
      }
      return { meta };
    }
    if (parsed.trinaxai) {
      return { meta: parseRetrievalMeta(parsed.trinaxai) };
    }
    if (Object.prototype.hasOwnProperty.call(parsed, 'trinaxai_sources')) {
      return {
        meta: {
          sources: parsed.trinaxai_sources as Source[],
          ...parseRetrievalMeta(parsed.trinaxai_retrieval),
        },
        ...(parsed.trinaxai_research ? { researchMeta: parsed.trinaxai_research as ResearchStreamMeta } : {}),
      };
    }
    if (parsed.trinax_research || parsed.trinax_research_meta) {
      return { researchMeta: parsed.trinax_research || parsed.trinax_research_meta };
    }
    if (parsed.trinaxai_research) {
      return { researchMeta: parsed.trinaxai_research };
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
  let finalReason = 'stop';
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
        const response = await ollamaFetch(`${OLLAMA_BASE}/api/chat`, {
          method: 'POST',
          headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({
            model,
            messages: requestMessages,
            stream: true,
            think: options.thinking ?? shouldThinkForTurn(last),
            keep_alive: keepAlive,
            options: ollamaRuntimeOptions({
              num_ctx: analyticalTurn ? ANALYTICAL_NUM_CTX : TEXT_NUM_CTX,
              num_predict: analyticalTurn ? ANALYTICAL_NUM_PREDICT : TEXT_NUM_PREDICT,
              temperature: analyticalTurn ? 0.15 : 0.4,
              repeat_penalty: analyticalTurn ? 1.08 : 1.1,
            }, { preserveContext: analyticalTurn }),
          }),
          signal,
        });
        if (!response.ok) {
          const detail = await response.text().catch(() => '');
          throw apiErrorFromPayload(response.status, detail);
        }
        let generated = '';
        let doneReason: string | undefined;
        let sawDone = false;
        await readStreamLines(response, signal, (line) => {
          const parsed = parseOllamaJsonLine(line);
          if (parsed.done || parsed.doneReason) {
            doneReason = parsed.doneReason || 'stop';
            sawDone = true;
          }
          generated += appendOllamaJsonLine(
            line,
            analyticalTurn ? () => undefined : onToken,
            options.onThinking,
          );
        }, 'ollama_unavailable');
        if (!sawDone && !signal?.aborted) throw new ApiError('The model stream ended before completion.', 502, 'stream_incomplete');
        return { content: generated, finishReason: doneReason || (signal?.aborted ? 'cancelled' : 'stop') };
      };

      let attempt = await generateAttempt(baseRequestMessages);
      let batchContent = attempt.content;
      finalReason = attempt.finishReason;
      if (analyticalTurn && !signal?.aborted) {
        const issues = analyticalQualityIssues(batchContent, batches[batchIndex]);
        if (issues.length > 0) {
          attempt = await generateAttempt([
            ...baseRequestMessages,
            { role: 'assistant', content: batchContent },
            {
              role: 'user',
              content: `Reescribe todo el bloque desde cero y corrige estos problemas: ${issues.join('; ')}. Entrega únicamente la versión final limpia, completa y verificada.`,
            },
          ]);
          batchContent = attempt.content;
          finalReason = attempt.finishReason;
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
  if (signal?.aborted) finalReason = 'cancelled';
  const pending = finalReason === 'length' || structurallyIncomplete(fullContent);
  onMeta?.({
    finishReason: pending ? 'length' : finalReason,
    completionStatus: pending ? 'pending' : finalReason === 'stop' ? 'complete' : finalReason,
    canContinue: pending,
    maxContinuations: MAX_CONTINUATIONS,
  });
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
  const model = await resolveVisionModel(lastContent);
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

  const response = await ollamaFetch(`${OLLAMA_BASE}/api/chat`, {
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
      think: options.thinking ?? shouldThinkForTurn(lastContent),
      keep_alive: keepAlive,
      options: ollamaRuntimeOptions({
        num_ctx: VISION_NUM_CTX,
        num_predict: VISION_NUM_PREDICT,
      }, { preserveContext: true }),
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    const hint = /unexpected EOF|llama runner|model/i.test(detail)
      ? '\nEl modelo de visión local falló al cargar/procesar la imagen. Prueba con una captura más pequeña o una pregunta más concreta; el modelo se descargará de RAM automáticamente.'
      : '';
    throw apiErrorFromPayload(response.status, detail, hint ? 'model_loading_failed' : '');
  }

  let fullContent = '';
  let sawThinking = false;
  let doneReason: string | undefined;
  let sawDone = false;

  try {
    await readStreamLines(response, signal, (line) => {
      const event = parseOllamaJsonLine(line);
      if (event.error) throw new ApiError('', 503, 'model_loading_failed');
      if (event.thinking) options.onThinking?.(event.thinking);
      if (event.thinking) sawThinking = true;
      if (event.done || event.doneReason) {
        doneReason = event.doneReason || 'stop';
        sawDone = true;
      }
      if (event.token) {
        fullContent += event.token;
        onToken(event.token);
      }
    }, 'ollama_unavailable');
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

  if (!sawDone && !signal?.aborted) throw new ApiError('The vision stream ended before completion.', 502, 'stream_incomplete');

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
  const pending = doneReason === 'length' || structurallyIncomplete(fullContent);
  onMeta?.({
    finishReason: pending ? 'length' : doneReason || 'stop',
    completionStatus: pending ? 'pending' : 'complete',
    canContinue: pending,
    maxContinuations: MAX_CONTINUATIONS,
  });
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
  const model = await resolveVisionModel(prompt);
  await ensureOllamaModel(model, signal);
  const keepAlive = ollamaKeepAliveSetting();
  const instruction = lang === 'en'
    ? 'Describe this image in precise, concrete detail so another assistant can act on it. Transcribe any visible text or code verbatim. State only what is visible.'
    : 'Describe esta imagen con detalle preciso y concreto para que otro asistente pueda actuar sobre ella. Transcribe literalmente cualquier texto o código visible. Indica solo lo que se ve.';
  const userText = prompt.trim()
    ? (lang === 'en' ? `${instruction}\nThe user asks: ${prompt.trim()}` : `${instruction}\nEl usuario pregunta: ${prompt.trim()}`)
    : instruction;
  const response = await ollamaFetch(`${OLLAMA_BASE}/api/chat`, {
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
      }, { preserveContext: true }),
    }),
    signal,
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw apiErrorFromPayload(response.status, detail, 'model_loading_failed');
  }
  let out = '';
  let sawDone = false;
  try {
    await readStreamLines(response, signal, (line) => {
      const event = parseOllamaJsonLine(line);
      if (event.error) throw new ApiError('', 503, 'model_loading_failed');
      if (event.done || event.doneReason) sawDone = true;
      if (event.token) out += event.token;
    }, 'ollama_unavailable');
  } finally {
    if (shouldUnloadAfterRequest(keepAlive)) unloadOllamaModel(model);
  }
  if (!sawDone && !signal?.aborted) throw new ApiError('The image description stream ended before completion.', 502, 'stream_incomplete');
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
  const response = await ragFetch(`${RAG_BASE}/v1/chat/completions`, {
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
      mode: options.mode ?? 'knowledge',
      think: options.thinking ?? shouldThinkForTurn(lastUser),
    }),
    signal,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => '');
    throw apiErrorFromPayload(response.status, detail);
  }

  let fullContent = '';
  let sawDone = false;
  let sawFinish = false;
  let retrievalErrorCode = '';
  await readStreamLines(response, signal, (line) => {
    const event = parseRagSseLine(line);
    if (event.error) throw apiErrorFromPayload(503, event.error);
    if (event.meta) {
      sawFinish = sawFinish || typeof event.meta.finishReason === 'string';
      retrievalErrorCode ||= event.meta.errorCode || '';
      onMeta?.(event.meta);
    }
    if (event.done) sawDone = true;
    if (event.thinking) options.onThinking?.(event.thinking);
    if (event.thinkingDurationMs !== undefined) {
      options.onThinkingDuration?.(event.thinkingDurationMs);
    }
    if (event.token) {
      if (retrievalErrorCode === 'collection_empty' || (!fullContent && isCollectionEmptyMessage(event.token))) {
        throw apiErrorFromPayload(424, { detail: { code: 'collection_empty' } });
      }
      fullContent += event.token;
      onToken(event.token);
    }
  }, 'rag_unavailable');
  if (!sawDone && !signal?.aborted) throw new ApiError('The RAG stream ended before completion.', 502, 'stream_incomplete');
  if (!sawFinish) {
    const pending = structurallyIncomplete(fullContent);
    onMeta?.({
      finishReason: pending ? 'length' : signal?.aborted ? 'cancelled' : 'stop',
      completionStatus: pending ? 'pending' : signal?.aborted ? 'cancelled' : 'complete',
      canContinue: pending,
      maxContinuations: MAX_CONTINUATIONS,
    });
  }
  return fullContent;
}
