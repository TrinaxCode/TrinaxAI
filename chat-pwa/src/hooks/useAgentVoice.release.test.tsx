import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const voice = vi.hoisted(() => ({
  detectBackendVoice: vi.fn(() => false),
  detectSpeechRecognition: vi.fn(() => false),
  transcribeAudio: vi.fn(),
}));
const recorder = vi.hoisted(() => ({ startAudioRecorder: vi.fn() }));

vi.mock('../services/voice', () => voice);
vi.mock('../utils/audioRecorder', () => recorder);

import { useAgentVoice } from './useAgentVoice';

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
  start = vi.fn(() => this.onstart?.());

  constructor() { FakeRecognition.instances.push(this); }
}

const t = (key: string) => key;

function options() {
  const input = document.createElement('textarea');
  input.value = 'Existing';
  input.focus = vi.fn();
  return {
    inputRef: { current: input },
    lang: 'es' as const,
    setInput: vi.fn(),
    setImageError: vi.fn(),
    t,
  };
}

describe('agent voice release paths', () => {
  beforeEach(() => {
    voice.detectBackendVoice.mockReturnValue(false);
    voice.detectSpeechRecognition.mockReturnValue(false);
    voice.transcribeAudio.mockReset();
    recorder.startAudioRecorder.mockReset();
    FakeRecognition.instances = [];
    delete (window as any).SpeechRecognition;
    delete (window as any).webkitSpeechRecognition;
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('reports dictation unavailable when neither voice implementation exists', () => {
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    expect(result.current.dictationAvailable).toBe(false);
    act(() => result.current.toggleDictation());
    expect(result.current.listening).toBe(false);
    expect(recorder.startAudioRecorder).not.toHaveBeenCalled();
  });

  it('starts, transcribes final and interim browser results, and stops', () => {
    voice.detectSpeechRecognition.mockReturnValue(true);
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    const opts = options();
    const { result, unmount } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    const recognition = FakeRecognition.instances[0];
    expect(result.current.dictationAvailable).toBe(true);
    expect(result.current.listening).toBe(true);
    expect(recognition).toMatchObject({ lang: 'es-MX', interimResults: true, continuous: true });

    const finalResult = Object.assign([{ transcript: 'final ' }], { isFinal: true });
    const interimResult = Object.assign([{ transcript: 'draft' }], { isFinal: false });
    act(() => recognition.onresult?.({ resultIndex: 0, results: [finalResult, interimResult] }));
    expect(opts.setInput).toHaveBeenLastCalledWith('Existing final draft');

    act(() => result.current.toggleDictation());
    expect(recognition.abort).toHaveBeenCalledOnce();
    expect(result.current.listening).toBe(false);
    unmount();
  });

  it('surfaces fatal recognition errors and does not restart after onend', async () => {
    vi.useFakeTimers();
    voice.detectSpeechRecognition.mockReturnValue(true);
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: FakeRecognition });
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    act(() => {
      FakeRecognition.instances[0].onerror?.({ error: 'not-allowed' });
      FakeRecognition.instances[0].onend?.();
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(1500); });

    expect(opts.setImageError).toHaveBeenCalledWith('voiceMicPermissionDenied');
    expect(result.current.listening).toBe(false);
    expect(FakeRecognition.instances).toHaveLength(1);
  });

  it.each([
    ['audio-capture', 'voiceNoMicrophone'],
    ['service-not-allowed', 'voiceRecognitionUnsupported'],
    ['language-not-supported', 'voiceRecognitionUnsupported'],
  ])('maps the fatal %s error to %s', (error, message) => {
    voice.detectSpeechRecognition.mockReturnValue(true);
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    act(() => FakeRecognition.instances[0].onerror?.({ error }));

    expect(opts.setImageError).toHaveBeenCalledWith(message);
    expect(result.current.listening).toBe(false);
  });

  it('restarts browser recognition after recoverable errors and onend', async () => {
    vi.useFakeTimers();
    voice.detectSpeechRecognition.mockReturnValue(true);
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    act(() => {
      FakeRecognition.instances[0].onerror?.({ error: 'no-speech' });
      FakeRecognition.instances[0].onend?.();
    });
    expect(result.current.listening).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(700); });

    expect(FakeRecognition.instances).toHaveLength(2);
    expect(result.current.listening).toBe(true);
    expect(opts.inputRef.current.focus).toHaveBeenCalledOnce();
  });

  it('uses backend recording when browser recognition is unavailable', async () => {
    voice.detectBackendVoice.mockReturnValue(true);
    const callbacks: any[] = [];
    const cancel = vi.fn();
    recorder.startAudioRecorder.mockImplementation(async (value: any) => {
      callbacks.push(value);
      value.onStart();
      return { cancel, stop: vi.fn() };
    });
    voice.transcribeAudio.mockResolvedValue('backend words');
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    await waitFor(() => expect(callbacks).toHaveLength(1));
    expect(result.current.dictationAvailable).toBe(true);
    expect(result.current.listening).toBe(true);

    await act(async () => {
      await callbacks[0].onSilence(new Blob(['voice'], { type: 'audio/webm' }));
    });
    expect(voice.transcribeAudio).toHaveBeenCalledWith(expect.any(Blob), 'es-MX', expect.any(AbortSignal));
    const update = opts.setInput.mock.calls.at(-1)?.[0];
    expect(update('Existing')).toBe('Existing backend words');

    act(() => result.current.cancelDictation());
    expect(result.current.listening).toBe(false);
  });

  it.each([
    ['NotAllowedError', 'voiceMicPermissionDenied'],
    ['UnknownError', 'voiceRecognitionFailed'],
  ])('surfaces backend recorder %s failures', async (name, message) => {
    vi.useFakeTimers();
    voice.detectBackendVoice.mockReturnValue(true);
    const failure = new Error('recorder failed');
    failure.name = name;
    recorder.startAudioRecorder.mockRejectedValue(failure);
    const opts = options();
    const { result } = renderHook(() => useAgentVoice(opts));

    act(() => result.current.toggleDictation());
    await act(async () => { await Promise.resolve(); });

    expect(opts.setImageError).toHaveBeenCalledWith(message);
    expect(result.current.listening).toBe(false);
    if (name === 'UnknownError') {
      await act(async () => { await vi.advanceTimersByTimeAsync(1200); });
      expect(recorder.startAudioRecorder).toHaveBeenCalledTimes(2);
    }
  });
});
