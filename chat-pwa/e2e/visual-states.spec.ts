import { expect, test, type Page } from '@playwright/test';
import path from 'node:path';

const captureLabel = process.env.VISUAL_AUDIT_LABEL;

function capturePath(project: string, name: string) {
  return path.resolve('visual-audit', captureLabel!, project, name);
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'es');
  });
  await page.route('**/api/network', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ online: true, recommendedUrl: '', urls: [], needsRefresh: false, refreshCommand: '' }),
  }));
  await page.route('**/api/rag/app-state', (route) => route.fulfill({
    status: 304,
  }));
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ models: [] }),
  }));
  await page.route('**/api/rag/**', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ ok: true, memories: [], collections: [], count: 0 }),
  }));
});

test('agent mode remains readable in light and dark themes', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('tc-theme')) localStorage.setItem('tc-theme', 'light');
  });
  await page.goto('/#/agent');
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: '¿En qué trabajamos hoy?' })).toBeVisible();
  await expect(page.getByRole('textbox', { name: 'Carpeta de trabajo' })).toHaveAttribute('placeholder', 'Carpeta de trabajo');
  await expect(page.locator('.agent-empty-state').getByRole('img', { name: 'TrinaxAI' })).toBeVisible();
  await expect(page.locator('.agent-empty-state .empty-chat-visual')).toHaveCSS('animation-name', 'float');
  await expect(page.locator('.agent-empty-state .chip-elegant')).toHaveCount(3);
  await expect(page.locator('.agent-empty-state')).toHaveCSS('opacity', '1');
  await expect(page.getByLabel(/Historial del agente/i)).toBeVisible();
  if (captureLabel === 'before') {
    await page.locator('canvas').evaluate((element) => {
      (element as HTMLElement).style.filter = 'invert(27%) sepia(99%) saturate(1512%) hue-rotate(178deg) brightness(87%)';
    });
  }

  if (captureLabel) {
    await page.screenshot({
      path: capturePath(testInfo.project.name, 'agent-light.png'),
      fullPage: true,
    });
  }

  await page.evaluate(() => localStorage.setItem('tc-theme', 'dark'));
  await page.reload();
  await expect(page.locator('html')).toHaveClass(/dark/);
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  await expect(page.locator('.agent-empty-state')).toHaveCSS('opacity', '1');
  await expect(page.locator('.agent-empty-state .empty-chat-visual > div')).toHaveCSS('background-color', 'rgb(0, 0, 0)');
  await expect(page.locator('.agent-empty-state .empty-chat-visual img')).toHaveCSS('animation-name', 'glow-pulse');
  if (captureLabel) {
    await page.screenshot({
      path: capturePath(testInfo.project.name, 'agent-dark.png'),
      fullPage: true,
    });
  }
});

test('agent history opens inside the main column', async ({ page }) => {
  await page.goto('/#/agent');
  await page.getByRole('button', { name: /Historial del agente/i }).click();
  const history = page.getByRole('dialog', { name: /Historial del agente/i });
  await expect(history).toBeVisible();
  await expect.poll(async () => Math.round((await history.boundingBox())?.x ?? -1)).toBe(
    Math.round((await page.locator('#tc-main-content').boundingBox())?.x ?? -2),
  );
});

for (const theme of ['light', 'dark'] as const) {
  test(`agent welcome rotates messages and working recommendations in ${theme} mode`, async ({ page }) => {
    await page.addInitScript((value) => localStorage.setItem('tc-theme', value), theme);
    await page.goto('/#/agent');
    const welcome = page.locator('.agent-empty-state');
    const suggestions = welcome.locator('.agent-suggestion');
    await expect(welcome.getByRole('heading')).toHaveText('¿En qué trabajamos hoy?');
    await expect(suggestions).toHaveCount(3);
    const original = await suggestions.allTextContents();
    await expect(welcome.getByRole('button')).toHaveCount(3);
    await welcome.hover();
    await expect(welcome.getByRole('heading')).toHaveText('¿Qué construimos hoy?', { timeout: 6_000 });
    expect(await suggestions.allTextContents()).toEqual(original);
    await expect.poll(() => suggestions.allTextContents(), { timeout: 16_000 }).not.toEqual(original);
    await expect(suggestions).toHaveCount(3);
    await suggestions.filter({ hasText: 'Generar tests' }).click();
    await expect(page.locator('textarea[name="agent-prompt"]')).toHaveValue('Genera pruebas unitarias para este código.');
    await expect(page.locator('textarea[name="agent-prompt"]')).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  });
}

test('agent recommendations rotate without animation when reduced motion is enabled', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/#/agent');
  const welcome = page.locator('.agent-empty-state');
  const suggestions = welcome.locator('.agent-suggestion');
  await expect(suggestions).toHaveCount(3);
  const original = await suggestions.allTextContents();
  await welcome.hover();
  await expect.poll(() => suggestions.allTextContents(), { timeout: 17_000 }).not.toEqual(original);
  await expect(welcome.getByRole('button')).toHaveCount(3);
  await expect(suggestions.first()).toBeVisible();
});

test('history sidebar fits the viewport and retains its controls', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('tc-theme')) localStorage.setItem('tc-theme', 'light');
  });
  await page.goto('/#/');
  await expect(page.locator('.chat-empty-motd')).toBeVisible();
  if (captureLabel) {
    await page.screenshot({ path: capturePath(testInfo.project.name, 'chat-light.png'), fullPage: true });
  }
  const sidebar = page.locator('aside.sidebar-surface');
  if (testInfo.project.name !== 'chromium-desktop') await page.getByLabel(/Abrir historial/i).click();
  await expect(sidebar).toHaveAttribute('aria-hidden', 'false');
  await expect(sidebar).toBeVisible();
  await expect(sidebar.getByText('Historial', { exact: true })).toBeVisible();
  await expect(sidebar.getByLabel(/Configuración/i)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  if (testInfo.project.name === 'chromium-desktop') {
    expect((await page.locator('#tc-main-content').boundingBox())?.x).toBe(280);
  }
  if (captureLabel) {
    await page.screenshot({
      path: capturePath(testInfo.project.name, 'history-light.png'),
      fullPage: true,
    });
  }
});

test('agent controls fit a 200 percent zoom equivalent viewport', async ({ page }) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('tc-theme')) localStorage.setItem('tc-theme', 'light');
  });
  await page.setViewportSize({ width: 639, height: 360 });
  await page.goto('/#/agent');
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  await expect(page.getByLabel(/Enviar/i)).toBeVisible();
  const toolsButton = page.getByRole('button', { name: /Herramientas del agente/i });
  await toolsButton.click();
  const tools = toolsButton.locator('..');
  await expect(tools.getByRole('button', { name: /RAG activado/i })).toBeVisible();
  await expect(tools.getByRole('button', { name: /Búsqueda web activada/i })).toBeVisible();
  await expect(tools.getByRole('button', { name: /Investigación profunda/i })).toBeVisible();
  await expect(page.getByRole('switch', { name: /Modo normal/i })).toHaveAttribute('aria-checked', 'false');
  await expect(tools.getByRole('option', { name: 'Auto | Router' })).toBeAttached();
  await expect(tools.getByRole('option', { name: 'General' })).toBeAttached();
  await expect(tools.getByRole('option', { name: 'Profundo' })).toBeAttached();
  await expect(tools.getByRole('option', { name: 'Rápido' })).toBeAttached();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

test('knowledge fragments keep a readable width across compact layouts', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'chromium-desktop');
  await page.route('**/api/rag/collections', (route) => route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify({ collections: [{ id: 'default', name: 'General' }] }),
  }));

  await page.setViewportSize({ width: 640, height: 700 });
  await page.goto('/#/browser');
  await expect(page.getByRole('tablist')).toBeVisible();

  await page.setViewportSize({ width: 768, height: 700 });
  const fragmentPanel = page.locator('.tc-browser-panel').last();
  await expect(fragmentPanel).toBeVisible();
  expect((await fragmentPanel.boundingBox())?.width).toBeGreaterThan(300);

  await page.setViewportSize({ width: 1024, height: 700 });
  await expect.poll(async () => (await fragmentPanel.boundingBox())?.width ?? 0).toBeGreaterThan(280);
});
