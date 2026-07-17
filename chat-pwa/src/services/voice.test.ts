import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getVoiceCapabilities, transcribeAudio } from './voice';

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
