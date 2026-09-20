import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const voice = vi.hoisted(() => ({
  detectBackendVoice: vi.fn(() => false),
  detectSpeechRecognition: vi.fn(() => false),
  detectSpeechSynthesis: vi.fn(() => false),
  shouldStopBackendVoice: vi.fn((retries: number) => retries >= 3),
  speakBackend: vi.fn(async ({ onEnded }: { onEnded?: () => void }) => { onEnded?.(); return undefined; }),
  stopBackendSpeech: vi.fn(),
  takeSpeechChunk: vi.fn((text: string, force = false) => ({ chunk: force ? text.trim() : '', remainder: force ? '' : text.trim() })),
  transcribeAudio: vi.fn(),
}));
const recorder = vi.hoisted(() => ({ startAudioRecorder: vi.fn() }));
const audio = vi.hoisted(() => ({ play: vi.fn() }));

vi.mock('../services/voice', () => voice);
vi.mock('../utils/audioRecorder', () => recorder);
vi.mock('../services/audioManager', () => ({ audioManager: audio }));

import { useChatVoice } from './useChatVoice';

const t = (key: string) => key;

function options(overrides: Partial<Parameters<typeof useChatVoice>[0]> = {}) {
  const input = document.createElement('textarea');
  const setInput = vi.fn();
  return {
    inputRef: { current: input },
    setInput,
    sendTextRef: { current: vi.fn(async () => undefined) },
    streaming: false,
    t,
    toast: { toast: vi.fn() },
    voiceLang: 'en-US',
    ...overrides,
  };
}

class FakeRecognition {
  static instances: FakeRecognition[] = [];
  lang = '';
  interimResults = false;
  continuous = false;
  onresult: ((event: any) => void) | null = null;
  onend: (() => void) | null = null;
  onerror: ((event: any) => void) | null = null;
  onstart: (() => void) | null = null;
  abort = vi.fn();
  stop = vi.fn(() => this.onend?.());
  start = vi.fn(() => this.onstart?.());
  constructor() { FakeRecognition.instances.push(this); }
}

class FakeUtterance {
  text: string;
  lang = '';
  rate = 1;
  pitch = 1;
  volume = 1;
  voice: unknown;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) { this.text = text; }
}

describe('chat voice hook', () => {
  beforeEach(() => {
    voice.detectBackendVoice.mockReturnValue(false);
    voice.detectSpeechRecognition.mockReturnValue(false);
    voice.detectSpeechSynthesis.mockReturnValue(false);
    voice.speakBackend.mockClear();
    voice.stopBackendSpeech.mockClear();
    voice.transcribeAudio.mockReset();
    recorder.startAudioRecorder.mockReset();
    audio.play.mockClear();
    FakeRecognition.instances = [];
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;
    delete (window as any).speechSynthesis;
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: false });
  });

  it('reports unsupported and insecure contexts, then runs browser dictation and call mode', async () => {
    const opts = options();
    const { result, rerender } = renderHook((props) => useChatVoice(props), { initialProps: opts });
    act(() => result.current.startDictation());
    expect(opts.toast.toast).toHaveBeenCalledWith('voiceRecognitionUnsupported', 'warning');

    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    voice.detectSpeechRecognition.mockReturnValue(true);
    rerender(opts);
    act(() => result.current.startDictation());
    const recognition = FakeRecognition.instances[0];
    expect(result.current.listening).toBe(true);
    recognition.onresult?.({ resultIndex: 0, results: [[{ transcript: 'hello' , }]] });
    recognition.onend?.();
    expect(opts.setInput).toHaveBeenCalledWith(expect.any(String));
    act(() => result.current.stopDictation());
    expect(audio.play).toHaveBeenCalledWith('stt-off');

    act(() => result.current.startCall());
    expect(result.current.callMode).toBe(true);
    act(() => result.current.stopVoice());
    expect(result.current.callMode).toBe(false);
  });

  it('handles recognition errors, speech pause restarts, and streaming guards', async () => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    voice.detectSpeechRecognition.mockReturnValue(true);
    const opts = options();
    const { result } = renderHook(() => useChatVoice(opts));
    act(() => result.current.startDictation());
    const recognition = FakeRecognition.instances[0];
    recognition.onerror?.({ error: 'not-allowed' });
    expect(opts.toast.toast).toHaveBeenCalledWith('voiceMicPermissionDenied', 'error');
    act(() => result.current.startDictation());
    FakeRecognition.instances.at(-1)?.onerror?.({ error: 'no-speech' });
    vi.useFakeTimers();
    act(() => FakeRecognition.instances.at(-1)?.onend?.());
    await act(async () => { await vi.advanceTimersByTimeAsync(700); });
    vi.useRealTimers();

    const streaming = options({ streaming: true });
    const streamHook = renderHook(() => useChatVoice(streaming));
    act(() => streamHook.result.current.startDictation());
    expect(streaming.sendTextRef.current).not.toHaveBeenCalled();
  });

  it('speaks browser responses, toggles active speech, and flushes streamed TTS', async () => {
    const synthesis = {
      speaking: false,
      pending: false,
      getVoices: vi.fn(() => [{ lang: 'en-US' }]),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      resume: vi.fn(),
      cancel: vi.fn(),
      speak: vi.fn((utterance: FakeUtterance) => {
        synthesis.speaking = true;
        queueMicrotask(() => { synthesis.speaking = false; utterance.onend?.(); });
      }),
    };
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: synthesis });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: FakeUtterance });
    voice.detectSpeechSynthesis.mockReturnValue(true);
    const opts = options();
    const { result } = renderHook(() => useChatVoice(opts));
    act(() => result.current.speak('Hello `code` and [link](https://example.test)', vi.fn(), 'answer-1'));
    await waitFor(() => expect(result.current.ttsSpeaking).toBe(false));
    expect(synthesis.speak).toHaveBeenCalled();
    act(() => result.current.speak('again', undefined, 'answer-1'));
    act(() => result.current.appendResponseToken('A sentence. ', true));
    act(() => result.current.finishResponseSpeech('fallback', vi.fn()));
    act(() => result.current.speakWithFallback('fallback text', vi.fn()));
    await waitFor(() => expect(voice.takeSpeechChunk).toHaveBeenCalled());
    act(() => result.current.stopSpeak());
    expect(synthesis.cancel).toHaveBeenCalled();
  });

  it('uses backend TTS when the browser exposes no voices', async () => {
    const synthesis = {
      speaking: false,
      pending: false,
      getVoices: vi.fn(() => []),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      resume: vi.fn(),
      cancel: vi.fn(),
      speak: vi.fn(),
    };
    Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: synthesis });
    voice.detectSpeechSynthesis.mockReturnValue(true);
    const { result } = renderHook(() => useChatVoice(options()));

    act(() => result.current.speak('backend voice'));

    await waitFor(() => expect(voice.speakBackend).toHaveBeenCalled());
    expect(synthesis.speak).not.toHaveBeenCalled();
  });

  it('uses backend TTS when the browser has no speech synthesis API', async () => {
    const { result } = renderHook(() => useChatVoice(options()));

    act(() => result.current.speak('backend voice'));

    await waitFor(() => expect(voice.speakBackend).toHaveBeenCalled());
  });

  it('uses backend recording when browser recognition is unavailable', async () => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    voice.detectBackendVoice.mockReturnValue(true);
    const callbacks: any[] = [];
    recorder.startAudioRecorder.mockImplementation(async (value: any) => {
      callbacks.push(value);
      value.onStart?.();
      return { cancel: vi.fn(), stop: vi.fn() };
    });
    voice.transcribeAudio.mockResolvedValue('backend words');
    const opts = options();
    const { result } = renderHook(() => useChatVoice(opts));
    act(() => result.current.startDictation());
    await waitFor(() => expect(callbacks).toHaveLength(1));
    await act(async () => { await callbacks[0].onSilence(new Blob(['audio'], { type: 'audio/webm' })); });
    expect(opts.setInput).toHaveBeenCalledWith(expect.any(Function));
    callbacks[0].onError(new DOMException('denied', 'NotAllowedError'));
    expect(opts.toast.toast).toHaveBeenCalledWith('voiceMicPermissionDenied', 'error');
    act(() => result.current.stopVoice());
    expect(recorder.startAudioRecorder).toHaveBeenCalled();
  });

  it('falls back to backend recording when native call recognition reports a network error', async () => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    voice.detectSpeechRecognition.mockReturnValue(true);
    voice.detectBackendVoice.mockReturnValue(true);
    const callbacks: any[] = [];
    recorder.startAudioRecorder.mockImplementation(async (value: any) => {
      callbacks.push(value);
      value.onStart?.();
      return { cancel: vi.fn(), stop: vi.fn() };
    });
    const opts = options();
    const { result } = renderHook(() => useChatVoice(opts));

    act(() => result.current.startCall());
    FakeRecognition.instances[0].onerror?.({ error: 'network' });

    await waitFor(() => expect(callbacks).toHaveLength(1));
    expect(result.current.callMode).toBe(true);
    expect(result.current.listening).toBe(true);
  });
});
