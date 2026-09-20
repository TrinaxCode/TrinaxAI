import { expect, test, type Page } from '@playwright/test';

/**
 * Two explicit presentation decisions are locked here:
 *  - The composer must read as a flat, slightly translucent grey bar in dark
 *    mode, the same way it reads as a bright white bar in light mode, instead
 *    of sinking into the black page behind a gradient and a blue halo.
 *  - The AI lifecycle controls ("Apagar IA" / "Encender IA") use a solid fill
 *    in light mode; dark mode keeps the quieter tinted treatment.
 */

type Theme = 'dark' | 'light';

async function stubShell(page: Page, theme: Theme) {
  // The app-state sync treats its payload as authoritative, so the requested
  // theme has to travel in both places.
  await page.addInitScript((value) => {
    localStorage.setItem('tc-onboarding-complete', 'true');
    localStorage.setItem('tc-lang', 'es');
    localStorage.setItem('tc-theme', value);
  }, theme);
  await page.route('**/api/network', (route) => route.fulfill({
    json: { online: true, existingInstallation: true, capabilities: { manageSystem: true } },
  }));
  await page.route('**/api/rag/**', (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith('/app-state')) {
      return route.fulfill({
        status: 200,
        headers: { ETag: '"theme-surfaces"' },
        json: {
          schema_version: 2,
          revision: 0,
          values: { 'tc-onboarding-complete': 'true', 'tc-lang': 'es', 'tc-theme': theme },
        },
      });
    }
    if (pathname.endsWith('/v1/settings/web-search')) return route.fulfill({ json: { enabled: false, providers: {} } });
    if (pathname.endsWith('/collections')) return route.fulfill({ json: { collections: [] } });
    return route.fulfill({ json: { ok: true, memories: [], collections: [], count: 0 } });
  });
  await page.route('**/api/ollama/api/tags', (route) => route.fulfill({ json: { models: [] } }));
}

function composer(page: Page) {
  return page.locator('.composer-surface').first();
}

function composerStyle(page: Page) {
  return composer(page).evaluate((element) => {
    const style = getComputedStyle(element);
    return {
      background: style.backgroundColor,
      backgroundImage: style.backgroundImage,
      border: style.borderTopColor,
      boxShadow: style.boxShadow,
    };
  });
}

test('keeps the dark composer a flat translucent grey bar', async ({ page }) => {
  await stubShell(page, 'dark');
  await page.goto('/');
  await expect(composer(page)).toBeVisible();
  await expect(page.locator('html')).toHaveClass(/\bdark\b/);

  // Blur first: the composer is focused on load, and every surface property
  // transitions, so the assertions below retry until the state settles.
  await page.evaluate(() => (document.activeElement instanceof HTMLElement ? document.activeElement.blur() : undefined));
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgba(255, 255, 255, 0.1)');
  const idle = await composerStyle(page);
  expect(idle.background).toBe('rgba(148, 163, 184, 0.22)');
  expect(idle.backgroundImage).toBe('none');
  expect(idle.boxShadow).not.toContain('rgba(22, 141, 226');

  await page.locator('.composer-surface textarea').first().focus();
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgba(22, 141, 226, 0.55)');
  const focused = await composerStyle(page);
  expect(focused.boxShadow).toContain('rgba(22, 141, 226, 0.16)');
});

test('keeps the light composer as the bright white bar', async ({ page }) => {
  await stubShell(page, 'light');
  await page.goto('/');
  await expect(composer(page)).toBeVisible();
  await expect(page.locator('html')).toHaveClass(/\blight\b/);

  await expect(composer(page)).toHaveCSS('background-color', 'rgba(255, 255, 255, 0.92)');
  await expect(composer(page)).toHaveCSS('border-top-color', 'rgba(0, 107, 189, 0.22)');
  const style = await composerStyle(page);
  expect(style.backgroundImage).toBe('none');
});

test('renders the AI lifecycle controls as solid fills in light mode', async ({ page }) => {
  await stubShell(page, 'light');
  await page.goto('/#/settings/advanced');

  const shutdown = page.getByRole('button', { name: 'Apagar IA' });
  const startup = page.getByRole('button', { name: 'Encender IA' });
  await expect(shutdown).toBeVisible();
  await expect(shutdown).toHaveCSS('background-color', 'rgb(220, 38, 38)');
  await expect(shutdown).toHaveCSS('color', 'rgb(255, 255, 255)');
  await expect(startup).toHaveCSS('background-color', 'rgb(4, 120, 87)');
  await expect(startup).toHaveCSS('color', 'rgb(255, 255, 255)');
});

test('keeps the quiet tinted AI lifecycle controls in dark mode', async ({ page }) => {
  await stubShell(page, 'dark');
  await page.goto('/#/settings/advanced');

  const shutdown = page.getByRole('button', { name: 'Apagar IA' });
  await expect(shutdown).toBeVisible();
  await expect(shutdown).toHaveCSS('background-color', 'rgba(239, 68, 68, 0.1)');
  await expect(page.getByRole('button', { name: 'Encender IA' })).toHaveCSS('background-color', 'rgba(34, 197, 94, 0.1)');
});
