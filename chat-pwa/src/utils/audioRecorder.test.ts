import { expect, it, vi } from 'vitest';

import { startAudioRecorder } from './audioRecorder';

it('releases the microphone when recorder initialization fails', async () => {
  const trackStop = vi.fn();
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    constructor() { throw new Error('recorder failed'); }
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] }) },
  });

  await expect(startAudioRecorder({ onSilence: vi.fn(), onError: vi.fn() })).rejects.toThrow('recorder failed');

  expect(trackStop).toHaveBeenCalledOnce();
  vi.unstubAllGlobals();
});

it('does not transcribe after a recorder error', async () => {
  let mediaRecorder: { onerror: () => void; onstop: () => void } | undefined;
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    constructor() { mediaRecorder = this; }
    start() { this.onstart(); }
    stop() { this.onstop(); }
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({ fftSize: 0, smoothingTimeConstant: 0, getByteTimeDomainData: vi.fn() });
    close = vi.fn().mockResolvedValue(undefined);
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }) },
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const onSilence = vi.fn();
  const onError = vi.fn();

  await startAudioRecorder({ onSilence, onError });
  mediaRecorder?.onerror();
  mediaRecorder?.onstop();

  expect(onError).toHaveBeenCalledOnce();
  expect(onSilence).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it('releases the microphone without transcribing when cancelled', async () => {
  const trackStop = vi.fn();
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    start() { this.onstart(); }
    stop() { this.onstop(); }
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({ fftSize: 0, smoothingTimeConstant: 0, getByteTimeDomainData: vi.fn() });
    close = vi.fn().mockResolvedValue(undefined);
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: trackStop }] }) },
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const onSilence = vi.fn();

  const recorder = await startAudioRecorder({ onSilence, onError: vi.fn() });
  recorder.cancel();

  expect(trackStop).toHaveBeenCalledOnce();
  expect(onSilence).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

it('keeps listening during initial silence', async () => {
  const stop = vi.fn();
  const frames: FrameRequestCallback[] = [];
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    start() { this.onstart(); }
    stop() { stop(); this.onstop(); }
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({
      fftSize: 0,
      smoothingTimeConstant: 0,
      getByteTimeDomainData: (data: Uint8Array) => data.fill(128),
    });
    close = vi.fn().mockResolvedValue(undefined);
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ kind: 'audio', stop: vi.fn(), addEventListener: vi.fn(), removeEventListener: vi.fn() }] }) },
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn((callback: FrameRequestCallback) => { frames.push(callback); return frames.length; }));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  vi.spyOn(Date, 'now').mockReturnValueOnce(0).mockReturnValue(10_000);

  const recorder = await startAudioRecorder({ onSilence: vi.fn(), onError: vi.fn() }, 2200);
  frames[0](10_000);

  expect(stop).not.toHaveBeenCalled();
  recorder.cancel();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});
