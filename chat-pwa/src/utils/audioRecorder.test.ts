import { expect, it, vi } from 'vitest';

import { startAudioRecorder } from './audioRecorder';

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
