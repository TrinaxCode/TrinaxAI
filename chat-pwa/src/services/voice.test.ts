import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  cleanSpeechText,
  detectBackendVoice,
  detectSpeechRecognition,
  getVoiceCapabilities,
  pickBestVoice,
  scoreVoice,
  shouldStopBackendVoice,
  speakBackend,
  stopBackendSpeech,
  takeSpeechChunk,
  transcribeAudio,
} from './voice';

describe('speech chunking', () => {
  it('releases a sentence before the model stream ends', () => {
    expect(takeSpeechChunk('Hola, esta es la primera frase. Y todavía sigo generando')).toEqual({
      chunk: 'Hola, esta es la primera frase.',
      remainder: 'Y todavía sigo generando',
    });
  });

  it('uses a short word boundary when there is no punctuation yet', () => {
    const text = 'Esta respuesta sigue llegando desde el modelo y necesita comenzar a reproducirse antes del final';
    const result = takeSpeechChunk(text);
    expect(result.chunk.length).toBeGreaterThanOrEqual(24);
    expect(result.chunk.endsWith(' ')).toBe(false);
    expect(result.remainder.startsWith(' ')).toBe(false);
    expect(`${result.chunk} ${result.remainder}`).toContain(text.slice(0, 40));
  });

  it('flushes the final incomplete fragment on force', () => {
    expect(takeSpeechChunk('fragmento final sin punto', true)).toEqual({
      chunk: 'fragmento final sin punto',
      remainder: '',
    });
  });
});

describe('voice API routes', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('uses the versioned capabilities endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      stt: { available: true, engine: 'whisper', model: 'local' },
      tts: { available: false, preferred: null, backends: [] },
    }), { status: 200 }));

    await getVoiceCapabilities();

    expect(fetchMock.mock.calls[0]?.[0]).toEqual(
      expect.stringMatching(/\/v1\/voice\/capabilities$/),
    );
    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe('include');
  });

  it('rejects failed capabilities responses instead of accepting an HTTP error body', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 503 }));

    await expect(getVoiceCapabilities()).rejects.toThrow('voiceCapabilitiesFailed');
  });

  it('rejects malformed capabilities payloads instead of trusting an HTTP 200', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ stt: { available: true } }), { status: 200 }));

    await expect(getVoiceCapabilities()).rejects.toThrow('voiceCapabilitiesInvalid');
  });

  it('aborts a capabilities request when the timeout expires', async () => {
    vi.useFakeTimers();
    try {
      const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true });
      }));
      const request = getVoiceCapabilities();
      const rejection = expect(request).rejects.toMatchObject({ name: 'TimeoutError' });

      await vi.advanceTimersByTimeAsync(8_000);

      await rejection;
      expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ['audio/webm', 'webm'],
    ['audio/mp4', 'mp4'],
    ['audio/m4a', 'mp4'],
    ['audio/ogg', 'ogg'],
    ['audio/wav', 'wav'],
    ['audio/flac', 'webm'],
  ])('uses a stable upload filename for %s', async (mimeType, extension) => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ text: 'hola' }), { status: 200 }));

    await transcribeAudio(new Blob(['audio'], { type: mimeType }), 'es-MX');

    expect(fetchMock.mock.calls[0]?.[0]).toEqual(expect.stringMatching(/\/v1\/voice\/stt$/));
    expect(fetchMock.mock.calls[0]?.[1]?.credentials).toBe('include');
    const form = fetchMock.mock.calls[0]?.[1]?.body as FormData;
    expect(form.get('file')).toMatchObject({ name: `recording.${extension}` });
    expect(form.get('lang')).toBe('es');
  });

  it('rejects failed transcription responses with the HTTP status', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(null, { status: 502 }));

    await expect(transcribeAudio(new Blob(['audio'], { type: 'audio/webm' }), 'en-US'))
      .rejects.toThrow('voiceSttFailed:502');
  });

  it('rejects malformed transcription payloads instead of turning them into empty speech', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));

    await expect(transcribeAudio(new Blob(['audio'], { type: 'audio/webm' }), 'en-US'))
      .rejects.toThrow('voiceSttInvalidResponse');
  });

  it('propagates caller cancellation to the transcription request', async () => {
    const controller = new AbortController();
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener('abort', () => reject(init.signal?.reason), { once: true });
    }));
    const request = transcribeAudio(new Blob(['audio'], { type: 'audio/webm' }), 'en-US', controller.signal);

    controller.abort();

    await expect(request).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetchMock.mock.calls[0]?.[1]?.signal?.aborted).toBe(true);
  });

  it('keeps backend voice available when Web Speech is unavailable', () => {
    const speechDescriptor = Object.getOwnPropertyDescriptor(window, 'SpeechRecognition');
    const webkitSpeechDescriptor = Object.getOwnPropertyDescriptor(window, 'webkitSpeechRecognition');
    const mediaDevicesDescriptor = Object.getOwnPropertyDescriptor(navigator, 'mediaDevices');
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn() },
    });

    try {
      expect(detectSpeechRecognition()).toBe(false);
      expect(detectBackendVoice()).toBe(true);
    } finally {
      if (speechDescriptor) Object.defineProperty(window, 'SpeechRecognition', speechDescriptor);
      else delete (window as Window & { SpeechRecognition?: unknown }).SpeechRecognition;
      if (webkitSpeechDescriptor) Object.defineProperty(window, 'webkitSpeechRecognition', webkitSpeechDescriptor);
      else delete (window as Window & { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition;
      if (mediaDevicesDescriptor) Object.defineProperty(navigator, 'mediaDevices', mediaDevicesDescriptor);
      else delete (navigator as Navigator & { mediaDevices?: unknown }).mediaDevices;
    }
  });

  it('aborts pending backend speech before a late response can create audio', async () => {
    let resolveResponse!: (response: Response) => void;
    let requestSignal: AbortSignal | undefined;
    const pendingResponse = new Promise<Response>((resolve) => { resolveResponse = resolve; });
    vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) => {
      requestSignal = init?.signal;
      return pendingResponse;
    });
    const AudioMock = vi.fn();
    vi.stubGlobal('Audio', AudioMock);

    const speech = speakBackend({ text: 'Hola', lang: 'es-MX' });
    await Promise.resolve();
    stopBackendSpeech();
    resolveResponse(new Response('audio', { status: 200, headers: { 'Content-Type': 'audio/mpeg' } }));

    try {
      expect(requestSignal?.aborted).toBe(true);
      await expect(speech).rejects.toMatchObject({ name: 'AbortError' });
      expect(AudioMock).not.toHaveBeenCalled();
    } finally {
      stopBackendSpeech();
      vi.unstubAllGlobals();
    }
  });

  it('does not return backend audio stopped while playback is pending', async () => {
    let resolvePlay!: () => void;
    class PendingAudio {
      onended: (() => void) | null = null;
      onerror: (() => void) | null = null;

      constructor(readonly src: string) {}

      pause(): void {}

      removeAttribute(): void {}

      play(): Promise<void> {
        return new Promise((resolve) => { resolvePlay = resolve; });
      }
    }
    vi.stubGlobal('Audio', PendingAudio);
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:voice'),
      revokeObjectURL: vi.fn(),
    });
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('audio', { status: 200, headers: { 'Content-Type': 'audio/mpeg' } }));

    const speech = speakBackend({ text: 'Hola', lang: 'es-MX' });
    for (let attempt = 0; attempt < 4 && !resolvePlay; attempt += 1) await Promise.resolve();
    await new Promise<void>((resolve) => setTimeout(resolve, 0));
    expect(resolvePlay).toBeDefined();

    stopBackendSpeech();
    resolvePlay();

    await expect(speech).rejects.toMatchObject({ name: 'AbortError' });
    vi.unstubAllGlobals();
  });
});

it('stops backend voice after consecutive retries reach the cap', () => {
  expect(shouldStopBackendVoice(2)).toBe(false);
  expect(shouldStopBackendVoice(3)).toBe(true);
});


const voice = (name: string, lang: string, extra: Partial<SpeechSynthesisVoice> = {}) =>
  ({ name, lang, voiceURI: name, default: false, localService: true, ...extra }) as SpeechSynthesisVoice;

describe('voice selection', () => {
  it('skips the macOS novelty and compact voices that used to be picked first', () => {
    const voices = [
      voice('Eddy (Spanish (Mexico))', 'es-MX'),
      voice('Zarvox', 'es-MX'),
      voice('Paulina', 'es-MX'),
      voice('Samantha', 'en-US'),
    ];
    expect(pickBestVoice(voices, 'es-MX')?.name).toBe('Paulina');
  });

  it('prefers premium or enhanced downloads over the compact default', () => {
    const voices = [voice('Paulina', 'es-MX', { default: true }), voice('Mónica (Enhanced)', 'es-ES')];
    expect(pickBestVoice(voices, 'es-MX')?.name).toBe('Paulina');
    expect(pickBestVoice([voice('Jorge', 'es-ES'), voice('Mónica (Premium)', 'es-ES')], 'es-ES')?.name).toBe('Mónica (Premium)');
  });

  it('matches locales written with an underscore, as Android and some Safari builds do', () => {
    expect(scoreVoice(voice('Juan', 'es_MX'), 'es-MX')).toBeGreaterThanOrEqual(100);
  });

  it('prefers an exact locale over another region of the same language', () => {
    const voices = [voice('Jorge', 'es-ES'), voice('Juan', 'es-MX')];
    expect(pickBestVoice(voices, 'es-MX')?.name).toBe('Juan');
  });

  it('never returns a voice that speaks another language', () => {
    expect(pickBestVoice([voice('Samantha', 'en-US')], 'es-MX')).toBeUndefined();
    expect(pickBestVoice([], 'es-MX')).toBeUndefined();
  });
});

describe('speakable text', () => {
  it('drops links, emoji, formulas and markdown that a synthesizer reads aloud', () => {
    const text = '## Resumen\n- Visita https://example.com/docs ahora 😀\n1. Usa **negrita** y `codigo` con $x^2$.\n[Guía](https://a.b/c)';
    expect(cleanSpeechText(text)).toBe('Resumen Visita ahora Usa negrita y con . Guía');
  });

  it('replaces fenced code with the spoken placeholder', () => {
    expect(cleanSpeechText('Antes\n```js\nconsole.log(1)\n```\nDespués', 'bloque de código')).toBe('Antes bloque de código Después');
  });
});
