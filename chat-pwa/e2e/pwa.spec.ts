import { expect, test } from '@playwright/test';

test('configures web search without exposing provider secrets', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
  });
  const publicSettings = {
    enabled: true, preferred_provider: 'duckduckgo', active_provider: 'duckduckgo', source: 'managed',
    externally_managed: { preferred_provider: false, brave_api_key: false, searxng_url: false },
    providers: {
      duckduckgo: { available: true, configured: true, requires_api_key: false },
      brave: { available: true, configured: true, requires_api_key: true },
      searxng: { available: true, configured: false, requires_api_key: false, base_url: null },
    },
  };
  await page.route('**/api/rag/v1/settings/web-search', (route) => route.fulfill({ json: publicSettings }));
  await page.route('**/api/rag/v1/settings/web-search/test', (route) => route.fulfill({
    json: { ok: true, provider: 'duckduckgo', result_count: 1 },
  }));
  await page.goto('/#/settings/web-search');
  await expect(page.getByLabel('Preferred search engine')).toHaveValue('duckduckgo');
  await expect(page.locator('input[type="password"]')).toHaveCount(0);
  await page.getByRole('button', { name: 'Test connection' }).click();
  await expect(page.getByText('Connection successful: duckduckgo')).toBeVisible();
  await expect(page.locator('body')).not.toContainText('test-secret-value');
});

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
  expect(manifest.name).toBe('TrinaxAI Chat');
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
