/* Voice service: Web Speech detection and backend fallback.
   Servicio de voz: detección de Web Speech y fallback al backend. */

import { RAG_BASE } from '../lib/api';
import { systemRequestHeaders } from '../lib/authHeaders';

export interface VoiceCapabilities {
  stt: { available: boolean; engine: string; model: string | null };
  tts: { available: boolean; preferred: string | null; backends: string[] };
}

export interface SpeechChunk {
  chunk: string;
  remainder: string;
}

export function takeSpeechChunk(text: string, force = false): SpeechChunk {
  const normalized = text.replace(/\s+/g, ' ').trimStart();
  if (!normalized.trim()) return { chunk: '', remainder: '' };
  if (force) return { chunk: normalized.trim(), remainder: '' };

  const sentence = /[.!?](?:["'”»)]*)?(?=\s|$)/g;
  let match: RegExpExecArray | null;
  while ((match = sentence.exec(normalized))) {
    const end = match.index + match[0].length;
    if (end >= 12) return { chunk: normalized.slice(0, end).trim(), remainder: normalized.slice(end).trimStart() };
  }

  if (normalized.length < 48) return { chunk: '', remainder: normalized };
  const limit = Math.min(normalized.length, 88);
  const cut = normalized.lastIndexOf(' ', limit);
  if (cut < 24) return { chunk: '', remainder: normalized };
  return { chunk: normalized.slice(0, cut).trim(), remainder: normalized.slice(cut).trimStart() };
}

export function detectSpeechRecognition(): boolean {
  return typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function detectSpeechSynthesis(): boolean {
  // Feature-detect the API itself. getVoices() is frequently empty on the first
  // call (voices load asynchronously via the 'voiceschanged' event), so gating
  // on voices.length here would spuriously fall back to backend TTS on cold load.
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

export function detectBackendVoice(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.mediaDevices?.getUserMedia === 'function';
}

// ponytail: fixed retry cap; add backoff/telemetry only if deployment data justifies it.
export const MAX_BACKEND_VOICE_RETRIES = 3;

export function shouldStopBackendVoice(retries: number): boolean {
  return retries >= MAX_BACKEND_VOICE_RETRIES;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const onAbort = () => controller.abort(init.signal?.reason);
  if (init.signal?.aborted) controller.abort(init.signal.reason);
  else init.signal?.addEventListener('abort', onAbort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(new DOMException('Request timed out', 'TimeoutError')), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener('abort', onAbort);
  }
}

export async function getVoiceCapabilities(): Promise<VoiceCapabilities> {
  const res = await fetchWithTimeout(`${RAG_BASE}/v1/voice/capabilities`, { headers: systemRequestHeaders() }, 8000);
  if (!res.ok) throw new Error('voiceCapabilitiesFailed');
  const data: unknown = await res.json().catch(() => null);
  const stt = isRecord(data) && isRecord(data.stt) ? data.stt : null;
  const tts = isRecord(data) && isRecord(data.tts) ? data.tts : null;
  const validModel = (value: unknown): value is string | null => value === null || typeof value === 'string';
  if (!stt || typeof stt.available !== 'boolean' || typeof stt.engine !== 'string' || !validModel(stt.model)
    || !tts || typeof tts.available !== 'boolean' || !validModel(tts.preferred)
    || !Array.isArray(tts.backends) || !tts.backends.every((backend) => typeof backend === 'string')) {
    throw new Error('voiceCapabilitiesInvalid');
  }
  return {
    stt: { available: stt.available, engine: stt.engine, model: stt.model },
    tts: { available: tts.available, preferred: tts.preferred, backends: tts.backends },
  };
}

export async function transcribeAudio(blob: Blob, lang: string, signal?: AbortSignal): Promise<string> {
  const form = new FormData();
  const ext = blob.type.includes('mp4') || blob.type.includes('m4a')
    ? 'mp4'
    : blob.type.includes('ogg')
      ? 'ogg'
      : blob.type.includes('wav')
        ? 'wav'
        : 'webm';
  form.append('file', blob, `recording.${ext}`);
  form.append('lang', lang.slice(0, 2));
  const res = await fetchWithTimeout(`${RAG_BASE}/v1/voice/stt`, { method: 'POST', headers: systemRequestHeaders(), body: form, signal }, 60_000);
  if (!res.ok) throw new Error(`voiceSttFailed:${res.status}`);
  const data: unknown = await res.json().catch(() => null);
  if (!isRecord(data) || typeof data.text !== 'string') throw new Error('voiceSttInvalidResponse');
  return data.text;
}

export interface BackendTTSOptions {
  text: string;
  lang: string;
  onEnded?: () => void;
  onError?: () => void;
}

let activeBackendAudio: HTMLAudioElement | null = null;
let activeBackendAudioUrl: string | null = null;
let activeBackendRequest: AbortController | null = null;
let backendSpeechGeneration = 0;

export function stopBackendSpeech(): void {
  activeBackendRequest?.abort();
  activeBackendRequest = null;
  backendSpeechGeneration += 1;
  activeBackendAudio?.pause();
  activeBackendAudio?.removeAttribute('src');
  if (activeBackendAudioUrl) URL.revokeObjectURL(activeBackendAudioUrl);
  activeBackendAudio = null;
  activeBackendAudioUrl = null;
}

export async function speakBackend({ text, lang, onEnded, onError }: BackendTTSOptions): Promise<HTMLAudioElement> {
  stopBackendSpeech();
  const requestController = new AbortController();
  const generation = backendSpeechGeneration;
  activeBackendRequest = requestController;
  try {
    const res = await fetchWithTimeout(`${RAG_BASE}/v1/voice/tts`, {
      method: 'POST',
      headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ text, lang: lang.slice(0, 2) }),
      signal: requestController.signal,
    }, 60_000);
    if (generation !== backendSpeechGeneration || requestController.signal.aborted) {
      throw new DOMException('Speech request aborted', 'AbortError');
    }
    if (!res.ok) throw new Error(`voiceTtsFailed:${res.status}`);
    const blob = await res.blob();
    if (generation !== backendSpeechGeneration || requestController.signal.aborted) {
      throw new DOMException('Speech request aborted', 'AbortError');
    }
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    activeBackendAudio = audio;
    activeBackendAudioUrl = url;
    const release = () => {
      if (activeBackendAudio !== audio) return false;
      URL.revokeObjectURL(url);
      activeBackendAudio = null;
      activeBackendAudioUrl = null;
      return true;
    };
    audio.onended = () => {
      if (release()) onEnded?.();
    };
    audio.onerror = () => {
      if (release()) onError?.();
    };
    try {
      await audio.play();
    } catch (err) {
      // Autoplay policy / no user gesture: revoke the URL we just created,
      // otherwise every blocked attempt leaks a blob URL.
      release();
      throw err;
    }
    if (generation !== backendSpeechGeneration || requestController.signal.aborted) {
      release();
      throw new DOMException('Speech request aborted', 'AbortError');
    }
    return audio;
  } finally {
    if (activeBackendRequest === requestController) activeBackendRequest = null;
  }
}
