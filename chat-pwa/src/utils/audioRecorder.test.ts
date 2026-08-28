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

it('does not let a newer start inherit a superseded pending recorder', async () => {
  const firstTrackStop = vi.fn();
  const secondTrackStop = vi.fn();
  const stream = (stop: () => void) => ({
    getTracks: () => [{
      kind: 'audio',
      stop,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }],
  });
  let resolveFirst: (value: ReturnType<typeof stream>) => void = () => {};
  const getUserMedia = vi.fn()
    .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
    .mockResolvedValueOnce(stream(secondTrackStop));
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    start() { this.onstart(); }
    stop() {}
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({ fftSize: 0, smoothingTimeConstant: 0, getByteTimeDomainData: vi.fn() });
    close = vi.fn().mockResolvedValue(undefined);
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia },
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());

  const first = startAudioRecorder({ onSilence: vi.fn(), onError: vi.fn() });
  const second = startAudioRecorder({ onSilence: vi.fn(), onError: vi.fn() });
  const secondRecorder = await second;
  resolveFirst(stream(firstTrackStop));
  const firstRecorder = await first;

  firstRecorder.cancel();
  expect(getUserMedia).toHaveBeenCalledTimes(2);
  expect(firstTrackStop).toHaveBeenCalledOnce();
  expect(secondTrackStop).not.toHaveBeenCalled();

  secondRecorder.cancel();
  expect(secondTrackStop).toHaveBeenCalledOnce();
  vi.unstubAllGlobals();
});

it('releases the microphone when recorder start fails', async () => {
  const trackStop = vi.fn();
  const contextClose = vi.fn().mockResolvedValue(undefined);
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    start() { throw new Error('start failed'); }
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({ fftSize: 0, smoothingTimeConstant: 0, getByteTimeDomainData: vi.fn() });
    close = contextClose;
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ kind: 'audio', stop: trackStop, addEventListener: vi.fn(), removeEventListener: vi.fn() }],
    }) },
  });

  await expect(startAudioRecorder({ onSilence: vi.fn(), onError: vi.fn() })).rejects.toThrow('start failed');

  expect(trackStop).toHaveBeenCalledOnce();
  expect(contextClose).toHaveBeenCalledOnce();
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

it('stops once at the maximum duration and ignores late recorder events', async () => {
  vi.useFakeTimers();
  const trackStop = vi.fn();
  const contextClose = vi.fn().mockResolvedValue(undefined);
  const recorderStop = vi.fn();
  let mediaRecorder: { onerror: () => void; onstop: () => void } | undefined;
  vi.stubGlobal('MediaRecorder', class {
    static isTypeSupported = () => true;
    ondataavailable = () => {};
    onstop = () => {};
    onerror = () => {};
    onstart = () => {};
    constructor() { mediaRecorder = this; }
    start() { this.onstart(); }
    stop() { recorderStop(); }
  });
  vi.stubGlobal('AudioContext', class {
    createMediaStreamSource = () => ({ connect: vi.fn() });
    createAnalyser = () => ({ fftSize: 0, smoothingTimeConstant: 0, getByteTimeDomainData: vi.fn() });
    close = contextClose;
  });
  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: { getUserMedia: vi.fn().mockResolvedValue({
      getTracks: () => [{ kind: 'audio', stop: trackStop, addEventListener: vi.fn(), removeEventListener: vi.fn() }],
    }) },
  });
  vi.stubGlobal('requestAnimationFrame', vi.fn(() => 1));
  vi.stubGlobal('cancelAnimationFrame', vi.fn());
  const onSilence = vi.fn();
  const onError = vi.fn();

  const recorder = await startAudioRecorder({ onSilence, onError }, 1500, 0.015, 1000);
  vi.advanceTimersByTime(1000);

  expect(recorderStop).toHaveBeenCalledOnce();
  mediaRecorder?.onstop();
  mediaRecorder?.onerror();
  mediaRecorder?.onstop();
  recorder.stop();
  recorder.cancel();

  expect(onSilence).toHaveBeenCalledOnce();
  expect(onError).not.toHaveBeenCalled();
  expect(trackStop).toHaveBeenCalledOnce();
  expect(contextClose).toHaveBeenCalledOnce();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
