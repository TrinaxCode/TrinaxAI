import { expect, test } from '@playwright/test';

test('production manifest and service worker support an offline relaunch', async ({ browser, baseURL }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop', 'One Chromium installability check is sufficient.');
  const context = await browser.newContext({
    baseURL,
    ignoreHTTPSErrors: true,
    serviceWorkers: 'allow',
  });
  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
  });
  await page.goto('/');
  const manifest = await page.evaluate(async () => {
    const link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
    if (!link) throw new Error('Manifest link missing');
    return fetch(link.href).then((response) => response.json());
  });
  expect(manifest.name).toBe('TrinaxAI');
  expect(manifest.display).toBe('standalone');
  expect(manifest.icons.some((icon: { sizes?: string }) => icon.sizes === '512x512')).toBe(true);

  await page.evaluate(() => navigator.serviceWorker.ready.then(() => undefined));
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator('#root')).not.toBeEmpty();
  await context.setOffline(false);
  await context.close();
});
