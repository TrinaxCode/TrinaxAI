/* Voice service: Web Speech detection and backend fallback.
   Servicio de voz: detección de Web Speech y fallback al backend. */

import { RAG_BASE } from '../lib/api';

export interface VoiceCapabilities {
  stt: { available: boolean; engine: string; model: string | null };
  tts: { available: boolean; preferred: string | null; backends: string[] };
}

export function detectSpeechRecognition(): boolean {
  return typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition);
}

export function detectSpeechSynthesis(): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
  const voices = window.speechSynthesis.getVoices();
  return voices.length > 0;
}

export function detectBackendVoice(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.mediaDevices?.getUserMedia === 'function';
}

export async function getVoiceCapabilities(): Promise<VoiceCapabilities> {
  const res = await fetch(`${RAG_BASE}/voice/capabilities`);
  if (!res.ok) throw new Error('voiceCapabilitiesFailed');
  return res.json();
}

export async function transcribeAudio(blob: Blob, lang: string): Promise<string> {
  const form = new FormData();
  const ext = blob.type.includes('mp4') || blob.type.includes('m4a') ? 'mp4' : 'webm';
  form.append('file', blob, `recording.${ext}`);
  form.append('lang', lang.slice(0, 2));
  const res = await fetch(`${RAG_BASE}/voice/stt`, { method: 'POST', body: form });
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

export async function speakBackend({ text, lang, onEnded, onError }: BackendTTSOptions): Promise<HTMLAudioElement> {
  const res = await fetch(`${RAG_BASE}/voice/tts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, lang: lang.slice(0, 2) }),
  });
  if (!res.ok) throw new Error(`voiceTtsFailed:${res.status}`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.onended = () => {
    URL.revokeObjectURL(url);
    onEnded?.();
  };
  audio.onerror = () => {
    URL.revokeObjectURL(url);
    onError?.();
  };
  await audio.play();
  return audio;
}
