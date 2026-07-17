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
