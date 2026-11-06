import { expect, test, type Page } from '@playwright/test';

const health = { ok: true, indexed: false, ollama: true, profile: '16gb', capabilities: { manage_system: true } };
const resources = {
  ok: true,
  profile: '16gb',
  ram: { total: 16_400_000_000, available: 9_000_000_000, used: 7_000_000_000, percent: 38 },
  vram: null,
  hardware: { cpu: { model: 'AMD Ryzen 7 5700U', cores: 16 }, ram: { total_bytes: 16_400_000_000 }, gpu: { vendor: 'none', name: 'No dedicated GPU' } },
};

async function mockFirstRun(page: Page, options: { healthy?: boolean; existingInstallation?: boolean } = {}) {
  const { healthy = true, existingInstallation = false } = options;
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, recommendedUrl: '', urls: [], needsRefresh: false, refreshCommand: '', existingInstallation, capabilities: { manageSystem: true } },
  }));
  // Reads see an empty server; writes are refused so the wizard's local result stays authoritative.
  await page.route('**/api/rag/app-state', (route) => (route.request().method() === 'GET'
    ? route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: { ETag: '"trinaxai-e2e-onboarding"' },
      body: JSON.stringify({ schema_version: 2, revision: 0, values: {} }),
    })
    : route.fulfill({ status: 503, json: { detail: 'offline' } })));
  await page.route('**/api/rag/health', (route) => (healthy ? route.fulfill({ json: health }) : route.abort()));
  await page.route('**/api/rag/resources', (route) => (healthy ? route.fulfill({ json: resources }) : route.abort()));
  // With the RAG service down the status check falls back to asking Ollama directly.
  await page.route('**/api/ollama/**', (route) => route.abort());
}

test.describe('first-run onboarding', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      if (sessionStorage.getItem('onb-e2e-seeded')) return;
      sessionStorage.setItem('onb-e2e-seeded', '1');
      localStorage.clear();
      localStorage.setItem('tc-lang', 'en');
      localStorage.setItem('tc-theme', 'dark');
    });
  });

  test('asks only the essentials and copies the installer profile into the browser', async ({ page }) => {
    await mockFirstRun(page);
    await page.goto('/');

    await expect(page.getByRole('heading', { level: 1, name: 'Welcome to TrinaxAI' })).toBeVisible();
    // Nothing the installer already did is asked again.
    await expect(page.locator('body')).not.toContainText(/GB of RAM|Ollama|Memory profile/);

    await page.getByRole('radio', { name: 'Spanish' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Bienvenido a TrinaxAI' })).toBeVisible();
    // The theme switch runs inside a view transition, so assert after the click.
    await page.getByRole('radio', { name: 'Claro' }).click();
    await expect(page.getByRole('radio', { name: 'Claro' })).toBeChecked();
    await expect(page.locator('html')).toHaveClass(/light/);
    await page.getByRole('radio', { name: 'Inglés' }).click();
    await expect(page.getByRole('heading', { level: 1, name: 'Welcome to TrinaxAI' })).toBeVisible();

    await page.getByLabel('What should we call you?').fill('Ana');
    await page.keyboard.press('Enter');

    await expect(page.getByRole('heading', { level: 1, name: 'Welcome to TrinaxAI' })).toBeHidden();
    const stored = await page.evaluate(() => ({
      done: localStorage.getItem('tc-onboarding-complete'),
      nickname: localStorage.getItem('tc-user-nickname'),
      chat: localStorage.getItem('tc-models-chat'),
      fast: localStorage.getItem('tc-models-fast'),
    }));
    expect(stored).toEqual({ done: 'true', nickname: 'Ana', chat: 'qwen3.5:4b', fast: 'qwen3.5:2b' });
  });

  test('floats over the app background with the bare logo', async ({ page }) => {
    await mockFirstRun(page);
    await page.goto('/');
    const root = page.locator('.onb-root');
    await expect(root).toBeVisible();
    await expect(root).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
    await expect(page.locator('canvas').first()).toBeAttached();
    const logo = page.getByRole('img', { name: 'TrinaxAI' });
    await expect(logo).toBeVisible();
    await expect(logo).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
  });

  test('still finishes when the local service is unreachable, without guessing models', async ({ page }) => {
    await mockFirstRun(page, { healthy: false });
    await page.goto('/');
    await page.getByRole('button', { name: 'Start chatting' }).click();

    await expect(page.getByRole('heading', { level: 1, name: 'Welcome to TrinaxAI' })).toBeHidden();
    const stored = await page.evaluate(() => ({ done: localStorage.getItem('tc-onboarding-complete'), chat: localStorage.getItem('tc-models-chat') }));
    expect(stored.done).toBe('true');
    expect(stored.chat).toBeNull();
  });

  test('fits the viewport without horizontal scroll', async ({ page }) => {
    await mockFirstRun(page);
    await page.goto('/');
    await expect(page.getByRole('button', { name: 'Start chatting' })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(0);
  });

  test('offers restore-or-new before the wizard on an existing installation', async ({ page }) => {
    await mockFirstRun(page, { existingInstallation: true });
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1, name: 'How do you want to use TrinaxAI?' })).toBeVisible();
    await page.getByRole('button', { name: /Use my existing setup/ }).click();
    await expect(page.getByRole('button', { name: 'Back' })).toBeFocused();
  });
});
