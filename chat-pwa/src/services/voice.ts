/* Voice service: Web Speech detection and backend fallback.
   Servicio de voz: detección de Web Speech y fallback al backend. */

import { RAG_BASE } from '../lib/api';
import { systemRequestHeaders } from '../lib/authHeaders';

export interface VoiceCapabilities {
  stt: { available: boolean; engine: string; model: string | null };
  tts: { available: boolean; preferred: string | null; backends: string[] };
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
  return res.json();
}

export async function transcribeAudio(blob: Blob, lang: string, signal?: AbortSignal): Promise<string> {
  const form = new FormData();
  const ext = blob.type.includes('mp4') || blob.type.includes('m4a') ? 'mp4' : 'webm';
  form.append('file', blob, `recording.${ext}`);
  form.append('lang', lang.slice(0, 2));
  const res = await fetchWithTimeout(`${RAG_BASE}/v1/voice/stt`, { method: 'POST', headers: systemRequestHeaders(), body: form, signal }, 60_000);
  if (!res.ok) throw new Error(`voiceSttFailed:${res.status}`);
  const data = await res.json();
  return data.text as string;
}

export interface BackendTTSOptions {
  text: string;
  lang: string;
  onEnded?: () => void;
  onError?: () => void;
}

let activeBackendAudio: HTMLAudioElement | null = null;
let activeBackendAudioUrl: string | null = null;

export function stopBackendSpeech(): void {
  activeBackendAudio?.pause();
  activeBackendAudio?.removeAttribute('src');
  if (activeBackendAudioUrl) URL.revokeObjectURL(activeBackendAudioUrl);
  activeBackendAudio = null;
  activeBackendAudioUrl = null;
}

export async function speakBackend({ text, lang, onEnded, onError }: BackendTTSOptions): Promise<HTMLAudioElement> {
  stopBackendSpeech();
  const res = await fetchWithTimeout(`${RAG_BASE}/v1/voice/tts`, {
    method: 'POST',
    headers: systemRequestHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ text, lang: lang.slice(0, 2) }),
  }, 60_000);
  if (!res.ok) throw new Error(`voiceTtsFailed:${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  activeBackendAudio = audio;
  activeBackendAudioUrl = url;
  const release = () => {
    if (activeBackendAudio !== audio) return;
    URL.revokeObjectURL(url);
    activeBackendAudio = null;
    activeBackendAudioUrl = null;
  };
  audio.onended = () => {
    release();
    onEnded?.();
  };
  audio.onerror = () => {
    release();
    onError?.();
  };
  try {
    await audio.play();
  } catch (err) {
    // Autoplay policy / no user gesture: revoke the URL we just created,
    // otherwise every blocked attempt leaks a blob URL.
    release();
    throw err;
  }
  return audio;
}
