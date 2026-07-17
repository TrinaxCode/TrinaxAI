import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
  });
  await page.route('**/api/rag/app-state', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        headers: { ETag: '"trinaxai-app-state-v2-0"' },
        body: JSON.stringify({ schema_version: 2, revision: 0, values: {} }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true, revision: 1 }),
    });
  });
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ models: [] }),
  }));
  await page.route('**/api/rag/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, memories: [], collections: [], summary: '', count: 0 }),
  }));
});

test('deep links survive reload and expose a working skip link', async ({ page }) => {
  await page.goto('/#/settings/memory');
  await expect(page.getByText('Auto-summary')).toBeVisible({ timeout: 10_000 });
  await page.reload();
  await expect(page).toHaveURL(/#\/settings\/memory$/);
  await expect(page.getByText('Auto-summary')).toBeVisible({ timeout: 10_000 });

  const skipLink = page.getByRole('link', { name: 'Skip to main content' });
  await page.keyboard.press('Tab');
  await expect(skipLink).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#tc-main-content')).toBeFocused();
});

test('the active route fits the viewport without horizontal document overflow', async ({ page }) => {
  await page.goto('/#/settings/general');
  await expect(page.getByText('Settings', { exact: true }).first()).toBeVisible({ timeout: 10_000 });

  const dimensions = await page.evaluate(() => ({
    viewport: window.innerWidth,
    document: document.documentElement.scrollWidth,
  }));
  expect(dimensions.document).toBeLessThanOrEqual(dimensions.viewport + 1);
});

test('sound preference applies immediately and survives reload', async ({ page }) => {
  await page.goto('/#/settings/general');
  const soundSwitch = page.getByRole('switch', { name: 'Sound effects' });
  await expect(soundSwitch).toHaveAttribute('aria-checked', 'true');
  await soundSwitch.click();
  await expect(soundSwitch).toHaveAttribute('aria-checked', 'false');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('tc-sound-effects'))).toBe('0');
  await page.reload();
  await expect(page.getByRole('switch', { name: 'Sound effects' })).toHaveAttribute('aria-checked', 'false');
  await page.getByRole('switch', { name: 'Sound effects' }).click();
  await expect(page.getByRole('switch', { name: 'Sound effects' })).toHaveAttribute('aria-checked', 'true');
});
