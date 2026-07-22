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
  await expect(page.locator('.animate-intro-logo')).toHaveCount(0, { timeout: 10_000 });
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  await expect(page.locator('.animate-agent-avatar')).toBeVisible();
  await expect(page.getByLabel(/Historial del agente/i)).toBeVisible();
  if (captureLabel === 'before') {
    await page.locator('.animate-agent-avatar').evaluate((element) => {
      (element as HTMLElement).style.color = 'rgb(0, 107, 189)';
    });
    await page.locator('canvas').evaluate((element) => {
      (element as HTMLElement).style.filter = 'invert(27%) sepia(99%) saturate(1512%) hue-rotate(178deg) brightness(87%)';
    });
  }
  if (captureLabel !== 'before') {
    await expect(page.locator('.agent-empty-avatar')).toHaveCSS('color', 'rgb(107, 114, 128)');
  }

  if (captureLabel) {
    await page.screenshot({
      path: capturePath(testInfo.project.name, 'agent-light.png'),
      fullPage: true,
    });
  }

  await page.evaluate(() => localStorage.setItem('tc-theme', 'dark'));
  await page.reload();
  await expect(page.locator('.animate-intro-logo')).toHaveCount(0, { timeout: 10_000 });
  await expect(page.locator('html')).toHaveClass(/dark/);
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  if (captureLabel) {
    await page.screenshot({
      path: capturePath(testInfo.project.name, 'agent-dark.png'),
      fullPage: true,
    });
  }
});

test('history sidebar fits the viewport and retains its controls', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    if (!localStorage.getItem('tc-theme')) localStorage.setItem('tc-theme', 'light');
  });
  await page.goto('/#/');
  await expect(page.locator('.animate-intro-logo')).toHaveCount(0, { timeout: 10_000 });
  await page.getByLabel(/Abrir historial/i).click();
  const sidebar = page.locator('aside.sidebar-surface');
  await expect(sidebar).toBeVisible();
  await expect(sidebar.getByText('Historial', { exact: true })).toBeVisible();
  await expect(sidebar.getByLabel(/Cerrar menú/i)).toBeVisible();

  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
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
  await page.setViewportSize({ width: 640, height: 360 });
  await page.goto('/#/agent');
  await expect(page.getByRole('heading', { name: /TrinaxAI Agent/i })).toBeVisible();
  await expect(page.getByLabel(/Enviar/i)).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
