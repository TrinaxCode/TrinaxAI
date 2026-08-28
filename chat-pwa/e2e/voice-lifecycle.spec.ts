import { expect, test } from '@playwright/test';

test('STT on/off/on, Call Mode exit releases every microphone track', async ({ page }) => {
  test.skip(test.info().project.name !== 'chromium-desktop', 'fake microphone is configured for desktop Chromium');
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: undefined });
    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).__trinaxMicTracks = [];
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await original(constraints);
      (window as any).__trinaxMicTracks.push(...stream.getAudioTracks());
      return stream;
    };
  });
  await page.route('**/api/rag/app-state', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: { ETag: '"trinaxai-e2e-app-state"' },
    body: JSON.stringify({ schema_version: 2, revision: 0, values: { 'tc-onboarding-complete': 'true', 'tc-lang': 'en' } }),
  }));
  await page.goto('/#/chat');

  const start = page.getByRole('button', { name: 'Start dictation' });
  await expect(start).toBeVisible({ timeout: 10_000 });
  await start.click();
  await expect(page.getByRole('button', { name: 'Stop dictation' })).toBeVisible();
  await page.getByRole('button', { name: 'Stop dictation' }).click();
  await expect(start).toBeVisible();
  await start.click();
  await page.getByRole('button', { name: 'Stop dictation' }).click();

  await page.getByRole('button', { name: 'Call mode' }).click();
  await expect(page.getByRole('button', { name: 'Exit call mode' })).toBeVisible();
  await page.getByRole('button', { name: 'Exit call mode' }).click();
  await expect(page.getByRole('button', { name: 'Call mode' })).toBeVisible();

  await expect.poll(() => page.evaluate(() =>
    (window as any).__trinaxMicTracks.map((track: MediaStreamTrack) => track.readyState),
  )).toEqual(['ended', 'ended', 'ended']);
});

test('uses backend STT when Web Speech is unavailable', async ({ page }) => {
  test.skip(test.info().project.name !== 'chromium-desktop', 'fake microphone is configured for desktop Chromium');
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
    Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: undefined });
    Object.defineProperty(window, 'webkitSpeechRecognition', { configurable: true, value: undefined });

    const original = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    (window as any).__trinaxFallbackMicTracks = [];
    navigator.mediaDevices.getUserMedia = async (constraints) => {
      const stream = await original(constraints);
      (window as any).__trinaxFallbackMicTracks.push(...stream.getAudioTracks());
      return stream;
    };

    class FakeAudioContext {
      createMediaStreamSource() {
        return { connect: () => undefined };
      }

      createAnalyser() {
        return {
          fftSize: 0,
          smoothingTimeConstant: 0,
          getByteTimeDomainData: () => undefined,
        };
      }

      resume() { return Promise.resolve(); }
      close() { return Promise.resolve(); }
    }

    class FakeMediaRecorder {
      static instances = 0;
      static isTypeSupported(type: string) { return type === 'audio/webm'; }

      instance = ++FakeMediaRecorder.instances;
      mimeType = 'audio/webm';
      state = 'inactive';
      ondataavailable: ((event: { data: Blob }) => void) | null = null;
      onstop: (() => void) | null = null;
      onstart: (() => void) | null = null;

      start() {
        this.state = 'recording';
        this.onstart?.();
        if (this.instance !== 1) return;
        window.setTimeout(() => {
          if (this.state !== 'recording') return;
          this.ondataavailable?.({ data: new Blob(['audio'], { type: 'audio/webm' }) });
          this.state = 'inactive';
          this.onstop?.();
        }, 0);
      }

      stop() {
        if (this.state !== 'recording') return;
        this.state = 'inactive';
        this.onstop?.();
      }
    }

    Object.defineProperty(window, 'AudioContext', { configurable: true, value: FakeAudioContext });
    Object.defineProperty(window, 'MediaRecorder', { configurable: true, value: FakeMediaRecorder });
    window.requestAnimationFrame = () => 0;
  });
  await page.route('**/api/rag/app-state', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    headers: { ETag: '"trinaxai-e2e-backend-voice"' },
    body: JSON.stringify({ schema_version: 2, revision: 0, values: { 'tc-onboarding-complete': 'true', 'tc-lang': 'en' } }),
  }));
  let sttRequests = 0;
  await page.route('**/api/rag/v1/voice/stt', (route) => {
    sttRequests += 1;
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ text: 'backend transcript' }),
    });
  });

  await page.goto('/#/chat');
  const start = page.getByRole('button', { name: 'Start dictation' });
  await expect(start).toBeVisible({ timeout: 10_000 });
  await start.click();

  await expect.poll(() => sttRequests).toBe(1);
  await expect(page.getByRole('textbox', { name: 'Type a message' })).toHaveValue('backend transcript');
  await expect(page.getByRole('button', { name: 'Stop dictation' })).toBeVisible();
  await page.getByRole('button', { name: 'Stop dictation' }).click();
  await expect(start).toBeVisible();
  await expect.poll(() => page.evaluate(() =>
    (window as any).__trinaxFallbackMicTracks.length > 0
      && (window as any).__trinaxFallbackMicTracks.every((track: MediaStreamTrack) => track.readyState === 'ended'),
  )).toBe(true);
});
