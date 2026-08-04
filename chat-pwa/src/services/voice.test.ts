import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getVoiceCapabilities, takeSpeechChunk, transcribeAudio } from './voice';

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
  beforeEach(() => vi.restoreAllMocks());

  it('uses the versioned capabilities endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      stt: { available: true, engine: 'whisper', model: 'local' },
      tts: { available: false, preferred: null, backends: [] },
    }), { status: 200 }));

    await getVoiceCapabilities();

    expect(fetchMock.mock.calls[0]?.[0]).toEqual(
      expect.stringMatching(/\/v1\/voice\/capabilities$/),
    );
  });

  it('uses the versioned transcription endpoint', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ text: 'hola' }), { status: 200 }));

    await transcribeAudio(new Blob(['audio'], { type: 'audio/webm' }), 'es-MX');

    expect(fetchMock.mock.calls[0]?.[0]).toEqual(expect.stringMatching(/\/v1\/voice\/stt$/));
  });
});
