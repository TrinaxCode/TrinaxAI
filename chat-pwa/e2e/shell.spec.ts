import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'en');
  });
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, recommendedUrl: '', urls: [], needsRefresh: false, refreshCommand: '' },
  }));
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
  // Chromium starts tab navigation near the hash target after a deep-link reload.
  for (let attempt = 0; attempt < 50 && !(await skipLink.evaluate((link) => link === document.activeElement)); attempt++) {
    await page.keyboard.press('Shift+Tab');
  }
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

for (const destination of [
  { button: 'Settings', route: 'settings' },
  { button: 'Knowledge Browser', route: 'browser' },
]) {
  test(`closes the history sidebar when entering ${destination.route}`, async ({ page }) => {
    await page.goto('/');
    const sidebar = page.locator('aside.sidebar-surface');
    if (await sidebar.getAttribute('aria-hidden') === 'true') await page.getByRole('button', { name: 'Open history' }).click();
    await expect(sidebar).toHaveAttribute('aria-hidden', 'false');
    await sidebar.getByRole('button', { name: destination.button, exact: true }).click();
    await expect(page.locator(`[data-route-screen="${destination.route}"]`)).toBeVisible();
    await expect(sidebar).toHaveAttribute('aria-hidden', 'true');
    await expect(page.locator('#tc-main-content')).toHaveCSS('margin-left', '0px');

    await page.reload();
    await expect(page.locator(`[data-route-screen="${destination.route}"]`)).toBeVisible();
    await expect(sidebar).toHaveAttribute('aria-hidden', 'true');
    await page.setViewportSize({ width: 900, height: 700 });
    await page.setViewportSize({ width: 1280, height: 720 });
    await expect(sidebar).toHaveAttribute('aria-hidden', 'true');
  });
}

test('folder menu stays above chat rows and groups in a long history', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    const now = Date.now();
    localStorage.setItem('tc-chat-sessions', JSON.stringify([
      { id: 'folder-chat', title: 'Documentation chat', folderId: 'docs', engine: 'ollama', createdAt: now, updatedAt: now, messages: [] },
      ...Array.from({ length: 20 }, (_, i) => ({
        id: `chat-${i}`, title: `Conversation ${i + 1}`, engine: 'ollama', createdAt: now, updatedAt: now - i * 1000, messages: [],
      })),
      { id: 'last', title: 'Last conversation', engine: 'ollama', createdAt: now, updatedAt: now - 100_000, messages: [] },
    ]));
    localStorage.setItem('tc-chat-folders', JSON.stringify([{ id: 'docs', name: 'Documentation', createdAt: now }]));
  });
  await page.goto('/#/chat/last');
  if ((page.viewportSize()?.width ?? 0) < 1024) await page.getByRole('button', { name: 'Open history' }).click();
  await page.getByRole('button', { name: 'Documentation 1', exact: true }).first().click();
  const folderRow = page.locator('[data-session-row]').filter({ has: page.getByRole('button', { name: 'Documentation chat', exact: true }) });
  if ((page.viewportSize()?.width ?? 0) >= 1024) {
    await page.mouse.move(400, 10);
    const copy = folderRow.locator('.sidebar-session-copy');
    const width = (await copy.boundingBox())!.width;
    await expect(folderRow.locator('.sidebar-session-options')).toHaveCSS('opacity', '0');
    await folderRow.hover();
    await expect(copy).toHaveCSS('transform', 'matrix(1, 0, 0, 1, -4, 0)');
    await expect.poll(async () => (await copy.boundingBox())!.width).toBeLessThan(width - 30);
  }
  await folderRow.getByRole('button', { name: 'Chat options: Documentation chat' }).click();
  for (const name of ['General', 'Documentation', 'Delete chat']) {
    const option = folderRow.getByRole('button', { name, exact: true });
    await expect.poll(() => option.evaluate((button) => {
      const rect = button.getBoundingClientRect();
      return button.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
    })).toBe(true);
  }
  if (process.env.VISUAL_AUDIT_LABEL) await page.screenshot({ path: `visual-audit/${process.env.VISUAL_AUDIT_LABEL}/${testInfo.project.name}/history-menu.png` });
  await page.keyboard.press('Escape');
  await expect(folderRow.getByRole('button', { name: 'Chat options: Documentation chat' })).toBeFocused();
  await expect(folderRow.getByRole('button', { name: 'Documentation', exact: true })).toHaveCount(0);
  const row = page.locator('[data-session-row]').filter({ has: page.getByRole('button', { name: 'Last conversation' }) });
  await row.scrollIntoViewIfNeeded();
  if ((page.viewportSize()?.width ?? 0) >= 1024) await row.hover();
  await row.getByRole('button', { name: 'Chat options: Last conversation' }).click();
  const destination = row.getByRole('button', { name: 'Documentation', exact: true });
  await expect(destination).toBeVisible();
  await expect.poll(() => destination.evaluate((button) => {
    const rect = button.getBoundingClientRect();
    return button.contains(document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2));
  })).toBe(true);
  await destination.click();
  await expect(page.getByRole('button', { name: 'Documentation 2' }).first()).toBeVisible();
});

test('desktop documentation uses the full content column without clipping', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/#/docs');
  await expect(page.locator('.docs-content h1')).toBeVisible();
  const main = (await page.locator('#tc-main-content').boundingBox())!;
  await expect.poll(async () => {
    const content = (await page.locator('.docs-content').boundingBox())!;
    return Math.abs(main.x + main.width - content.x - content.width);
  }).toBeLessThan(2);
  const content = await page.locator('.docs-content').boundingBox();
  expect(content?.width ?? 0).toBeGreaterThan(1100);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  if (process.env.VISUAL_AUDIT_LABEL) await page.screenshot({ path: `visual-audit/${process.env.VISUAL_AUDIT_LABEL}/${testInfo.project.name}/docs-wide.png` });
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

test('identity questions are answered by the model', async ({ page }) => {
  let chatRequests = 0;
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({
    json: { models: [{ name: 'qwen3.5:4b', model: 'qwen3.5:4b', size: 1 }] },
  }));
  await page.route('**/api/ollama/api/chat', (route) => {
    chatRequests += 1;
    const request = route.request().postDataJSON() as { messages?: Array<{ content?: string }> };
    const prompt = request.messages?.at(-1)?.content || '';
    const content = prompt.includes('created') ? 'model creator answer' : 'model identity answer';
    return route.fulfill({
      status: 200,
      contentType: 'application/x-ndjson',
      body: `${JSON.stringify({ message: { content }, done: true })}\n`,
    });
  });
  await page.goto('/');

  const composer = page.getByRole('textbox', { name: /Type a message/ });
  await expect(composer).toBeVisible();
  await composer.fill('who are you');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('#tc-main-content').getByText('model identity answer', { exact: true })).toBeVisible();

  await composer.fill('who created you');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.locator('#tc-main-content').getByText('model creator answer', { exact: true })).toBeVisible();
  expect(chatRequests).toBe(2);
});
